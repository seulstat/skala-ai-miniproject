#!/usr/bin/env bash
# API 스모크 (CP2): 서버를 임시 데이터 폴더로 띄우고 curl로 stream → pending → resume 시나리오를 확인한다.
#   bash sh/smoke_chat.sh fake     fake 모델: ErrorRaised 경로 + REST 엔드포인트 (ollama·네트워크 불필요)
#   bash sh/smoke_chat.sh ollama   ollama 모델: 승인 → 저장까지 정상 경로 (ollama serve와 모델이 있어야 한다)
# 환경변수: SMOKE_PORT(기본 8110), FAST_MODEL·QUALITY_MODEL·EMBEDDING_MODEL(ollama 기본값은 agent.md §5 예시),
#           SMOKE_TRIES(ollama에서 승인 대기까지 가는 시도 횟수, 기본 3 — 소형 모델은 구조화 출력이 가끔 실패한다),
#           SMOKE_URL(이미 떠 있는 서버를 쓴다. 그 서버의 데이터를 바꾸는 NOT_READY 점검은 건너뛴다).
set -euo pipefail
cd "$(dirname "$0")/.."
MODE=${1:-fake}
case "$MODE" in fake|ollama) ;; *) echo "사용법: bash sh/smoke_chat.sh [fake|ollama]" >&2; exit 2 ;; esac
PY=.venv/bin/python; [ -x "$PY" ] || PY=python3
TMP=$(mktemp -d); SERVER_PID=""
cleanup() {   # 종료 코드는 스크립트의 것을 그대로 돌려준다 (wait가 서버의 143을 덮어쓰지 않게)
  local rc=$?
  if [ -n "$SERVER_PID" ]; then kill "$SERVER_PID" 2>/dev/null || true; wait "$SERVER_PID" 2>/dev/null || true; fi
  rm -rf "$TMP"; exit "$rc"
}
trap cleanup EXIT
step() { printf '\n[%s]\n' "$*"; }
die() { echo "FAIL: $*" >&2; [ -f "$TMP/server.log" ] && tail -15 "$TMP/server.log" >&2; exit 1; }
# JSON 값 확인: jq_py <파일> <파이썬 식(d=JSON)>  — 식이 거짓이면 실패
check() { "$PY" -c 'import json,sys; d=json.load(open(sys.argv[1])); sys.exit(0 if eval(sys.argv[2]) else 1)' "$1" "$2" || die "$3 ($(head -c 300 "$1"))"; }
http() { curl -s -o "$TMP/body.json" -w '%{http_code}' "$@"; }   # 본문은 $TMP/body.json, 상태 코드는 stdout
stream() {   # stream <thread> <message> → $TMP/stream.out (SSE 원문), $TMP/events.json (이벤트 목록)
  curl -sN --max-time 300 -G "$URL/chat/stream" --data-urlencode "thread_id=$1" --data-urlencode "message=$2" >"$TMP/stream.out" || die "stream 요청 실패"
  "$PY" -c 'import json,sys
ev=[l[6:] for l in open(sys.argv[1]).read().split("\n\n") if l]
assert ev and ev[-1]=="[DONE]", "마지막이 [DONE]이 아님: %r" % ev[-1:]
json.dump([json.loads(e) for e in ev[:-1]], open(sys.argv[2],"w"))' "$TMP/stream.out" "$TMP/events.json" || die "SSE 형식 오류"
}

if [ "$MODE" = ollama ]; then
  export FAST_MODEL=${FAST_MODEL:-ollama:qwen3:0.6b} QUALITY_MODEL=${QUALITY_MODEL:-ollama:qwen3:8b}
  curl -sf --max-time 3 "${OLLAMA_BASE_URL:-http://localhost:11434}/api/tags" >"$TMP/tags.json" || { echo "ollama 서버가 없습니다 — 'ollama serve'를 먼저 실행하세요" >&2; exit 2; }
  have() { grep -Eq "\"name\":\"${1#ollama:}(:latest)?\"" "$TMP/tags.json"; }
  for m in "$FAST_MODEL" "$QUALITY_MODEL"; do
    have "$m" || { echo "ollama에 모델이 없습니다: ${m#ollama:} ('ollama pull ${m#ollama:}')" >&2; exit 2; }
  done
  if [ -z "${EMBEDDING_MODEL:-}" ]; then   # 임베딩 모델이 없어도 API 흐름은 확인할 수 있다 (검색 품질은 확인 안 됨)
    if have ollama:nomic-embed-text; then export EMBEDDING_MODEL=ollama:nomic-embed-text
    else export EMBEDDING_MODEL=fake; echo "참고: nomic-embed-text가 없어 EMBEDDING_MODEL=fake로 진행합니다 ('ollama pull nomic-embed-text')"; fi
  fi
else
  export FAST_MODEL=fake QUALITY_MODEL=fake EMBEDDING_MODEL=fake
fi

OWN_SERVER=0
if [ -z "${SMOKE_URL:-}" ]; then
  OWN_SERVER=1; PORT=${SMOKE_PORT:-8110}; URL=http://127.0.0.1:$PORT
  export COACH_DATA_DIR="$TMP/data"; mkdir -p "$COACH_DATA_DIR"; cp -R examples/sample_user/. "$COACH_DATA_DIR/"
  step "서버 기동 :$PORT ($MODE, 데이터 $COACH_DATA_DIR)"
  "$PY" -m uvicorn server:app --host 127.0.0.1 --port "$PORT" --log-level warning >"$TMP/server.log" 2>&1 &
  SERVER_PID=$!
  for _ in $(seq 60); do curl -sf "$URL/api/readiness" >/dev/null 2>&1 && break; kill -0 "$SERVER_PID" 2>/dev/null || die "서버가 종료됨"; sleep 0.5; done
else
  URL=$SMOKE_URL
fi

step "REST: 준비 점검·프로필·문서·카드"
[ "$(http "$URL/api/readiness")" = 200 ] || die "readiness"; check "$TMP/body.json" 'd["ready"] is True' "준비 미완료 — 서류를 확인하세요"
[ "$(http "$URL/api/profile")" = 200 ] || die "profile"; check "$TMP/body.json" 'd["target_role"]' "프로필"
[ "$(http "$URL/api/docs")" = 200 ] || die "docs"; check "$TMP/body.json" 'len(d) >= 1' "문서 목록"
[ "$(http "$URL/api/cards")" = 200 ] || die "cards"; check "$TMP/body.json" 'isinstance(d, list)' "카드 목록"
[ "$(http "$URL/api/cards/due")" = 200 ] || die "cards/due"
[ "$(http -X POST "$URL/api/cards/C9999/review" -H 'content-type: application/json' -d '{"result":"known"}')" = 404 ] || die "없는 카드는 404여야 함"
check "$TMP/body.json" 'd["error"]["code"] == "NOT_FOUND"' "NOT_FOUND 본문"
[ "$(http -X PUT "$URL/api/profile" -H 'content-type: application/json' -d '{"goal":"g","target_role":"r","tone_preference":"아무말"}')" = 422 ] || die "잘못된 enum은 422여야 함"
check "$TMP/body.json" 'd["error"]["code"] == "INPUT_INVALID"' "INPUT_INVALID 본문"
echo "ok"

if [ "$OWN_SERVER" = 1 ]; then
  step "SSE: 서류가 없으면 NOT_READY → [DONE]"
  DOC=$(ls "$COACH_DATA_DIR/docs" | head -1)
  [ "$(http -X DELETE "$URL/api/docs/$DOC")" = 200 ] || die "문서 삭제"
  stream smoke-nr "민원을 줄였다고 말하고 싶어"
  check "$TMP/events.json" '[e["type"] for e in d] == ["ErrorRaised"] and d[0]["error"]["code"] == "NOT_READY" and not d[0]["error"]["recoverable"]' "NOT_READY 이벤트"
  "$PY" -c 'import json,sys; print(json.dumps({"name":sys.argv[1],"content":open(sys.argv[2],encoding="utf-8").read()}))' "$DOC" "examples/sample_user/docs/$DOC" >"$TMP/doc.json"
  [ "$(http -X POST "$URL/api/docs" -H 'content-type: application/json' --data-binary @"$TMP/doc.json")" = 200 ] || die "문서 복구"
  echo "ok"
fi

MSG="배송 지연 원인을 데이터로 찾아서 민원을 줄였다고 말하고 싶어"
if [ "$MODE" = fake ]; then
  step "SSE: fake 모델은 빈 응답이라 ErrorRaised → [DONE]"
  stream smoke-1 "$MSG"; cat "$TMP/stream.out"
  # 코드는 라우터가 빈 구조화 출력을 어떻게 분류하느냐에 따라 LLM_OUTPUT_INVALID 또는 UNEXPECTED_ERROR (handoff/api.md 요청 1)
  check "$TMP/events.json" 'd[-1]["type"] == "ErrorRaised" and d[-1]["error"]["code"] in ("LLM_OUTPUT_INVALID", "UNEXPECTED_ERROR")' "ErrorRaised 이벤트"
  step "pending 없음 → resume 409"
  [ "$(http "$URL/chat/pending?thread_id=smoke-1")" = 200 ] || die "pending"; check "$TMP/body.json" 'd["pending"] is None' "pending은 null이어야 함"
  [ "$(http -X POST "$URL/chat/resume" -H 'content-type: application/json' -d '{"thread_id":"smoke-1","approve":true}')" = 409 ] || die "resume은 409여야 함"
  check "$TMP/body.json" 'd["error"]["code"] == "NO_PENDING"' "NO_PENDING 본문"
  echo "ok"; echo; echo "SMOKE OK (fake)"; exit 0
fi

step "SSE: ollama로 카드 생성 → 승인 대기까지 (최대 ${SMOKE_TRIES:-3}번 시도)"
for i in $(seq "${SMOKE_TRIES:-3}"); do
  stream smoke-1 "$MSG"; cat "$TMP/stream.out"
  check "$TMP/events.json" 'd[-1]["type"] in ("ApprovalRequired", "ErrorRaised")' "스트림이 승인 대기나 오류로 끝나야 함"
  "$PY" -c 'import json,sys; sys.exit(0 if json.load(open(sys.argv[1]))[-1]["type"]=="ApprovalRequired" else 1)' "$TMP/events.json" && break
  echo "시도 $i: 승인 대기에 못 갔다 (소형 모델의 구조화 출력 실패일 수 있음)"
  [ -f "$TMP/server.log" ] && grep 'trace_id=' "$TMP/server.log" | tail -1 | cut -c1-240 || true   # 서버 로그의 내부 원인
done
check "$TMP/events.json" 'd[-1]["type"] == "ApprovalRequired" and d[0]["type"] == "RouteDecided"' "승인 대기에 도달하지 못함"
step "pending → resume(승인) → 카드 저장"
[ "$(http "$URL/chat/pending?thread_id=smoke-1")" = 200 ] || die "pending"; check "$TMP/body.json" 'd["pending"]["card"]["formal_expression"]' "pending 카드"
[ "$(http -X POST "$URL/chat/resume" -H 'content-type: application/json' -d '{"thread_id":"smoke-1","approve":true}')" = 200 ] || die "resume"
check "$TMP/body.json" 'd["saved"] is True and d["card_id"] == "C0001" and d["next_review"]' "저장 결과"
[ "$(http "$URL/api/cards")" = 200 ] || die "cards"; check "$TMP/body.json" 'len(d) == 1 and d[0]["id"] == "C0001"' "저장된 카드"
[ "$(http "$URL/chat/pending?thread_id=smoke-1")" = 200 ] || die "pending"; check "$TMP/body.json" 'd["pending"] is None' "승인 뒤 pending은 null"
[ "$(http -X POST "$URL/chat/resume" -H 'content-type: application/json' -d '{"thread_id":"smoke-1","approve":true}')" = 409 ] || die "이미 처리된 resume은 409여야 함"
echo "ok"; echo; echo "SMOKE OK (ollama)"
