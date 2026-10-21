# web 인수인계 — 2026-10-21 (CP3 대상)

## 한 일
탭 3개 P0 화면 전부와 P1 복습 퀴즈, `web_server.py`(정적 서빙 + 프록시 + MOCK)를 만들었다. 백엔드 없이 `MOCK=1`로
design §4 화면 전부와 `sse_*.json` 8종 재생, pending 복원, resume 응답, `error_response` 표시를 확인했다.
실제 백엔드(A3)가 아직 없어 **프록시 경로는 가짜 백엔드(MOCK 라우터를 :8190에 띄운 것)로** 같은 시나리오를 다시 돌려 확인했다.
실제 `server.py`와의 연결은 CP2 이후 Lead가 확인한다.

- ① 준비: 점검 체크리스트(필수 3 + 개인정보 경고·안내), 프로필 폼, `.md` 업로드(FileReader→JSON)·목록·삭제, 공고 붙여넣기/업로드 → 6개 섹션 정리 → 수정(섹션 누락 실시간 표시) → 저장
- ② 코치: 채팅 + 예시 칩, 진행 타임라인(분류→근거 검색→초안→검수 위반→재작성), 카드(Formal/Casual·핵심 표현·근거 칩·답변 초안), 경고 배너(`warning`·남은 위반·`notices`), 승인·거절, 새로고침 복원
- ③ 카드: 목록·다음 복습일·단계, 카드 펼치기, 오늘 복습 플립 퀴즈(안다/다시)
- 오류 화면(ADR-0012): `ErrorRaised`·REST `ErrorResponse`는 `user_message` 표시, `recoverable`이면 "다시 시도", `NOT_READY`면 "준비 탭으로 이동", `EvidenceSearched.error`는 타임라인에 ✕, `ApprovalRequired.notices`는 카드 위 배너, SSE가 끊기면 `/chat/pending` 확인
- 프록시: httpx 스트리밍으로 SSE를 버퍼링 없이 중계, `SSE_HEADERS` 전달

## 실행 방법
```bash
MOCK=1 .venv/bin/python web_server.py            # http://localhost:8600 (백엔드 불필요)
.venv/bin/python web_server.py                   # 실제 백엔드 server.py(:8100)로 프록시
```
| 환경변수 | 기본값 | 뜻 |
|---|---|---|
| `MOCK` | 없음 | `1`이면 `contracts/fixtures`로 응답 (`web/mock_backend.py`) |
| `MOCK_DELAY` | `0.5` | MOCK SSE 이벤트 사이 간격(초) |
| `BACKEND_URL` | `http://127.0.0.1:8100` | 프록시 대상 |
| `WEB_PORT` | `8600` | 웹 서버 포트. 127.0.0.1에만 바인딩한다 (개인 서류 보호) |

**주의 — 포트 충돌**: 이 머신에는 10/20부터 Base 데모 프로세스(`all_total_vue_student`의 `server.py`가 :8100, `web_demo_server.py`가 :8600)가 떠 있다.
둘을 끄지 않으면 실제 A3 서버와 이 웹 서버가 같은 포트를 쓰려 하고, 프록시가 엉뚱한 Base 서버로 연결될 수 있다. 검증은 :8610·:8611·:8190에서 했다.

### MOCK 시나리오 (코치 탭의 "MOCK 시나리오" 칩 = 메시지 끝 `#태그`)
| 칩 / 메시지 | fixture | 확인할 화면 |
|---|---|---|
| 예시 칩 1 (한국어 문장) | `sse_express_approve` | 검수 위반 2건 → 재작성 → 승인 대기 → 승인하면 카드 저장 |
| 예시 칩 2 (영어 질문) | `sse_answer_approve` | 답변 초안 포함 카드 |
| 예시 칩 3 (`복습`) | `sse_review` | `FinalAnswer` 말풍선 |
| 범위 밖 `#oos` | `sse_out_of_scope` | `FinalAnswer` 말풍선 |
| 검수 미통과 경고 `#warning` | `sse_express_warning` | 경고 배너(+남은 위반), 검수 3회 ! 표시 |
| 근거 검색 일부 실패 `#degraded` | `sse_evidence_degraded` | 타임라인 ✕ + 카드 위 알림 배너 |
| 복구 가능 오류 `#error` | `sse_error_recoverable` | 오류 상자 + "다시 시도" (두 번째는 성공) |
| 준비 미완료 `#notready` | `sse_error_not_ready` | "준비 탭으로 이동" 버튼 (다시 시도 없음) |
| 연결 끊김(승인 대기 있음) `#disconnect` | `sse_express_approve`를 ApprovalRequired 앞에서 끊음 | 끊김 후 `/chat/pending`으로 승인 카드 복구 |
| 연결 끊김(대기 없음) `#drop` | 같은 fixture를 2번째 이벤트에서 끊음 | `STREAM_DISCONNECTED` + 다시 시도 (두 번째는 성공) |

그 밖의 시연 방법: 승인 대기 상태에서 새로고침 → 복원 / `http://localhost:8600/?thread_id=demo-thread-1` → `pending.json` 복원 /
같은 대화를 탭 두 개로 열어 한쪽에서 먼저 승인하면 다른 쪽이 `resume` 409(`error_response.json`, NO_PENDING)를 표시한다.

## 화면 캡처 (`web/captures/`, MOCK 모드 · 가상 fixture 데이터)
| 파일 | 화면 |
|---|---|
| `01a-prepare-checklist-profile.png` · `01b-prepare-docs-posting.png` | ① 준비 (점검·개인정보 경고·프로필 / 문서·공고 정리) |
| `02-coach-express-approval.png` | ② 코치: 타임라인(위반→재작성) + 카드 + 승인·거절 |
| `03-coach-answer-draft.png` | answer 모드 답변 초안 |
| `04-coach-warning-banner.png` | 검수 미통과 경고 배너 |
| `05-coach-degraded.png` | 근거 검색 일부 실패(✕) + 알림 배너 |
| `06-error-recoverable.png` · `07-error-not-ready.png` | 오류 상자: 다시 시도 / 준비 탭 이동 |
| `08-pending-restore.png` | 새로고침 후 승인 대기 복원 |
| `09-error-no-pending.png` | `resume` 409 NO_PENDING |
| `10-cards.png` · `11-quiz-front.png` · `12-quiz-back.png` | ③ 카드 목록·다음 복습일 / 퀴즈 앞면·뒷면 |
| `13-mobile-coach.png` | 모바일 폭(390px) |
| `14-error-backend-down.png` | 백엔드가 꺼져 있을 때 (프록시 502) |

## 파일·함수 위치
| 파일 | 함수/클래스 | 역할 |
|---|---|---|
| `web_server.py` | `create_app`, `proxy`, `WebFiles`, `lifespan` | 정적 서빙, `/api/*`·`/chat/*` 프록시(SSE 무버퍼), MOCK 전환 |
| `web/mock_backend.py` | `create_mock_router` | `ROUTES` 14개 전부를 fixture로 응답, SSE 재생, 승인 대기·카드 상태(메모리) |
| `web/mock_scenarios.py` | `SCENARIOS`, `MOCK_CHIPS`, `pick` | `#태그` → fixture 선택 |
| `web/api.js` | `IC.api` (`request`, `streamChat`, `readFile`, `threadId`) | fetch·EventSource 래퍼, 오류 → ErrorInfo 변환 |
| `web/store.js` | `IC.store` | 탭·준비 점검·MOCK 여부 등 공유 상태 |
| `web/coach.js` | `applyEvent`, `useCoach` | SSE 이벤트 → 타임라인·카드, 승인·거절, 복원, 끊김 처리 |
| `web/components/` | `CoachTab`·`TurnView`·`Timeline`·`ExpressionCard`·`ErrorBox` | ② 코치 |
| | `PrepareTab`·`ReadinessList`·`ProfileForm`·`DocManager`·`PostingEditor` | ① 준비 |
| | `CardsTab`·`Quiz` | ③ 카드·복습 |
| `web/index.html`, `web/app.js`, `web/style.css` | | 셸, 앱 마운트, 스타일 (Vue 3.5.13 + SRI 고정) |

## 관련 ADR
- [ADR-0006](../adr/0006-hitl-json-resume-pending.md) — resume JSON, pending 복원 / [ADR-0007](../adr/0007-upload-filereader-json.md) — FileReader → JSON
- [ADR-0008](../adr/0008-single-user-mvp-scope.md) — 개인정보 경고 / [ADR-0012](../adr/0012-error-handling-4layer.md) — 오류 화면
- [ADR-0016 (Proposed)](../adr/0016-web-contract-gaps-rest-bodies-profile-404-proxy-error.md) — 계약 빈틈 4건 확정 요청

## 사용한 계약 (contracts/)
`api.ROUTES`(경로 전부 — MOCK이 `ROUTES`와 핸들러 집합이 같은지 assert), `api.ErrorResponse`·`ResumeResponse`·`PendingResponse` 등,
`events.SSE_DONE`·`SSE_HEADERS`·이벤트 7종, `errors.ERROR_CATALOG`·`error_info`(프록시 오류 응답), `schemas.UserProfile`·`ExpressionCard`·`SavedCard`·`ApprovalRequest`·`REVIEW_INTERVALS_DAYS`, `fixtures.load`.

## 테스트 결과
- `bash check.sh`: FAIL 0 · WARN 1 (신규 Proposed ADR-0016 색인 미등록 — Lead가 등록). ruff·pytest 20·계약 43·파일 길이(200줄 초과 없음) 통과
- 브라우저(Chrome, Playwright) E2E — **MOCK 모드 41/41, 프록시 모드 41/41** (같은 스크립트): 준비 탭 전 기능, `sse_*.json` 8종, 승인·거절, 오류 3종, 끊김 복구, 새로고침 복원, 409, STORE_ERROR 재시도(같은 `approve` 재전송), 422 표시, 카드 목록, 퀴즈, `demo-thread-1`, 모바일 폭 가로 스크롤 없음
- `curl -N`으로 프록시 SSE 도착 시각 확인(이벤트 사이 1초 대기 백엔드): 프록시 경유 20.06 → 21.07 → 22.07 → 23.07초로 하나씩 도착, 백엔드 직접 호출과 같은 간격. 응답 헤더 `cache-control: no-cache`·`x-accel-buffering: no`. 한글·공백 경로(`DELETE /api/docs/...`)의 percent 인코딩과 4xx 상태 코드도 그대로 전달, 백엔드가 꺼지면 `502 + ErrorResponse`
- 이 E2E 스크립트는 커밋하지 않았다 (아래 요청 참고)

## 알려진 한계·미완료
- **실제 `server.py`와는 연결해 보지 못했다** (A3 구현 전). 응답 본문이 계약에 없는 4개 경로와 프로필 미존재 응답은 ADR-0016의 가정대로 구현했다
- 대화 기록은 저장하지 않는다. 새로고침하면 승인 대기 카드만 복원되고 이전 말풍선은 사라진다 (대화 조회 API가 계약에 없음)
- 새 메시지는 승인 대기 중에는 보낼 수 없게 막았다 (승인 대기 중 새 요청의 서버 동작이 계약에 없어서)
- Vue를 CDN(unpkg)에서 받으므로 오프라인에서는 화면이 뜨지 않는다. 필요하면 `web/vendor/`로 내려받아 `<script src>`만 바꾸면 된다
- 공고 원문·수정본은 서버에서 다시 불러오지 못한다 (`GET /api/posting`이 계약에 없음). 저장 후에는 준비 점검의 "공고" 항목으로만 확인한다
- 퀴즈의 "오늘 복습" 대상은 `GET /api/cards/due` 결과다 (날짜 계산은 서버)

## Lead·다른 역할에 대한 요청
- **Lead**: ADR-0016의 4건 확정 (REST 응답 본문, 프로필 미존재 404, 프록시 연결 불가 오류 코드, fixture `FinalAnswer.error` 잔재)
- **Lead**: A4 자동 테스트를 둘 곳이 없다. `check.sh` 소유권 정규식이 `tests/test_web_*.py`를 허용하지 않고, 접두사 규칙도 없다. 허용해 주면 `web_server.py`의 프록시 SSE 무버퍼 테스트와 MOCK 라우터 테스트(httpx `ASGITransport`)를 추가할 수 있다
- **Lead·사용자**: 위 "포트 충돌"의 Base 데모 프로세스(:8100·:8600) 종료. 제가 띄운 프로세스가 아니라 건드리지 않았다
- **A3**: `GET /api/profile` 미존재 시 `404 NOT_FOUND`, `/chat/stream`의 `NOT_READY`는 HTTP 오류가 아니라 SSE `ErrorRaised` → `[DONE]` (EventSource는 오류 본문을 읽지 못한다), `/chat/stream` 응답에 `SSE_HEADERS`

## 발표 때 설명할 포인트 (3줄)
1. 카드는 토큰 스트리밍 대신 **단계 이벤트 타임라인**(분류→근거→초안→검수→재작성)으로 진행을 보여 주고, 승인은 저장 직전에만 받는다 (ADR-0006)
2. 오류는 코드별로 다르게 보인다: 다시 시도 / 준비 탭 이동 / 부분 실패 알림 배너, SSE가 끊겨도 `/chat/pending`으로 승인 대기를 복구한다 (ADR-0012)
3. `MOCK=1` 하나로 백엔드 없이 fixture 8종을 재생해 화면을 먼저 완성했고, 프록시는 SSE를 버퍼링 없이 흘려보낸다 (강의 p.114)
