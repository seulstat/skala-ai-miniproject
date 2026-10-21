# 흐름 설명서 — 사용자(발표자)용

> 코드를 읽지 않고도 "무엇이 어디서 어떻게 움직이는지"를 설명할 수 있게 만든 문서. CP마다 Lead가 갱신한다.
> 막히는 용어는 맨 아래 §6 용어집에서 찾는다. 이 문서를 읽고도 모르는 부분은 Lead에게 묻고, 답을 §7에 쌓는다.

## 1. 한 장 요약

```
[브라우저]  탭 ①준비 ②코치 ③카드          ← web/ (A4)
    │  모든 요청은 같은 주소(:8600)로
[web_server.py :8600]  화면 파일 서빙 + /api·/chat 요청을 :8100으로 그대로 전달(프록시)
    │
[server.py :8100]  FastAPI. 켜질 때 한 번 Deps(모델·MCP·DB 연결)를 조립   ← routers/ (A3)
    │
[LangGraph 그래프]  router → coach → reviewer(최대 2번 재작성) → approve(⏸멈춤) → save   ← agent/ (A1)
    │                        │
[MCP 서버 "coach"]  경험 검색(RAG)·표현집 검색·공고 섹션·검수 규칙   ← mcp_server.py, rag.py (A2)
    │
[data/ 폴더]  사용자 서류 + DB 파일 2개 (§2)
```

## 2. 데이터는 어디에 저장되나 (`data/` = `COACH_DATA_DIR`)

| 파일 | 내용 | 누가 쓰나 | 언제 바뀌나 |
|---|---|---|---|
| `profile.json` | 프로필 | 준비 탭 → `PUT /api/profile` | 저장할 때 |
| `docs/*.md` | 경험 문서 | 준비 탭 → `POST /api/docs` | 업로드할 때 |
| `job_posting.md` | 정리된 공고 | 준비 탭 → `PUT /api/posting` | 저장할 때 |
| **`checkpoints.db`** | **그래프 진행 상태** — "어느 단계에서 멈췄고, 그때 카드·경고가 무엇이었나" | 그래프(LangGraph `AsyncSqliteSaver`)가 단계마다 자동 기록 | 노드가 끝날 때마다 |
| **`coach.db`** | **승인된 카드**와 복습 단계·다음 복습일 | save 노드(`CardStore`) | 승인했을 때만 |
| `embedding_cache.json` | 경험 문서 임베딩 캐시 | MCP 서버(RAG) | 문서가 바뀌었을 때 |

핵심: **승인 대기 중인 카드는 `checkpoints.db`에, 승인된 카드는 `coach.db`에** 있다. 둘 다 디스크의 파일이라 서버를 꺼도 남는다(메모리 캐시가 아니다).

## 3. API 지도 — 화면 동작 ↔ 엔드포인트

| 화면에서 하는 일 | 엔드포인트 | 하는 일 |
|---|---|---|
| ① 준비 탭 열기 | `GET /api/readiness` | 프로필·문서·공고가 다 있는지 점검표를 돌려줌 (오류를 내지 않고 "error/warn/ok" 표만 줌) |
| 프로필 저장 | `GET·PUT /api/profile` | `profile.json` 읽기·쓰기 |
| 경험 문서 올리기·지우기 | `GET·POST·DELETE /api/docs` | `docs/*.md` 관리 |
| 공고 정리 → 저장 | `POST /api/posting/normalize` → `PUT /api/posting` | LLM이 6개 섹션으로 정리한 초안 → 사용자가 고친 뒤 저장 |
| ② 질문 보내기 | `GET /chat/stream` | 그래프를 돌리며 진행 단계를 실시간(SSE)으로 흘려보냄. 카드가 나오면 멈춤 |
| 새로고침했을 때 | `GET /chat/pending` | **멈춰 있는 카드가 있으면 꺼내 줌** (`checkpoints.db`에서) |
| 승인·거절 버튼 | `POST /chat/resume` | 멈춘 그래프를 이어서 실행 → 승인이면 저장 |
| ③ 카드 탭 | `GET /api/cards`, `/api/cards/due`, `POST /api/cards/{id}/review` | 저장된 카드 목록, 오늘 복습할 카드, 복습 결과 |

경로 목록의 원본은 `contracts/api.py`의 `ROUTES`, 실제 구현은 `routers/setup.py`·`chat.py`·`cards.py`.

## 4. 시나리오별 흐름

### A. 정상: 질문 → 카드 → 승인 → 저장
1. 사용자가 질문 → 브라우저가 `GET /chat/stream?message=...&thread_id=...`를 연다(EventSource).
2. 서버가 먼저 준비 점검. 통과하면 그래프 실행.
3. router가 의도 분류 → 화면에 `RouteDecided`.
4. coach가 MCP로 근거 검색(호출마다 `EvidenceSearched`) → 카드 초안(`CardDrafted`).
5. reviewer가 MCP Prompt로 받은 규칙 + 금지 표현 검사 → `ReviewDone`. 불합격이면 coach가 다시 씀(최대 2번).
6. approve 노드에서 **그래프가 멈춘다**(`interrupt`). 이 순간의 상태가 `checkpoints.db`에 저장됨 → 화면에 `ApprovalRequired`(카드) → `[DONE]`으로 스트림 종료.
7. 승인 클릭 → `POST /chat/resume {thread_id, approve:true}` → 그래프가 멈춘 지점부터 이어서 save 실행 → `coach.db`에 저장 → `{saved, card_id, next_review}` 응답.

### B. 새로고침·서버 재시작 후 복원 (CP2 질문 1)
1. 6번에서 멈춘 상태는 이미 `checkpoints.db` 파일에 있다.
2. 새로고침하면 화면은 비지만, 브라우저 localStorage에 `thread_id`(대화 번호)가 남아 있다.
3. 화면이 `GET /chat/pending?thread_id=...`를 부른다 → 서버가 `checkpoints.db`에서 그 대화의 멈춘 지점(`interrupts`)을 읽어 카드·경고를 돌려준다 → 화면이 카드와 버튼을 다시 그린다.
4. 서버를 껐다 켜도 같다 — 켜질 때 같은 `checkpoints.db` 파일에 다시 연결하기 때문.
- `/chat/resume`은 "꺼내 오는" 게 아니라 "이어서 실행하는" 엔드포인트다. 꺼내 오는 건 `/chat/pending`.

### C. 오류 상황
| 상황 | 무슨 일이 일어나나 | 화면 |
|---|---|---|
| **서류 없이 질문** (CP2 질문 3) | `/chat/stream`이 그래프를 돌리기 전에 준비 점검 → 실패 → SSE로 `ErrorRaised(NOT_READY)` → `[DONE]` | "준비 탭에서 … 먼저 입력해 주세요" + 준비 탭 이동 버튼 |
| 근거 검색 지연 | 0.5초·1.5초 기다리며 재시도 → 그래도 실패하면 **그 검색만** 실패 표시하고 카드는 계속 만듦 | 타임라인에 실패 표시, 카드 위 경고 배너 |
| 모델이 카드 형식을 못 만듦 | `ErrorRaised(LLM_OUTPUT_INVALID)` | "다시 시도" 버튼 |
| **승인 두 번 클릭** (CP2 질문 2) | 같은 대화의 resume은 잠금(lock)으로 한 번에 하나만 처리. 첫 번째가 저장하면 승인 대기가 사라지므로 두 번째는 `409 NO_PENDING` | "이미 처리됐을 수 있어요" |
| 저장 중 DB 오류 | `STORE_ERROR`(재시도 가능). 그래프는 "저장 직전" 상태로 남아 있어 **승인 버튼을 다시 누르면 저장만 다시 시도** | "승인 버튼을 다시 눌러 주세요" |

- **왜 서류 없음을 HTTP 409가 아니라 SSE `ErrorRaised`로 보내나?** 브라우저의 EventSource는 HTTP 오류 응답의 본문을 읽지 못한다. 409로 보내면 화면은 "연결 실패"만 알고 이유를 모른다. 그래서 스트림을 정상(200)으로 열고 그 안에 오류 이벤트를 담아 보낸다.
- `GET /api/readiness`는 오류를 내는 곳이 아니라 점검표를 보여 주는 곳이다. 같은 점검 함수를 `/chat/stream`도 내부에서 쓴다.
- 알려진 한계: 저장 오류 상태에서 새로고침하면 `/chat/pending`이 비어 승인 화면이 사라진다(멈춤 지점이 아니라 "저장 직전"이라서). 다시 질문하면 된다.

## 5. 코드 위치 (궁금할 때 열어 볼 곳)

| 단계 | 파일 |
|---|---|
| 서버 시작·Deps 조립 | `server.py`, `agent/deps.py` |
| SSE·resume·pending | `routers/chat.py` |
| 그래프 흐름 | `agent/graph.py`, `agent/routing.py` |
| 근거 검색 래퍼·재시도 | `agent/tools.py` |
| 검수 | `agent/reviewer_agent.py` |
| 카드 저장·복습 단계 | `agent/store.py` |
| MCP 서버·RAG | `mcp_server.py`, `rag.py` |
| 오류 코드 표 | `contracts/errors.py` |

## 6. 용어집

| 용어 | 한 줄 설명 |
|---|---|
| 엔드포인트 | 서버가 받는 주소 하나 (예: `GET /chat/pending`). 앞의 GET·POST는 요청 종류 |
| SSE / EventSource | 서버가 한 번 연 연결로 여러 메시지를 차례로 흘려보내는 방식 / 그걸 받는 브라우저 기능 |
| thread_id | 대화 번호. 같은 번호면 같은 대화의 상태를 이어 쓴다 |
| interrupt | 그래프를 특정 지점에서 멈추고 사람의 결정을 기다리게 하는 기능 (HITL) |
| 체크포인트 / 체크포인터 | 그래프의 단계별 상태 기록 / 그것을 저장하는 장치(`checkpoints.db`) |
| resume | 멈춘 그래프를 사람이 준 값(승인·거절)으로 이어서 실행 |
| Deps | 그래프·서버가 쓰는 부품 묶음(모델 2개·MCP·카드 저장소·체크포인터·경로). 켤 때 한 번 조립해 넘겨줌(DI) |
| MCP Tool / Resource / Prompt | 서버가 제공하는 기능 / 읽기 전용 자료 / 미리 만든 지시문 |
| RAG | 내 문서에서 관련 문단을 찾아(임베딩 검색) 모델에게 근거로 주는 방식 |
| fake 모델 | 테스트용 가짜 모델. 정해 둔 답만 한다 |
| 치명(fatal) / 재시도 가능(recoverable) | 이번 요청을 끝내는 오류인가 / 다시 하면 될 수도 있는가 |

## 7. 리뷰 게이트 Q&A 기록

| CP | 질문 | 핵심 답 |
|---|---|---|
| CP0 | 새로고침 시 승인 대기 복원 흐름 | §4-B |
| CP0 | Deps 필드가 더 필요하면? | 직접 고치지 않고 Proposed ADR + Lead 요청. 직접 고치면 check.sh ⑤ 소유권 FAIL |
| CP0 | 검수 불합격이 계속되면? | 재작성 2번(검수 3라운드) 후 warning을 붙여 승인 단계로. 저장 여부는 사용자가 결정 |
| CP1 | 검색 응답 지연 | §4-C "근거 검색 지연" — 치명 아님, 카드는 계속 |
| CP1 | Reviewer가 MCP Prompt로 규칙을 받는 이유 | MCP 기술 요소(Prompt) 실사용, 데이터 경계 분리(Agent는 파일 위치를 모름), 표준 지시문 재사용 |
| CP1 | 문서·공고 반영 시점 | 공고·규칙은 요청마다 읽음(캐시 금지), 경험 문서는 수정 시각이 바뀌면 다시 색인 |
| CP2 | 재시작 후에도 승인 대기가 남는 이유 | §2 `checkpoints.db` + §4-B |
| CP2 | 승인 두 번 / 저장 오류 | §4-C |
| CP2 | 서류 없음을 SSE로 보내는 이유 | §4-C 아래 설명 |
