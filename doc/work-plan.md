# Interview Coach Agent — 작업 계획서

> 작성 2026-10-20 (Day1) · 기준 문서: [design.md](design.md) · 마감 Day3 13:00
> 역할별 agent가 각자 영역을 구현하고, 분기점(CP)마다 통합·검증한다. 모든 agent는 착수 전에 이 문서와 `agent.md`를 읽는다.

## 1. 목적과 원칙

| 원칙 | 내용 |
|---|---|
| 단일 기준 | 범위·구조·계약은 [design.md](design.md)가 기준이다. 바꿔야 하면 Lead가 design.md와 ADR을 먼저 고친다 |
| 계약 우선 | agent끼리 맞물리는 지점(State, Deps, 스키마, SSE 이벤트, API, MCP 이름)은 `contracts/`에 코드로 고정하고, 착수 전에 커밋한다 |
| 점검은 스크립트로 | "규칙 지켰음" 자기 보고 대신 `check.sh` 통과 여부로 판정한다. Lead가 다시 실행해 확인한다 |
| 소유권 | 각 agent는 자기 담당 경로만 수정한다. 공유 파일은 Lead만 수정한다 |
| 결정은 ADR로 | "왜 이렇게 만들었나"는 `doc/adr/`에 고정 틀로 남긴다(§8). 기각된 대안으로 임의로 돌아가지 않는다 |
| 설명 가능성 | 분기점마다 사용자가 인수인계 노트를 읽고 코드를 설명할 수 있어야 다음 단계로 넘어간다 |

## 2. 역할과 소유권

| 역할 | 담당 경로 (수정 가능) | 브랜치 / worktree | 실행 주체 |
|---|---|---|---|
| **Lead** (통합) | `contracts/`, `agent.md`, `check.sh`, `requirements.txt`, `pyproject.toml`, `.env.example`, `.gitignore`, `sh/`(단 `sh/smoke_*.sh` 제외), `ref/`(읽기 전용 참고 복사본), `examples/`, `tests/conftest.py`, `tests/test_contracts.py`, `doc/` 전체, `eval/`, `README.md` | `main` (repo 루트) | 메인 세션 (새 세션 권장) |
| **A1** 에이전트 코어 | `agent/`(단 `agent/mcp_client.py` 제외), `tests/test_core_*.py` | `feat/core` / `.worktrees/core` | 서브agent |
| **A2** MCP·RAG | `mcp_server.py`, `rag.py`, `agent/mcp_client.py`, `templates/`, `tests/test_mcp_*.py` | `feat/mcp` / `.worktrees/mcp` | 서브agent |
| **A3** API | `server.py`, `routers/`, `services/`, `tests/test_api_*.py`, `sh/smoke_*.sh` | `feat/api` / `.worktrees/api` | 서브agent (CP1 이후) |
| **A4** 프론트 | `web/`, `web_server.py` | `feat/web` / `.worktrees/web` | 서브agent |

- 모든 역할은 `doc/adr/`에 ADR 초안(Proposed)과 `doc/handoff/<role>.md`를 **추가**할 수 있다. 기존 ADR 수정·확정은 Lead만 한다.
- `examples/sample_user/`는 Lead가 Phase 0에 복사한 뒤 읽기 전용으로 둔다.

### 목표 디렉토리 구조
```
skala-ai-miniproject/
├── agent.md · check.sh · README.md · requirements.txt · .env.example · .gitignore
├── contracts/   state.py · deps.py · schemas.py · events.py · api.py · mcp.py · fixtures/
├── agent/       llm.py · deps.py(build_deps) · coach_agent.py · reviewer_agent.py · graph.py
│                store.py · tools.py(MCP 래퍼) · prompts.py · retry.py · mcp_client.py[A2]
├── mcp_server.py · rag.py · templates/persona_rules.default.md
├── server.py · routers/(setup · chat · cards) · services/(readiness · posting)
├── web/         index.html · app.js · api.js (200줄 넘으면 components/로 분리)
├── web_server.py
├── tests/ · eval/ · examples/sample_user/ · sh/
├── doc/         design.md · work-plan.md · adr/ · handoff/
└── data/        (gitignore: 사용자 입력·coach.db·checkpoints.db·임베딩 캐시)
```

## 3. Phase 0 — 공유 규칙·계약·환경 (Lead, 착수 전)

| 산출물 | 내용 | 완료 기준 |
|---|---|---|
| `agent.md` | 프로젝트 요약·문서 위치 / 소유권표(§2) / 코딩 규칙(노드는 `async`, 의존성은 Deps 주입, 파일 약 200줄, 주변 코드의 주석 밀도·명명 따르기) / 실행 명령·환경변수 / 금지 사항(타 영역 수정, 계약 변경, `.env`·`data/`·개인정보 커밋, 기각된 ADR 대안으로의 임의 회귀) / 작업 전·후 체크리스트(§4) / 인수인계 노트 양식(부록 A) / ADR 규칙(§8) / 커밋 메시지 규칙(`[role] 요약 (ADR-NNNN)`, **Claude·AI 이름 표기 금지** — `Co-Authored-By` 등 trailer를 붙이지 않는다) | 각 역할 agent가 이 파일과 design.md만 읽고 착수할 수 있음 |
| `contracts/` | `state.py`(AgentState), `deps.py`(Deps dataclass), `schemas.py`(UserProfile·ExpressionCard·Route·ReviewResult·Violation — 10/13 `dapdap/schemas.py` 기반 + Card 저장형), `events.py`(design §5 SSE 이벤트 Pydantic 모델), `api.py`(REST 요청·응답 모델), `mcp.py`(Tool·Resource·Prompt 이름·인자 상수), `fixtures/`(fake 카드·검수 결과·SSE 재생 시퀀스 JSON) | `tests/test_contracts.py` 통과 (import, 스키마 round-trip, fixture가 스키마를 만족) |
| `check.sh` | ① ruff ② pytest ③ 계약 테스트 ④ 금지 패턴 grep(`.env`, `data/`, 실제 서류 고유명사 목록) ⑤ **소유권 diff 검사**(현재 브랜치의 `main` 대비 변경 경로가 §2 허용 경로 밖이면 실패) ⑥ 파일 길이 경고(200줄 초과) ⑦ ADR 검사(§8) | `main`에서 통과 |
| 환경 | `git init` / `.gitignore`(.env, data/, *.db, .venv, .worktrees/) / `.venv` + 버전 고정 `requirements.txt`(fastapi, uvicorn, langgraph, langgraph-checkpoint-sqlite, langchain, langchain-openai, langchain-ollama, fastmcp, mcp, httpx, pydantic, python-dotenv, langsmith, pytest, pytest-asyncio, ruff) / `.env.example`(FAST_MODEL, QUALITY_MODEL, EMBEDDING_MODEL, COACH_DATA_DIR, LANGSMITH_*) / 디렉토리 skeleton / `sh/setup_venv.sh`·`sh/seed_sample.sh`(examples → data 복사) / worktree 4개 생성 | `bash sh/setup_venv.sh && bash check.sh` 통과 |
| 재사용 코드 복사 | 아래 표 | 출처를 파일 상단 주석에 한 줄로 기록 |
| 소급 ADR 0001~0011 | §8 표 | 색인 등록, `check.sh` ADR 검사 통과 |

### 재사용 코드 (참조가 아니라 복사)

| 출처 | 파일 | 가져갈 곳 · 담당 |
|---|---|---|
| 10/13 `skala-ai-agent/practice` | `dapdap/schemas.py` | `contracts/schemas.py` (Lead) |
| | `dapdap/prompts.py` (router·generator·reviewer 프롬프트, `banned_hits`) | `agent/prompts.py` (A1) |
| | `dapdap/graph.py` (노드 로직) | `agent/coach_agent.py`·`reviewer_agent.py`·`graph.py` 참고 (A1) |
| | `dapdap/tools.py` (검색 3종 로직, `save_card`·`get_due_cards`) | 검색 → `mcp_server.py` (A2), 저장 → `agent/store.py` (A1) |
| | `dapdap/rag.py` | `rag.py` (A2) |
| | `dapdap/config.py` (`init_chat_model`, `text_of`) | `agent/llm.py` 참고 (A1) |
| | `scripts/check_inputs.py`, `scripts/ingest_posting.py`(프롬프트) | `services/readiness.py`·`services/posting.py` (A3) |
| | `scripts/run_eval.py`, `data/test_cases.json` | `eval/` (Lead, Day3) |
| | `examples/sample_user/`, `templates/persona_rules.default.md` | 동일 경로 (Lead) |
| Base `all_total_vue_student` | `agent/mcp_client.py` (`find_*`, `_attr`) | `agent/mcp_client.py` (A2) |
| | `agent/retry.py` | `agent/retry.py` (A1) |
| | `server.py` (lifespan 싱글턴, LangSmith flush) | `server.py` 참고 (A3) |
| | `web_chat.html` (SSE 파싱, `STEP_LABELS` 패턴, 레이아웃 CSS) | `web/` 참고 (A4) |
| | `web_demo_server.py` (프록시 패턴) | `web_server.py` 참고 (A4) |

## 4. 작업 전·후 프로토콜

| 시점 | 체크리스트 |
|---|---|
| **작업 전** | ① `agent.md`, design.md, 이 문서의 자기 작업 지시서(§5) 읽기 ② `doc/adr/README.md` 색인에서 관련 ADR과 **기각된 대안** 확인 ③ 자기 브랜치·worktree인지 확인 ④ `bash check.sh` 기준선 통과 확인 (실패하면 착수하지 말고 Lead에 보고) |
| **작업 중** | ADR 트리거(§8)가 생기면 즉시 Proposed ADR 작성. 계약을 바꿔야 하면 수정하지 말고 Lead에 요청 |
| **작업 후** | ① `bash check.sh` 통과 ② 자기 테스트 통과 ③ `doc/handoff/<role>.md` 작성(부록 A) ④ 커밋 메시지에 관련 ADR 번호, Claude·AI 이름 표기 금지(`Co-Authored-By` trailer 없음) ⑤ Lead에 보고 |
| **Lead 검증** | 보고를 그대로 믿지 않고 해당 worktree에서 `check.sh`를 다시 실행 → 인수인계 노트와 실제 diff 대조 → Proposed ADR 검토 |

## 5. 역할별 작업 지시서

### A1 에이전트 코어 (Day1 저녁 ~ Day2 오전)
- **입력**: `contracts/`, 10/13 `dapdap/` 복사본, design §2·§3·§6
- **할 일**
  - `agent/llm.py`: `init_chat_model`로 FAST/QUALITY 모델 생성, 테스트용 `GenericFakeChatModel` 팩토리
  - `agent/deps.py`: `build_deps()` — Deps 조립 (정의는 `contracts/deps.py`)
  - `agent/tools.py`: MCP 래퍼 `@tool` 3종 — `deps.mcp`의 계약 인터페이스만 호출 (A2 구현 전에는 fixture 기반 fake MCP로 개발)
  - `agent/coach_agent.py`: `create_agent`(ReAct) 서브그래프, `ToolStrategy(ExpressionCard)`, `ToolCallLimitMiddleware`
  - `agent/reviewer_agent.py`: LLM 검수 + `banned_hits` 규칙 검사 서브그래프
  - `agent/graph.py`: Supervisor 그래프 — router → coach → reviewer ⟲2 → approve(`interrupt`) → save/rejected, review_cards, out_of_scope. 모든 노드 `async`, 이벤트는 `contracts/events.py` 모델로 `get_stream_writer()` 전송
  - `agent/store.py`: SQLite 카드 저장·due 조회·복습 단계(0·1·2 = D+1·D+3·D+7)
  - 체크포인터: `AsyncSqliteSaver`
- **완료 기준**: design §6 테스트 1~7 통과 (fake 모델, 네트워크 없음)
- **금지**: `agent/mcp_client.py`·라우터·웹 수정, 동기 `invoke` 사용

### A2 MCP·RAG (Day1 저녁 ~ Day2 오전)
- **입력**: `contracts/mcp.py`, 10/13 `rag.py`·`tools.py`, Base `mcp_client.py`
- **할 일**
  - `mcp_server.py`(fastmcp): Tool `search_my_experience`·`search_expression_bank`, Resource `posting://{section}`, Prompt `persona_review_prompt`
  - `rag.py`: 제목 단위 분할 → 임베딩(`EMBEDDING_MODEL` env, 테스트용 fake 임베딩) → 코사인 검색, 파일 mtime이 바뀌면 재색인, 결과에 출처 라벨 포함
  - `agent/mcp_client.py`: Base 클라이언트를 coach 서버용으로 조정, `find_*` 탐색 유지, 의도적 flaky 데모 제거
- **완료 기준**: `tests/test_mcp_*.py` — 이름·시그니처가 `contracts/mcp.py`와 일치, 검색 결과에 출처 라벨, Resource 섹션 추출, Prompt 렌더링, mtime 재색인
- **금지**: `agent/` 다른 파일 수정, 데이터 경로 하드코딩(`COACH_DATA_DIR` 사용)

### A3 API (CP1 이후, Day2 오전 ~ 점심)
- **입력**: CP1 통합본, `contracts/api.py`·`events.py`
- **할 일**
  - `server.py`: lifespan에서 Deps·MCP·체크포인터 1회 생성, LangSmith flush
  - `routers/setup.py`: profile, docs, posting(normalize·저장), readiness
  - `routers/chat.py`: `/chat/stream`(SSE, 이벤트 직렬화 → `[DONE]`), `/chat/resume`(JSON), `/chat/pending`
  - `routers/cards.py`: cards, due, review
  - `services/readiness.py`(check_inputs 이식), `services/posting.py`(ingest 프롬프트 이식)
  - `sh/smoke_chat.sh`: curl로 stream → pending → resume 시나리오
- **완료 기준**: 테스트 8·9 통과, 스모크 스크립트가 fake와 ollama에서 성공
- **금지**: 그래프 로직 수정(필요하면 A1에 요청), 계약 변경

### A4 프론트 (Day1 저녁 ~ Day2 저녁)
- **입력**: `contracts/fixtures/`, design §4·§5, Base `web_chat.html`
- **할 일**
  - 탭 3개(P0): 준비(체크리스트, 프로필 폼, 문서 업로드 FileReader, 공고 붙여넣기 → 정리 → 수정 → 저장) / 코치(타임라인, 카드 컴포넌트, 경고 배너, 승인·거절, pending 복원) / 카드(목록, P1 퀴즈)
  - Vue 버전 고정 CDN, `api.js`(fetch, EventSource 래퍼), `thread_id` localStorage
  - `web_server.py`: 정적 서빙 + `/api/*`·`/chat/*` catch-all 프록시, **`MOCK=1`이면 fixtures로 응답·SSE 재생**(백엔드 없이 개발)
- **완료 기준**: MOCK 모드에서 design §4 P0 화면 전부 동작 → CP3에서 실제 백엔드로 동작
- **금지**: 백엔드 코드 수정, 계약에 없는 필드 사용

### Eval·문서 (Lead, Day3 오전)
- `eval/run_eval.py`(v2 HTTP 버전) · `eval/before_after.ipynb` · `eval/demo.ipynb` (출력 포함 저장)
- design §7 지표·한계 4종 측정, README(실행법 + E2E 캡처 3개), ADR 결과 절 갱신, PPT 자료

## 6. 분기점 (Checkpoint)

**공통 절차**: 정해진 순서로 병합(core → mcp → api → web) → `check.sh` → design.md 적합성 체크리스트 → 해당 구간 ADR 확정 → **사용자 리뷰 게이트**(인수인계 노트를 읽고 핵심 흐름을 설명할 수 있는가) → 통과해야 다음 단계 → Lead가 `main`을 private 레포 `origin`(github.com/seulstat/skala-ai-miniproject)에 push.

| CP | 시점 | 결합 대상 | 통과 기준 | 적합성 체크 (design.md) | 실패 시 |
|---|---|---|---|---|---|
| **CP0** | Day1 19:30 | 계약 + 환경 | `check.sh` 통과, 빈 그래프가 fake 모델로 실행, worktree 4개 준비, ADR 0001~0011 등록 | §2 핵심 결정 ↔ ADR 대응 | 역할 착수 보류, Lead 보완 |
| **CP1** | Day2 10:00 | A1 + A2 | 실제 MCP 서버 + fake LLM으로 그래프 E2E, 테스트 1~7 + MCP 테스트 통과 | §3 Multi-Agent·MCP·RAG·DI·HITL 행 | 경계 문제면 계약 보완 ADR, 아니면 해당 agent 재작업 |
| **CP2** | Day2 13:00 | + A3 | `sh/smoke_chat.sh`가 fake → ollama 순서로 성공, 테스트 8·9 통과, 서버 재시작 후 pending 복원 확인 | §5 API·SSE 이벤트 표 | ollama 실패 시 QUALITY_MODEL 조정, 스모크는 fake로 진행 |
| **CP3** | Day2 20:00 | + A4 | 브라우저 E2E(ollama): 준비 → 생성 → 검수 → 승인 → 저장 → 카드 확인, 새로고침 후 승인 대기 복원 | §4 P0 체크리스트 전부 | **컷 규칙** 발동: P1 전부 제외, 결함 수정 우선 |
| **CP4** | Day3 11:30 | 최종 | OpenAI로 E2E 확인, `before_after.ipynb`·`demo.ipynb` 출력 포함, README 캡처, ADR 결과 절 갱신 | §1 목표 G1~G7 전부 | 미측정 지표는 "미측정"으로 명시하고 PPT 우선 |

## 7. 타임라인

| 시점 | Lead | A1 | A2 | A3 | A4 |
|---|---|---|---|---|---|
| Day1 ~17:00 | 스프레드시트 계획 등록 (design §11) | | | | |
| Day1 17:30~19:30 | Phase 0 → **CP0** | | | | |
| Day1 19:30~23:00 | 질의 대응·Proposed ADR 검토 | 그래프·HITL·store | MCP·RAG | | MOCK 모드 화면 |
| Day2 09:00~10:00 | **CP1** 병합·검증 | 마무리 | 마무리 | | 계속 |
| Day2 10:00~13:00 | 지원 → **CP2** | CP1 수정 대응 | CP1 수정 대응 | 라우터·SSE·스모크 | 계속 |
| Day2 13:00~20:00 | 통합 수정 → **CP3** | 결함 수정 | 결함 수정 | 결함 수정 | 실제 백엔드 연결 |
| Day2 20:00~ | P1 여부 판단 (컷 규칙) | P1: 복습 단계 | | P1: review API | P1: 퀴즈 |
| Day3 09:00~11:30 | Eval·문서 → **CP4** | | | | |
| Day3 11:30~13:00 | PPT 완성, Git·보고서 링크 등록 | | | | |

**컷 규칙** (design §9): Day2 오후까지 E2E가 안 되면 P1은 모두 버리고 측정·PPT를 우선한다.

## 8. ADR (Architecture Decision Record) 운영

**목적**: "왜 이렇게 만들었나"를 나중에도 설명하고, 같은 논쟁의 반복과 기각된 대안으로의 회귀를 막고, 온보딩·재검토 시 근거를 바로 찾는다.

- **위치**: `doc/adr/NNNN-<kebab-제목>.md` + 색인 `doc/adr/README.md` (번호 · 제목 · 상태 · 날짜 · 작성 역할 · 대체 관계를 한 줄씩)
- **고정 틀**: 메타 → **배경 → 결정 → 대안 비교 → 결과** (부록 B 템플릿)
- **상태**: Proposed(작성) → Accepted / Rejected(Lead가 CP에서 확정) → Superseded(새 ADR이 대체)
- **역할**: 결정한 agent가 Proposed로 작성 → Lead가 확정·색인 갱신. 기각된 대안도 반드시 대안 비교 표에 남긴다.

### 기록 시점 — 언제 무엇을

| 시점 | 작성 | 기록 대상 |
|---|---|---|
| **Phase 0** (착수 전) | Lead | design.md §2 핵심 결정 소급 기록 — 아래 0001~0011 |
| **작업 중** (결정 즉시) | 각 agent | 트리거: ① 계약 변경 요청 ② 라이브러리 추가·버전 변경 ③ design.md와 다르게 구현 ④ 대안 2개 이상 비교 후 선택 ⑤ 성능·보안·개인정보 영향 ⑥ 기존 ADR 번복 |
| **CP0~CP4** | Lead | 구간 내 Proposed 일괄 확정, 통합 중 발견한 충돌의 해결 결정 |
| **범위 컷 발생 시** | Lead | P1 포기·기능 축소와 그 근거(일정·위험) |
| **Day3 측정 후** | Lead | 결과 절 갱신 — 가설 vs 실측, 한계 4종과 연결 |

### Phase 0 소급 ADR

| 번호 | 제목 | design.md §2 대응 행 |
|---|---|---|
| 0001 | LLM 계층을 LangChain 모델로 통일하고 fast/quality 분리 | LLM 계층, 모델 분리 |
| 0002 | MCP Tool을 create_agent에 래퍼 Tool로 연결 | MCP ↔ create_agent |
| 0003 | RAG를 MCP 서버 프로세스 안에 둔다 | RAG 위치 |
| 0004 | Coach·Reviewer 멀티에이전트로 전환 (10/13 "단일 Agent + Reviewer 노드" 결정을 supersede) | Multi-Agent |
| 0005 | 모든 그래프 노드를 async로 | 비동기 |
| 0006 | HITL 재개는 JSON resume + pending 조회 | HITL |
| 0007 | 문서 업로드는 FileReader → JSON | 업로드 |
| 0008 | 단일 사용자 전제와 MVP 범위 컷 | 사용자, design §8 |
| 0009 | Before/After 측정 조건 고정 | design §7 |
| 0010 | 역할 분담과 worktree 병렬 진행 (테스트 7을 CP1로 앞당김 포함) | 이 문서 §2·§6, design §9 |
| 0011 | Deps 정의를 contracts/deps.py로, 조립은 agent/deps.py build_deps() | DI 위치 |

### 프로토콜·도구 연동
- **작업 전**: 색인에서 관련 ADR·기각된 대안 확인. 기각된 대안으로 돌아가려면 **새 근거를 담은 supersede ADR**을 써야 한다.
- **작업 후**: 내린 결정의 ADR 번호를 인수인계 노트와 커밋 메시지에 적는다.
- **`check.sh`**: ADR 필수 제목(배경·결정·대안 비교·결과) 검사, 색인 누락 검사, `contracts/`·`requirements.txt`가 바뀐 커밋에 ADR 번호가 없으면 실패.
- **인수인계 노트와의 구분**: 노트는 무엇을·어디에(구현 안내), ADR은 왜(결정 근거). 노트는 ADR 링크만 걸고 근거를 다시 쓰지 않는다.
- **발표 활용**: ADR 요약을 PPT의 "개선 근거"·"한계" 슬라이드와 질의응답 대비 자료로 쓴다.

## 9. 위험과 대응

| 위험 | 대응 |
|---|---|
| 작업 중 계약 변경이 필요 | agent는 수정하지 않고 Lead에 요청 → Lead가 계약·ADR 수정 후 영향받는 agent에 재통지 |
| ollama 소형 모델의 구조화 출력·Tool 호출 실패 | QUALITY_MODEL을 qwen3:8b 이상으로, ollama는 스모크 확인용, 최종 확인·측정은 OpenAI (실패율 자체를 한계로 기록) |
| worktree 병합 충돌 | 소유권 분리로 예방, 공유 파일은 Lead만 수정, 병합 순서 고정 |
| 일정 지연 | 컷 규칙 — P1 제외, 측정·PPT 우선 |
| 토큰 사용 한도 | Lead는 새 세션에서 시작, 역할 agent는 Sonnet, CP 판정은 `check.sh` 결과 위주 |
| 개인 서류 유출 | `examples/sample_user`만 사용, `data/` gitignore, `check.sh` 금지 패턴 검사 |

## 부록 A. 인수인계 노트 양식 (`doc/handoff/<role>.md`)

```markdown
# <역할> 인수인계 — <날짜> (CP<n>)
## 한 일
## 파일·함수 위치
| 파일 | 함수/클래스 | 역할 |
## 관련 ADR
## 사용한 계약 (contracts/)
## 테스트 결과 (check.sh, 자기 테스트)
## 알려진 한계·미완료
## 발표 때 설명할 포인트 (3줄)
```

## 부록 B. ADR 템플릿

```markdown
# ADR-NNNN: <결정 제목>

- 상태: Proposed | Accepted | Rejected | Superseded by ADR-XXXX
- 날짜: YYYY-MM-DD
- 작성: <역할>
- 관련: design.md §<절>, supersedes ADR-XXXX (있으면)

## 배경
<어떤 문제·제약 때문에 결정이 필요했는가>

## 결정
<무엇을 하기로 했는가 — 한두 문장>

## 대안 비교
| 대안 | 장점 | 단점 | 기각 이유 |
|---|---|---|---|

## 결과
- 긍정:
- 부정(트레이드오프):
- 후속 조치:
- 검증 방법:
```

### 작성 예시 — ADR-0004

```markdown
# ADR-0004: Coach·Reviewer 멀티에이전트로 전환

- 상태: Accepted
- 날짜: 2026-10-20
- 작성: Lead
- 관련: design.md §2·§3, supersedes 10/13 02_architecture.md "단일 Agent + Reviewer 노드"

## 배경
10/13 버전은 흐름이 하나라 Supervisor가 과하다고 보고 단일 Agent에 Reviewer 노드만 두었다.
이번 과제는 평가 기준에 Multi-Agent가 명시돼 있고, 검수가 생성 맥락에 끌려가는 문제
(GPT Reviewer 진동, 의미 왜곡 — 10/13 평가 §5.3 #5)가 이미 관찰됐다.

## 결정
Coach(ReAct, Tool 선택)와 Reviewer(LLM + 규칙 검사)를 각각 컴파일된 서브그래프로 분리하고,
메인 그래프가 Supervisor로서 라우팅·재시도 상한·승인을 통제한다.

## 대안 비교
| 대안 | 장점 | 단점 | 기각 이유 |
|---|---|---|---|
| 단일 Agent + Reviewer 노드 (10/13) | 단순, 호출 수 적음 | 검수가 같은 그래프 상태를 공유, Multi-Agent 근거 약함 | 평가 기준 미충족 |
| Supervisor + Writer·Researcher·Reviewer 3개 이상 | 역할 세분화 | 호출 수·지연·디버깅 부담, 2.5일 일정 초과 | MVP 범위 초과 |

## 결과
- 긍정: 검수가 생성 맥락과 분리되어 독립적으로 판단, 서브그래프 단위 단위테스트 가능
- 부정: 서브그래프 경계에서 상태 변환 코드 추가, 호출 오버헤드
- 후속 조치: Before/After에서 재작성 횟수·지연 비교
- 검증 방법: design §6 테스트 2·3, design §7 재작성 횟수 지표
```
