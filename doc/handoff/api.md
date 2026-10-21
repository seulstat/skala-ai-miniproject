# api 인수인계 — 2026-10-21 (CP2 대상)

## 한 일
`server.py`(:8100)와 라우터 3개·서비스 3개를 완성했다. 라우트는 `contracts.api.ROUTES` 14개 전부다(테스트가 대조). 테스트는 fake LLM·fake MCP·tmp_path만 써서 58개이고,
design §6 테스트 8·9·11과 "서버를 재시작해도 `/chat/pending`이 승인 대기를 돌려준다"(같은 `checkpoints.db`로 앱 2번)를 포함한다.

- **lifespan**: `build_deps()`로 Deps를 1회 조립하고 `build_graph()`를 1회 빌드해 `app.state`에 둔다. 라우터는 `Depends(get_deps/get_graph/get_thread_locks)`로 받는다(전역 싱글턴 없음).
  종료는 MCP `stop()` → 체크포인터 연결 close → LangSmith flush 순이고, 하나가 실패해도 로그를 남기고 나머지를 계속한다. MCP start(`build_deps` 안)와 stop은 같은 lifespan 함수 안이다(mcp.md 요청 3).
  `.env`는 기본 팩토리일 때만 lifespan 시작에서 읽는다(import 시점이 아니라서 테스트가 개발자 `.env`의 ollama·LangSmith 설정을 끌어오지 않는다).
- **오류(ADR-0012)**: `CoachError` → `ErrorResponse` + `ERROR_CATALOG[code].http_status`, `RequestValidationError` → 422 `INPUT_INVALID`, 그 외 → 500 `UNEXPECTED_ERROR`.
  SSE에서는 같은 변환을 `ErrorRaised → [DONE]`으로 한다. 내부 원인은 `LOG_FIELDS` 순서의 한 줄 로그(+`trace_id`)에만 남고 응답에는 `user_message`뿐이다.
- **setup**: 프로필(GET 없으면 404 `NOT_FOUND`, PUT 잘못된 enum 422), 문서(GET·POST·DELETE, `.md`·경로 구분자 불가·심볼릭 링크 탈출 불가), 공고 정리(`quality_llm` + 10/13 프롬프트, 이미 `## 주요 업무`·`## 자격 요건`이 있으면 LLM 생략), 공고 저장, 준비 점검.
- **chat**: `/chat/stream`은 readiness로 `NOT_READY`를 먼저 검사한 뒤 `graph.astream(stream_mode="custom")`을 `to_sse`로 보낸다. `/chat/resume`은 `thread_id`별 락 안에서 처리한다. `/chat/pending`은 `aget_state().interrupts`다.
- **cards**: 목록·오늘 복습·복습 결과(P1). 없는 id는 `CardStore`가 올린 `NOT_FOUND` → 404.
- **스모크**: `sh/smoke_chat.sh fake|ollama`. 임시 데이터 폴더로 서버를 직접 띄우고 정리한다.
- **Proposed ADR 2개**: 0017(API가 그래프를 구동하는 규칙), 0018(빈 구조화 출력 분류 — **A1 수정 요청**). 번호는 A4의 0016과 겹치지 않게 0017부터 썼다.

## 실행 방법·curl 예시
```bash
bash sh/setup_venv.sh                          # worktree마다 1회
bash sh/seed_sample.sh                         # examples/sample_user → COACH_DATA_DIR (.env 없으면 ./data)
.venv/bin/python server.py                     # :8100  (또는 uvicorn server:app --port 8100)
bash sh/smoke_chat.sh fake                     # 서버를 임시 데이터로 띄워 REST + ErrorRaised 경로 확인 (네트워크 불필요)
bash sh/smoke_chat.sh ollama                   # ollama serve 필요. 승인 → 저장까지. SMOKE_TRIES=5로 시도 횟수를 늘릴 수 있다
.venv/bin/python -m pytest tests/test_api_*.py # API 테스트만
```
```bash
B=http://127.0.0.1:8100
curl -s $B/api/readiness                                                    # {"ready":true,"items":[프로필·경험 문서·공고·개인정보]}
curl -s $B/api/profile                                                      # 없으면 404 {"error":{"code":"NOT_FOUND",...}}
curl -s -X PUT $B/api/profile -H 'content-type: application/json' -d @examples/sample_user/profile.json
curl -s -X PUT $B/api/profile -H 'content-type: application/json' -d '{"goal":"g","target_role":"r","tone_preference":"아무말"}'   # 422 INPUT_INVALID
curl -s -X POST $B/api/docs -H 'content-type: application/json' -d '{"name":"experience.md","content":"# 활동\n배송 지연을 분석해 민원을 400건에서 260건으로 줄였다."}'
curl -s $B/api/docs ; curl -s -X DELETE "$B/api/docs/experience.md"
curl -s -X POST $B/api/posting/normalize -H 'content-type: application/json' -d '{"text":"데이터 분석가 채용 ..."}'   # → PostingDraft
curl -s -X PUT $B/api/posting -H 'content-type: application/json' -d '{"markdown":"## 주요 업무\n- 분석\n\n## 자격 요건\n- SQL"}'
curl -N -G $B/chat/stream --data-urlencode 'message=배송 지연 원인을 분석해 민원을 줄였다고 말하고 싶어' --data-urlencode 'thread_id=demo'   # SSE → ... → data: [DONE]
curl -s "$B/chat/pending?thread_id=demo"                                    # {"thread_id":"demo","pending":{card,...}|null}
curl -s -X POST $B/chat/resume -H 'content-type: application/json' -d '{"thread_id":"demo","approve":true}'   # {"saved":true,"card_id":"C0001","next_review":"..."}  대기 없음 → 409 NO_PENDING
curl -s $B/api/cards ; curl -s $B/api/cards/due
curl -s -X POST $B/api/cards/C0001/review -H 'content-type: application/json' -d '{"result":"known"}'   # 없는 id → 404 NOT_FOUND
```

## 파일·함수 위치
| 파일 | 함수/클래스 | 역할 |
|---|---|---|
| `server.py` | `create_app(deps_factory)`, `app`, `_shutdown`, `_error_response` | lifespan(Deps·graph 1회, 종료 정리), 오류 핸들러 3종. `app = create_app()`는 import 시 모델·DB를 만들지 않는다 |
| `routers/dependencies.py` | `get_deps`·`get_graph`·`get_thread_locks` | `app.state`에서 꺼내는 Depends |
| `routers/setup.py` | `get_profile`·`put_profile`, `list_docs`·`add_doc`·`delete_doc`, `normalize`·`save_posting`, `readiness`, `_doc_path` | 파일은 `deps.paths`만, 동기 I/O는 `to_thread` |
| `routers/chat.py` | `stream`·`_event_stream`, `resume`, `pending`, `FRESH_TURN` | SSE·승인 재개·승인 대기 조회 (ADR-0006·0017) |
| `routers/cards.py` | `list_cards`·`due_cards`·`review_card` | `deps.store` 호출 |
| `services/readiness.py` | `check_readiness`(async)·`check_readiness_sync` | 10/13 `check_inputs.py` 이식, 항목당 한 줄 |
| `services/posting.py` | `normalize_posting`, `parse_sections`, `missing_required` | 10/13 `ingest_posting.py` 프롬프트 이식, `<think>`·코드펜스 제거 |
| `services/errors.py` | `report_error`, `http_status`, `as_coach_error` | 예외 → `ErrorInfo`(+`trace_id`) + `LOG_FIELDS` 로그 |
| `sh/smoke_chat.sh` | | curl 스모크 (fake: ErrorRaised·REST, ollama: 승인 → 저장) |
| `tests/test_api_support.py` | `FakeMCP`, `deps_factory`, `running_app`, `sse_events` | 테스트 공용 도구(테스트 없음). conftest.py가 Lead 소유라 여기에 둔다 |
| `tests/test_api_setup.py` | | **테스트 8**(필수 누락·`★`·개인정보 패턴), **테스트 9**(프로필 enum 422) |
| `tests/test_api_chat.py` | | **테스트 11**(`NOT_READY` 불가·`LLM_OUTPUT_INVALID` 재시도 가능·`UNEXPECTED_ERROR` 원인 비노출, 대기 없음 409), 정상 경로 |
| `tests/test_api_chat_state.py` | | 재시작 후 pending 복원, 저장 실패 재시도, 동시 승인, 같은 thread의 새 메시지 |
| `tests/test_api_docs.py`·`test_api_cards.py`·`test_api_app.py`·`test_api_lifespan.py` | | 문서·공고, 카드, 라우트 표·오류 매핑(카탈로그 전 코드)·종료 정리, 실제 MCP 조립 |

## 관련 ADR
[0005](../adr/0005-async-nodes.md)(async, 파일 I/O `to_thread`) · [0006](../adr/0006-hitl-json-resume-pending.md)(resume JSON·pending) · [0007](../adr/0007-upload-filereader-json.md)(문서 JSON 업로드) ·
[0011](../adr/0011-deps-in-contracts.md)(Deps·`paths`) · [0012](../adr/0012-error-handling-4layer.md)(오류 변환) · [0014](../adr/0014-explicit-writer-for-nested-subgraphs.md)(`astream(custom)` 그대로 사용).
Proposed: [0017](../adr/0017-api-drives-graph-turn-reset-lock-retry.md)(새 턴 입력 초기화·승인 직렬화·저장 재시도), [0018](../adr/0018-empty-structured-output-is-llm-output-invalid.md)(빈 구조화 출력 → `LLM_OUTPUT_INVALID`, A1 요청).

## 사용한 계약 (contracts/)
`api.py`(ROUTES·요청/응답 모델·`ErrorResponse`), `events.py`(`to_sse`·`parse_event`·`SSE_DONE`·`SSE_HEADERS`·`ErrorRaised`), `errors.py`(`ERROR_CATALOG`·`CoachError`·`error_info`·`LOG_FIELDS`),
`deps.py`(`Deps`·`DataPaths`), `schemas.py`(`UserProfile`·`PostingDraft`·`ApprovalRequest`·`SavedCard`), `state.py`(`ResumeValue`·`NODE_SAVE`), `fixtures/`(테스트). 계약은 고치지 않았다.

## 테스트 결과 (check.sh, 자기 테스트)
```
bash check.sh
check.sh — branch=feat/api role=api python=Python 3.11.15

[① ruff]
  PASS ruff

[② pytest (계약 테스트 제외)]
........................................................................ [ 54%]
...........................................................              [100%]
131 passed in 14.87s
  PASS pytest (rc=0, 5=수집된 테스트 없음)

[③ 계약 테스트]
43 passed in 0.12s
  PASS tests/test_contracts.py

[④ 금지 파일·패턴]
  PASS 커밋 대상에 .env·data/·*.db·private/ 없음
  PASS 전화번호·주민번호 패턴 없음
  PASS 고유명사 목록(.forbidden_patterns.local) 미검출

[⑤ 소유권 (main 대비 변경 경로)]
  PASS 변경 20개 모두 허용 경로

[⑥ 파일 길이 (>200줄 경고)]
  PASS 200줄 초과 없음

[⑦ 커밋 메시지 (형식, AI 이름 금지)]
  PASS AI 이름·Co-Authored-By 없음
  PASS 형식 [role] 요약

[⑧ ADR]
  PASS ADR 17개 필수 제목 4개
doc/adr/0017-api-drives-graph-turn-reset-lock-retry.md
doc/adr/0018-empty-structured-output-is-llm-output-invalid.md
  WARN 색인 미등록 ADR — Lead가 CP에서 등록
  PASS contracts·requirements 변경 커밋에 ADR 번호 있음

== 결과: FAIL 0 · WARN 1 ==
check.sh 통과
```
pytest 131개 = 기존 73(core 20 + mcp 52 + 통합 1) + API 58. `.venv/bin/python -m pytest tests/test_api_*.py`: 58 passed (약 2초, 실제 MCP를 띄우는 `test_api_lifespan.py` 1개 포함).
핵심 동작을 일부러 망가뜨려 테스트가 실패하는지 확인했다(15곳: `FRESH_TURN`·승인 락·저장 재시도·`NOT_READY` 검사·`SSE_HEADERS`·`[DONE]`·`NO_PENDING`·원인 노출·이메일 패턴·`ready` 판정·MCP stop·체크포인터 close·422 매핑·문서 경로 확인·복습 결과 무시). 처음에는 문서 경로 확인(심볼릭 링크 탈출) 1곳만 못 잡았고 테스트를 추가해 잡게 했다. 체크포인터 close를 빼면 aiosqlite 스레드가 남아 pytest 프로세스가 종료되지 않는다.
`bash sh/smoke_chat.sh fake`: SMOKE OK. `bash sh/smoke_chat.sh ollama`(qwen3:0.6b·qwen3:8b, 임베딩 fake): 2회 실행 중 1회 SMOKE OK(3번째 시도에서 승인 대기 → resume 저장 `C0001` → 이중 resume 409), 1회 FAIL(3번 모두 Coach 구조화 출력 `None`) — 한계 1 참고.
실제 프로세스: `.venv/bin/python server.py`로 기동 → `/api/readiness` 응답 → SIGINT로 정상 종료, MCP subprocess가 남지 않는 것을 확인했다.

## 알려진 한계·미완료
1. **ollama Coach 구조화 출력 실패가 잦다** (ADR-0018). `qwen3:8b`로 `sh/smoke_chat.sh ollama`를 2번(시도 6번) 돌려 승인 대기까지 간 것은 1번뿐이다. 나머지 5번은 Coach가 `structured_response=None`을 돌려줘 `agent/graph.py::_coach`의 `.model_dump()`에서
   `AttributeError`가 났고 `UNEXPECTED_ERROR`(재시도 불가)로 표시된다. 스모크는 이 경우 `FAIL: 승인 대기에 도달하지 못함`으로 끝난다(시도 횟수로 가리지 않는다). 승인 → 저장 정상 경로는 성공한 1번에서 확인했다.
2. **fake 모델의 코드**: 작업 지시서는 `LLM_OUTPUT_INVALID`를 기대했지만 `_router`가 `route.intent`를 `None`에 호출해 `UNEXPECTED_ERROR`가 나간다(ADR-0018). `sh/smoke_chat.sh fake`는 두 코드를 모두 허용한다. 테스트 11의 `LLM_OUTPUT_INVALID`는 스키마를 어긴 Route 출력으로 만들었다.
3. **ollama 스모크는 `EMBEDDING_MODEL=fake`로 돌렸다.** `nomic-embed-text`가 이 머신에 없다(`ollama pull` 필요). 실제 임베딩 검색 품질은 확인하지 못했다. 스크립트는 모델이 있으면 자동으로 쓴다.
4. 새 메시지를 보내면 같은 thread의 **이전 승인 대기가 새 카드로 대체**된다(경고 없음). 저장 실패(`STORE_ERROR`) 상태에서는 `/chat/pending`이 `null`이라 새로고침하면 승인 화면이 사라진다(resume 재시도는 가능, ADR-0017).
5. `trace_id`는 서버가 만드는 무작위 12자리이고 로그와 짝이다. LangSmith run id가 아니다.
6. 준비 점검은 10/13과 다르게 항목당 한 줄로 묶었고, API 키 점검은 뺐으며(모델 설정은 provider마다 다르다), "(공고에 명시 없음)"뿐인 섹션은 없는 섹션으로 센다. 개인정보 항목은 항상 `warn`이다(`fixtures/readiness.json`과 같음).
7. 시작할 때 MCP 서버를 못 띄우면(`MCP_UNAVAILABLE`) 서버 프로세스가 기동에 실패한다. 요청별 복구나 재연결은 없다(mcp.md 한계 2).
8. 업로드 크기 제한이 없다(단일 사용자 전제, ADR-0008). `/chat/stream`은 같은 thread의 동시 요청을 막지 않는다(resume만 직렬화).
9. FastAPI 0.150은 `include_router`가 지연 포함이라 `app.routes`에 개별 라우트가 보이지 않는다. 라우트 표 검사는 `app.openapi()["paths"]`로 한다.

## Lead·다른 역할에 대한 요청
1. **Lead → A1 (ADR-0018)**: `_router`의 `route.intent`와 `_coach`의 `result["structured_response"].model_dump()`가 `None`이면 `CoachError("LLM_OUTPUT_INVALID")`를 올리게 해 주세요. 반영되면 A3 변경은 없고
   `sh/smoke_chat.sh`의 fake 허용 코드를 `LLM_OUTPUT_INVALID` 하나로 좁히면 됩니다. 그와 별개로 `qwen3:8b` Coach의 구조화 출력 성공률(1/6)이 CP2 기준("ollama 승인 → 저장")의 걸림돌이라, 모델·프롬프트·`ToolStrategy` 설정 조정을 검토해 주세요.
2. **Lead (ADR-0017)**: 새 턴 입력 초기화(`FRESH_TURN`)는 A1의 `_router`가 `review`·`warning`을 비우면 더 근본적입니다. 반영되면 `routers/chat.py`의 `FRESH_TURN`을 지우겠습니다.
3. **Lead**: ADR 0017·0018 색인 등록과 번호 확정(A4의 0016 다음). 이 worktree에는 0016 파일이 아직 없어 0017부터 썼습니다.
4. **Lead**: `ollama pull nomic-embed-text` 후 `EMBEDDING_MODEL=ollama:nomic-embed-text`로 `bash sh/smoke_chat.sh ollama`를 다시 돌려 실제 검색까지 확인해 주세요(mcp.md 요청 4와 같은 항목).
5. **A4**: ① 새 메시지는 같은 thread의 승인 대기를 대체한다. ② `EventSource`는 `[DONE]`을 받으면 직접 `close()`해야 한다(자동 재연결하면 같은 메시지로 그래프를 다시 돌린다). ③ `STORE_ERROR`(recoverable)는 같은 `POST /chat/resume`을 다시 보내면 저장만 재시도된다.
   ④ 오류 본문은 `{"error":{code,layer,recoverable,fatal,user_message,trace_id}}`뿐이고 필드별 검증 메시지는 없다(422 `INPUT_INVALID`).
6. **환경 메모**: 세션 시작 직후 이 worktree에서 `.env.example`이 작업 트리에서만 삭제돼 있어 check.sh ⑤가 FAIL이었다(내가 지운 것이 아니고, 커밋된 내용 그대로 `git checkout -- .env.example`로 복원했다). 원인은 모른다.

## 발표 때 설명할 포인트 (3줄)
- DI·수명 관리: `Deps`와 그래프를 lifespan에서 1회 조립해 `app.state`에 두고 라우터는 `Depends`로만 받는다. MCP start/stop을 같은 lifespan 함수 안에 둬 anyio cancel scope 문제를 피하고, 종료 정리는 하나가 실패해도 나머지를 계속한다.
- 오류의 4번째 계층: 분류된 오류는 카탈로그의 상태·문구로, 미분류 예외는 `UNEXPECTED_ERROR`로 바꿔 화면에는 `user_message`뿐 보내고 내부 원인은 `trace_id`와 함께 `LOG_FIELDS` 로그에만 남긴다. SSE는 `ErrorRaised → [DONE]`으로, REST는 `ErrorResponse`로 같은 규칙을 쓴다.
- HITL 영속성: 승인 대기는 체크포인터에 있어 서버를 다시 띄워도 `/chat/pending`이 같은 카드를 돌려준다(같은 `checkpoints.db`로 앱 2번 띄우는 테스트). 승인 연타·저장 실패 재시도·같은 thread의 이전 경고 누수까지 실측해서 막았다.
