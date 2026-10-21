# Interview Coach Agent — 설계 문서 (MVP)

> 작성 2026-10-20 (Day1) · 마감 Day3 13:00 (Git 주소 + 결과 보고서 링크 등록)
> 출발점: 10/13 개인 과제 "영어 면접 Agent" (`skala-ai-agent/practice`, CLI) + Base 골격 `all_total_vue_student`
> 이 문서는 구현 agent들이 공유하는 **단일 기준(source of truth)**이다. 범위·계약 변경은 이 문서를 먼저 고친다.
> 변경 이력: 2026-10-20 Phase 0 — Deps 정의 위치를 `contracts/deps.py`로 이동(ADR-0011), 테스트 7 완료 시점을 CP1(Day2 오전)로 앞당김(ADR-0010) / CP0 리뷰 — 강의자료 대조 후 오류 처리 4계층·ErrorRaised 이벤트·테스트 10·11 추가(ADR-0012)

## 0. 한 줄 정의

내 경험 서류와 지원 공고를 근거로 영어 면접 표현·답변을 만들고, 규칙 검수 후 **사용자가 웹에서 승인한 것만** 복습 카드로 쌓는 웹 서비스.

## 1. 목표 (평가 기준 → 판정 기준)

| ID | 출처 | 목표 (충족 판정 기준) |
|---|---|---|
| G1 | 기능 구현 완성도 30 | 브라우저에서 준비 → 생성 → 검수 → 승인 → 저장 → 카드 확인이 E2E로 동작. ollama로 먼저, OpenAI로 최종 확인. 실행 결과가 남은 문서(캡처·출력 포함 노트북)로 바로 확인 가능 |
| G2 | 기술 요소 30 | Multi-Agent·MCP·RAG·DI·LangSmith·모듈화·단위테스트 7개를 코드 위치로 짚을 수 있게 구현. **HITL 필수** |
| G3 | Before/After 10 (보너스) | 같은 입력·같은 모델로 10/13 버전(v1) vs 신규(v2) 수치 표 |
| G4 | 한계·트레이드오프 20 | 개선이 새로 만든 약점 3개 이상 + 가능하면 수치 |
| G5 | PPT 20 | 문제 → 개선 → Before/After → 한계 순서, 링크로 바로 열람 |
| G6 | MVP | 2.5일 안에 완료, 코드 전체를 본인이 설명 가능 |
| G7 | 일정 | Day1 17시 계획 등록 / Day3 13시 Git + 보고서 링크 등록 |

### 목표 ↔ 산출물

| 목표 | 산출물 |
|---|---|
| G1 | README(웹 E2E 시나리오 3개 캡처: 문장 / 면접 질문 / 복습) + `eval/demo.ipynb`(출력 포함) |
| G2 | §3 대응표 (PPT에 코드 위치 표기) |
| G3 | `eval/before_after.ipynb` + 결과 표 |
| G4 | §7 한계 4종 측정값 |
| G5 | Google Slides 링크 |
| G6 | §8 범위 |
| G7 | §9 일정 |

## 2. 구조

```
브라우저 (Vue 3 CDN, 버전 고정, 탭 3개)
   │ same-origin
web_server.py (:8600)  index.html · app.js 서빙 + /api/* /chat/* catch-all 프록시
   │
server.py (:8100, FastAPI)  lifespan 싱글턴 → agent/deps.py build_deps() → Deps 주입 (Deps 정의: contracts/deps.py)
   ├ routers/setup.py   프로필 · 문서 · 공고 · 준비 점검
   ├ routers/chat.py    /chat/stream(SSE) · /chat/resume · /chat/pending
   └ routers/cards.py   카드 목록 · 오늘 복습 · 복습 결과
   │
LangGraph 메인 그래프 (Supervisor)
   router → [Coach Agent 서브그래프] → [Reviewer Agent 서브그래프] ⟲ 최대 2회
          → approve(interrupt) ⏸ → save / rejected
          → review_cards / out_of_scope
   │                         │
MCP 서버 "coach" (stdio)     SQLite: checkpoints.db (AsyncSqliteSaver)
 Tool     search_my_experience (RAG)        coach.db (카드 · 복습 단계 · 대화)
 Tool     search_expression_bank
 Resource posting://{section}
 Prompt   persona_review_prompt
```

### 핵심 설계 결정

| 결정 | 선택 | 이유 |
|---|---|---|
| LLM 계층 | LangChain `BaseChatModel`로 통일. `init_chat_model(env)`로 ollama/openai 선택, 테스트는 `GenericFakeChatModel` | `create_agent`가 LangChain 모델을 요구함. Base의 httpx LLM 클래스는 쓰지 않음 |
| 모델 분리 | `FAST_MODEL`(router) / `QUALITY_MODEL`(Coach·Reviewer) 환경변수 2개 | Base의 비용 분리(fast/quality) 개념 유지 |
| MCP ↔ create_agent | Agent의 `@tool`은 `deps.mcp.call_tool(...)`을 부르는 얇은 래퍼 | Base `MCPClient`·`find_*` 탐색 재사용, Agent 코드는 10/13과 동일 형태 유지 |
| RAG 위치 | MCP 서버 프로세스 안 (임베딩 + 코사인 검색, 10/13 `rag.py` 재사용). 파일 mtime 변경 시 재색인 | 데이터 접근을 MCP 경계 뒤로 숨김 |
| Multi-Agent | Coach(ReAct, Tool 선택) / Reviewer(LLM + 규칙 검사기, MCP Prompt) 각각 컴파일된 서브그래프. 메인 그래프가 Supervisor로 라우팅·재시도 상한·승인 통제 | 검수자가 생성자의 맥락을 공유하지 않아 독립적으로 판단 |
| 비동기 | 모든 노드 `async` + `ainvoke` | Base의 이벤트 루프 블로킹 재발 방지 |
| HITL | `interrupt()` + `AsyncSqliteSaver`. `/chat/resume`은 JSON 응답, `/chat/pending`으로 새로고침 복원 | `EventSource`는 POST 불가. 승인 대기는 재시작 후에도 유지 |
| 업로드 | 브라우저 `FileReader`로 텍스트를 읽어 JSON 전송 (multipart 없음) | 프록시 단순화 |
| 사용자 | 단일 사용자 전제 | MVP 범위 |
| 오류 처리 | 4계층(Tool·Orchestration·Application·Presentation) + 코드별 재시도 가능 여부·사용자 메시지(`contracts/errors.py`). timeout만 백오프 재시도, 검색 일부 실패는 격리하고 계속 진행 | 오류 종류마다 다른 안내·다시 시도 버튼, 부분 실패에도 결과 제공 (강의 p.18·p.174) |
| DI 위치 | `Deps` 정의(필드·Protocol)는 `contracts/deps.py`, 조립 함수 `build_deps()`만 `agent/deps.py` | 서버(A3)·그래프(A1)·테스트가 같은 계약을 import하고, A1 소유 파일을 다른 역할이 고칠 일이 없음 |

## 3. 기술 요소 대응 (G2)

| 요소 | 구현 | 위치 |
|---|---|---|
| Multi-Agent | Coach / Reviewer 서브그래프 + Supervisor 그래프 | `agent/coach_agent.py`, `agent/reviewer_agent.py`, `agent/graph.py` |
| MCP | Tool 2 · Resource 1 · Prompt 1, `find_*`로 서버 탐색 후 호출 | `mcp_server.py`, `agent/mcp_client.py` |
| RAG | 경험 문서 제목 단위 분할 → 임베딩 → 코사인 검색, mtime 재색인 | `mcp_server.py` + `rag.py` |
| DI | `Deps(fast_llm, quality_llm, mcp, store, checkpointer, paths)`를 `partial`로 주입 (`paths`=COACH_DATA_DIR 파일 배치, ADR-0011) | 정의 `contracts/deps.py`, 조립 `agent/deps.py`(`build_deps()`) |
| LangSmith | 노드·MCP·LLM 계층 trace, Before/After 실행에 태그 | `@traceable`, 환경변수 |
| 모듈화 | `agent/`, `routers/`, `web/` 분리, 파일당 약 200줄 이하 | 디렉토리 구조 |
| 단위테스트 | fake 모델 기반 pytest 11개 (§6) | `tests/` |
| HITL | `interrupt()` + SQLite 체크포인터, 웹 승인·거절, 재시작 후 복원 | `agent/graph.py` approve, `/chat/resume`, `/chat/pending` |

## 4. 화면 (탭 3개)

P0 = 필수, P1 = 시간이 남으면.

| 탭 | 기능 |
|---|---|
| ① 준비 | P0: 준비 체크리스트(필수 3개 + 개인정보 경고), 프로필 폼, 경험 문서 업로드(.md, FileReader)·목록, 공고 붙여넣기/업로드 → [6개 섹션 정리] → 수정 → 저장 |
| ② 코치 | P0: 채팅 입력 + 예시 칩, 진행 타임라인(분류 → 근거 검색 → 초안 → 검수 위반 → 재작성), 카드 컴포넌트(Formal/Casual, 핵심 표현, 근거 칩, 답변 초안), 경고 배너, 승인·거절 버튼, 새로고침 시 승인 대기 복원 |
| ③ 카드·복습 | P0: 저장된 카드 목록(다음 복습일). P1: 오늘 복습 플립 퀴즈, 안다/다시 → 단계 0·1·2 = D+1·D+3·D+7 |

## 5. API · SSE 이벤트

### REST

| 영역 | 엔드포인트 | 비고 |
|---|---|---|
| 프로필 | `GET/PUT /api/profile` | `UserProfile` Pydantic 검증 (잘못된 enum → 422) |
| 경험 문서 | `GET/POST/DELETE /api/docs` | JSON `{name, content}` |
| 공고 | `POST /api/posting/normalize` → 초안, `PUT /api/posting` 확정 | 10/13 `ingest_posting.py` 프롬프트 재사용 |
| 준비 점검 | `GET /api/readiness` | 10/13 `check_inputs.py` 로직을 JSON으로 |
| 코치 | `GET /chat/stream?message&thread_id` | SSE |
| HITL 재개 | `POST /chat/resume {thread_id, approve}` | → `{saved, card_id, next_review}` |
| 승인 대기 조회 | `GET /chat/pending?thread_id` | 체크포인터의 interrupt payload, 없으면 `null` |
| 카드 | `GET /api/cards`, `GET /api/cards/due`, `POST /api/cards/{id}/review {result}` | review는 P1 |

### SSE 이벤트 (순서)

`RouteDecided{intent}` → `EvidenceSearched{tool, query, error?}`(Tool 호출마다) → `CardDrafted{attempt}` → `ReviewDone{round, passed, violations[], error?}` → `ApprovalRequired{card, warning, notices[]}` 또는 `FinalAnswer{reply}` → `[DONE]`

치명 오류는 어느 지점에서든 `ErrorRaised{error}` → `[DONE]`으로 끝난다(라우팅 전 `NOT_READY` 포함). `error`는 `{code, layer, recoverable, fatal, user_message, trace_id}`이고, 화면은 `user_message`를 보여 주며 `recoverable`이면 다시 시도 버튼을 둔다. 치명 아닌 오류(검색 일부 실패, 검수 저하)는 해당 이벤트의 `error`와 `notices`로만 알린다. REST 오류는 모두 `{error}` 본문 + 코드별 HTTP 상태(ADR-0012). SSE 응답은 `X-Accel-Buffering: no`·`Cache-Control: no-cache` 헤더를 붙이고, 프록시는 버퍼링 없이 전달한다.

카드는 구조화 출력이므로 토큰 스트리밍하지 않는다(단계 이벤트로 진행 표시, 카드는 한 번에 렌더링 — 트레이드오프로 기록).

## 6. 단위테스트 11개 (fake 모델, 네트워크 없음)

1. router intent → 노드 매핑
2. Reviewer의 금지 표현 regex가 LLM "통과" 판정이어도 위반을 잡음
3. 재시도 2회 초과 시 warning을 달고 approve로 진행
4. interrupt 후 승인 → 카드 저장
5. 거절 → 저장 안 됨
6. 그래프를 새로 빌드해도 체크포인트에서 승인 대기 복원 (재시작 시뮬레이션)
7. 복습 단계 전환 (안다 / 다시)
8. 준비 점검이 필수 항목 누락·개인정보 패턴 감지
9. `/api/profile` 잘못된 enum → 422 (`ErrorResponse`, `INPUT_INVALID`)
10. MCP 검색 timeout → 백오프 재시도 후 `ToolError` → 해당 검색만 실패 표시(`EvidenceSearched.error`)하고 카드는 생성, 영구 오류는 재시도 없이 즉시 실패 (A1)
11. 치명 오류 → 코드별 `ErrorRaised`(`LLM_OUTPUT_INVALID` 재시도 가능, `NOT_READY` 불가) 후 `[DONE]`, `/chat/resume` 승인 대기 없음 → 409 `NO_PENDING` (A3)

## 7. Before/After · 한계 측정 (G3, G4)

측정 조건: v1 = 10/13 CLI(`run_eval.py`), v2 = 신규 서버 HTTP API(자동 승인). 모델 `openai:gpt-4o-mini` 고정, 테스트셋 10건, 같은 날 실행, 지연은 3회 평균.

| 지표 | 예상 (가설) | 의미 |
|---|---|---|
| 라우팅 정확도, 구조화 출력 성공률, LLM-judge 맥락 점수 | 비슷 | 기능 후퇴 없음 |
| Tool 호출 수, 재작성 횟수 | 비교 | 검수 분리 효과 |
| 재시작 후 승인 대기 복원 | 0/N → N/N | 영속화 효과 |
| 동시 2요청 총 처리 시간 | 순차 → 병행 | async 효과 |
| 1건 평균 지연 | 증가 가능 | 한계로 보고 |

**실측 (2026-10-21, `eval/before_after.ipynb`)**: 카드 생성 v1 17/21 → v2 21/21, 라우팅 26/30 → 30/30, 개인 맥락 4.93 → 4.86(비슷), 성공 카드 지연 13.2 → 15.3초(증가), 카드당 검색 1.7 → 4.2회, 재시작 복원 0/3 → 3/3, 동시 2요청 28.4 → 14.5초. 테스트셋은 sample_user 기준 10건으로 바꿈(ADR-0009).

한계 4종:
1. MCP stdio 경유 오버헤드 (호출당 ms)
2. 체크포인트 DB가 대화 수에 따라 커지는 양
3. ollama 소형 모델의 구조화 출력 실패율 (vs OpenAI)
4. 단일 사용자 전제 + 외부 LLM으로 개인 서류 전송 (완화: ollama 선택지, 개인정보 검사). SQLite 체크포인터라 다중 인스턴스 간 상태 공유 불가 (강의 p.21은 PostgreSQL 채택 — ADR-0006)

## 8. 범위

- **포함**: §3, §4의 P0, §6, §7
- **P1**: 복습 퀴즈 + 간격 반복, LangSmith Dataset 업로드
- **제외**: Gemini 전용 백엔드, URL·PDF 공고 변환, 표현집·규칙 편집기(기본 파일 사용), 카드 검색·삭제, 다중 사용자, 카드 토큰 스트리밍, 테스트셋 확장
- **개인정보**: 시연·Git에는 `examples/sample_user`만 사용. 실제 서류가 들어가는 `data/`는 `.gitignore`

## 9. 일정 (위험도 높은 것부터)

| 시점 | 작업 | 완료 기준 |
|---|---|---|
| Day1 ~17시 | 스프레드시트 계획 등록 | §11 압축본 |
| Day1 저녁 | Deps, LLM 팩토리, 그래프(서브그래프 2개 + HITL), SQLite 체크포인터, 카드 store, fake로 테스트 1~7·10 | pytest 통과 (테스트 7·10은 CP1까지) |
| Day2 오전 | MCP 서버(RAG 포함) + 래퍼 Tool, **CP1(테스트 1~7)**, API 라우터, ollama 스모크 | curl E2E |
| Day2 오후 | 프론트 탭 ①②③ P0, 프록시, 테스트 8·9·11 | 브라우저 E2E |
| Day3 오전 | OpenAI 최종 확인, Before/After 노트북, README 캡처, PPT, 남으면 P1 | 13시 전 링크 등록 |

**컷 규칙**: Day2 오후까지 E2E가 안 되면 P1은 모두 버리고 측정·PPT를 우선한다.

## 10. 설계 검토 이력

5개 관점(채점위원 / AI 에이전트 아키텍트 / 프론트·풀스택 / QA·측정 / MVP·일정 PM)으로 검토.

| 관점 | 1차 | 2차 | 남은 의견 |
|---|---|---|---|
| 채점위원 | 78 | 97 | PPT 디자인 품질은 설계 단계에서 판단 불가 |
| 아키텍트 | 72 | 95 | Multi-Agent 규모는 작지만 역할 분리 근거 명확 |
| 프론트·풀스택 | 74 | 96 | 단일 사용자 전제 명시 |
| QA·측정 | 65 | 95 | LLM 비결정성 → 지연 3회 평균으로 보완 |
| PM | 68 | 97 | — |
| **평균** | 71.4 | **96.0** | |

1차 주요 지적과 반영: LLM 계층 불일치(→ LangChain 모델 통일), MCP ↔ create_agent 연결 미정(→ 래퍼 Tool), RAG 위치 미정(→ MCP 서버 내부), resume의 SSE POST 문제(→ JSON), 새로고침 복원 부재(→ `/chat/pending`), 범위 과다(→ §8 제외 목록), Before/After 조건 미정(→ §7 고정), 단위테스트 미확정(→ §6).

> 점수는 실제 구현이 아니라 설계 기준이며, §7의 예상치는 실측 전 가설이다.

## 11. 스프레드시트 등록용 압축본

**[주제]**
Interview Coach Agent — 내 경험·지원 공고를 근거로 영어 면접 표현을 만들고 복습까지 이어주는 웹 서비스

**[주요 기능]**
- 입력 준비(웹): 프로필·경험 문서·공고 입력, 준비 점검
- 생성·검수: 근거 검색(RAG) → 표현 카드·답변 초안 → 규칙 검수(최대 2회 재작성)
- 승인 후 저장(HITL): 웹에서 승인한 카드만 저장, 카드함·복습

**[개선 포인트]** (10/13 CLI 버전 대비)
- 서비스화: CLI → FastAPI·SSE·Vue 웹
- 기술 요소: Coach·Reviewer 멀티에이전트, MCP, 의존성 주입·모듈화, pytest, LangSmith
- 영속성: 승인 대기·카드를 SQLite에 저장, 재시작 후에도 유지
- Before/After: 같은 테스트셋·모델로 정확도·지연·호출 수·복원율 비교
