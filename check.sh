#!/usr/bin/env bash
# 공용 점검 스크립트 (Lead 소유). 작업 전·후와 CP 판정에 쓴다. 실패 항목이 하나라도 있으면 exit 1.
#   bash check.sh            모든 항목
#   CHECK_SKIP_TESTS=1 bash check.sh   pytest 생략 (빠른 확인용, CP 판정에는 쓰지 않음)
# 역할은 브랜치 이름으로 판별한다: main=lead, feat/core|mcp|api|web=해당 역할 (agent.md §2).
set -uo pipefail
cd "$(dirname "$0")"

# ADR 검사(⑧) 활성 여부. Phase 0 M5에서 ADR 0001~0011 작성 후 활성화했다.
ADR_CHECK_ENABLED=1
MAX_LINES=200

PY=.venv/bin/python; [ -x "$PY" ] || PY=python3
FAILS=(); WARNS=()
pass() { printf '  \033[32mPASS\033[0m %s\n' "$1"; }
fail() { printf '  \033[31mFAIL\033[0m %s\n' "$1"; FAILS+=("$1"); }
warn() { printf '  \033[33mWARN\033[0m %s\n' "$1"; WARNS+=("$1"); }
section() { printf '\n[%s]\n' "$1"; }

BRANCH=$(git branch --show-current 2>/dev/null || echo "")
case "$BRANCH" in
  main) ROLE=lead ;;
  feat/core|feat/mcp|feat/api|feat/web) ROLE=${BRANCH#feat/} ;;
  *) ROLE=unknown ;;
esac
echo "check.sh — branch=${BRANCH:-?} role=$ROLE python=$($PY --version 2>&1)"

# 커밋될 수 있는 파일 = 추적 중 + 무시되지 않은 새 파일
FILES=$(git ls-files --cached --others --exclude-standard | sort -u)

section "① ruff"
if out=$($PY -m ruff check . --output-format concise 2>&1); then pass "ruff"; else echo "$out" | tail -20; fail "ruff"; fi

section "② pytest (계약 테스트 제외)"
if [ "${CHECK_SKIP_TESTS:-0}" = 1 ]; then warn "pytest 생략 (CHECK_SKIP_TESTS=1)"
else
  out=$($PY -m pytest --ignore=tests/test_contracts.py 2>&1); rc=$?
  echo "$out" | tail -3
  if [ $rc -eq 0 ] || [ $rc -eq 5 ]; then pass "pytest (rc=$rc, 5=수집된 테스트 없음)"; else fail "pytest"; fi
fi

section "③ 계약 테스트"
out=$($PY -m pytest tests/test_contracts.py 2>&1); rc=$?
echo "$out" | tail -1
[ $rc -eq 0 ] && pass "tests/test_contracts.py" || fail "tests/test_contracts.py"

section "④ 금지 파일·패턴"
bad=$(echo "$FILES" | grep -E '(^|/)\.env$|(^|/)\.env\.[^e]|^data/|\.db$|\.db-|(^|/)private/' || true)
[ -z "$bad" ] && pass "커밋 대상에 .env·data/·*.db·private/ 없음" || { echo "$bad"; fail "금지 파일이 커밋 대상에 있음"; }
# 일반 개인정보 패턴: 휴대전화, 주민등록번호
TEXT_FILES=$(echo "$FILES" | grep -vE '^ref/|\.(png|jpg|pdf|ipynb)$' | while read -r f; do [ -f "$f" ] && echo "$f"; done)
pii=$(echo "$TEXT_FILES" | xargs grep -nE '01[016789]-?[0-9]{3,4}-?[0-9]{4}|[0-9]{6}-[1-4][0-9]{6}' 2>/dev/null | grep -v '^check.sh:' || true)
[ -z "$pii" ] && pass "전화번호·주민번호 패턴 없음" || { echo "$pii" | head -5; fail "개인정보 패턴 발견"; }
# 실제 서류 고유명사: .forbidden_patterns.local (gitignore, 한 줄에 정규식 하나). worktree에서는 main 작업 트리의 파일을 쓴다
FPL=.forbidden_patterns.local
[ -f "$FPL" ] || FPL="$(cd "$(git rev-parse --git-common-dir)/.." && pwd)/.forbidden_patterns.local"
if [ -f "$FPL" ]; then
  hits=$(echo "$TEXT_FILES" | xargs grep -nEf <(grep -vE '^\s*(#|$)' "$FPL") 2>/dev/null || true)
  [ -z "$hits" ] && pass "고유명사 목록(.forbidden_patterns.local) 미검출" || { echo "$hits" | cut -c1-120 | head -5; fail "실제 서류 고유명사 발견"; }
else
  warn ".forbidden_patterns.local 없음 — 실제 서류 고유명사 검사 생략"
fi

section "⑤ 소유권 (main 대비 변경 경로)"
allowed_for() {   # 역할별 허용 경로 정규식 (agent.md §2)
  local common="^doc/handoff/$1\\.md$"
  case "$1" in
    core) echo "^agent/|^tests/test_core_[^/]*\\.py$|$common" ;;
    mcp)  echo "^mcp_server\\.py$|^rag\\.py$|^agent/mcp_client\\.py$|^templates/|^tests/test_mcp_[^/]*\\.py$|$common" ;;
    api)  echo "^server\\.py$|^routers/|^services/|^tests/test_api_[^/]*\\.py$|^sh/smoke_[^/]*\\.sh$|$common" ;;
    web)  echo "^web/|^web_server\\.py$|$common" ;;
  esac
}
if [ "$ROLE" = lead ]; then pass "main(Lead) — 검사 생략 (병합 지점)"
elif [ "$ROLE" = unknown ]; then warn "역할을 알 수 없는 브랜치 '$BRANCH' — 검사 생략"
else
  re=$(allowed_for "$ROLE")
  changed=$( { git diff --name-only main...HEAD; git diff --name-only HEAD; git ls-files --others --exclude-standard; } | sort -u)
  added=$( { git diff --name-only --diff-filter=A main...HEAD; git diff --name-only --diff-filter=A HEAD; git ls-files --others --exclude-standard; } | sort -u)
  viol=""
  for f in $changed; do
    [ "$ROLE" = core ] && [ "$f" = agent/mcp_client.py ] && { viol+="$f"$'\n'; continue; }
    echo "$f" | grep -qE "$re" && continue
    # 새 ADR 파일(Proposed) 추가는 모든 역할 허용, 기존 ADR·색인 수정은 Lead만
    if echo "$f" | grep -qE '^doc/adr/[0-9]{4}-[^/]+\.md$' && echo "$added" | grep -qxF "$f"; then continue; fi
    viol+="$f"$'\n'
  done
  [ -z "$viol" ] && pass "변경 $(echo "$changed" | grep -c .)개 모두 허용 경로" || { printf '%s' "$viol"; fail "허용 경로 밖 변경 ($ROLE)"; }
fi

section "⑥ 파일 길이 (>${MAX_LINES}줄 경고)"
long=$(echo "$TEXT_FILES" | grep -E '\.(py|js|html|vue|css)$' | grep -vE '^(contracts/fixtures|eval/v1)/' \
  | while read -r f; do n=$(wc -l < "$f"); [ "$n" -gt $MAX_LINES ] && echo "$f ($n줄)"; done)
[ -z "$long" ] && pass "200줄 초과 없음" || { echo "$long"; warn "200줄 초과 파일 — 분리 검토"; }

section "⑦ 커밋 메시지 (형식, AI 이름 금지)"
RANGE=HEAD; [ "$ROLE" != lead ] && [ "$ROLE" != unknown ] && RANGE="main..HEAD"
ai=$(git log "$RANGE" --format='%h %B' 2>/dev/null | grep -inE 'claude|anthropic|co-authored-by|generated with' || true)
[ -z "$ai" ] && pass "AI 이름·Co-Authored-By 없음" || { echo "$ai" | head -5; fail "커밋 메시지에 AI 표기"; }
badfmt=$(git log "$RANGE" --format='%h %s' 2>/dev/null | grep -vE '^[0-9a-f]+ (\[(lead|core|mcp|api|web)\] |Merge |WIP: )' || true)
[ -z "$badfmt" ] && pass "형식 [role] 요약" || { echo "$badfmt" | head -5; fail "커밋 형식 위반"; }

section "⑧ ADR"
if [ "$ADR_CHECK_ENABLED" != 1 ]; then warn "ADR 검사 비활성 (Phase 0 M5 완료 전)"
else
  adrs=$(ls doc/adr/[0-9][0-9][0-9][0-9]-*.md 2>/dev/null)
  miss=""; noidx=""
  for f in $adrs; do
    for h in "## 배경" "## 결정" "## 대안 비교" "## 결과"; do grep -qxF "$h" "$f" || miss+="$f: '$h' 없음"$'\n'; done
    num=$(basename "$f" | cut -c1-4)
    grep -qE "^\| *(\[)?$num" doc/adr/README.md 2>/dev/null || noidx+="$f"$'\n'
  done
  [ -z "$miss" ] && pass "ADR $(echo "$adrs" | grep -c .)개 필수 제목 4개" || { printf '%s' "$miss"; fail "ADR 필수 제목 누락"; }
  if [ -z "$noidx" ]; then pass "색인 누락 없음"
  elif [ "$ROLE" = lead ]; then printf '%s' "$noidx"; fail "ADR 색인 누락 (doc/adr/README.md)"
  else printf '%s' "$noidx"; warn "색인 미등록 ADR — Lead가 CP에서 등록"; fi
  nolink=""
  for c in $(git rev-list "$RANGE" 2>/dev/null); do
    git diff-tree --root --no-commit-id --name-only -r "$c" | grep -qE '^contracts/|^requirements\.txt$' || continue
    git log -1 --format=%B "$c" | grep -qE 'ADR-[0-9]{4}' || nolink+="$(git log -1 --format='%h %s' "$c")"$'\n'
  done
  [ -z "$nolink" ] && pass "contracts·requirements 변경 커밋에 ADR 번호 있음" || { printf '%s' "$nolink"; fail "ADR 번호 없는 계약·의존성 변경 커밋"; }
fi

printf '\n== 결과: FAIL %d · WARN %d ==\n' "${#FAILS[@]}" "${#WARNS[@]}"
for f in "${FAILS[@]+"${FAILS[@]}"}"; do echo "  FAIL: $f"; done
[ ${#FAILS[@]} -eq 0 ] && { echo "check.sh 통과"; exit 0; } || { echo "check.sh 실패"; exit 1; }
