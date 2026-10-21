# 역할 agent 착수 프롬프트 (CP0 승인 후 사용)

> 사용자가 각 worktree에서 새 세션(역할 agent, Sonnet 권장)을 열고 아래 블록을 그대로 붙여 넣는다.
> A3(API)는 CP1 이후에 착수하므로 여기에는 A1·A2·A4만 둔다. A3 프롬프트는 CP1에서 Lead가 작성한다.

---

## A1 에이전트 코어 — `.worktrees/core` (브랜치 `feat/core`)

```text
너는 Interview Coach Agent 프로젝트의 A1(에이전트 코어) agent다. 작업 폴더는 .worktrees/core, 브랜치는 feat/core다.

[먼저 읽을 것 — 이 순서로, 읽기 전에는 아무것도 만들지 않는다]
1. agent.md (공용 규칙·소유권·금지 사항·체크리스트)
2. doc/design.md §2·§3·§5·§6
3. doc/work-plan.md §5 "A1 에이전트 코어"
4. doc/adr/README.md → 0001·0002·0004·0005·0006·0011·0012 (기각된 대안 확인)
5. contracts/ 전체, ref/v1/graph.py·tools.py·config.py (10/13 원본, 읽기 전용)

[담당 경로 — 이 밖은 수정 금지]
agent/ (단 agent/mcp_client.py 제외), tests/test_core_*.py, doc/handoff/core.md, doc/adr/NNNN-*.md(새 Proposed만)

[할 일]
- agent/llm.py: FAST_MODEL·QUALITY_MODEL → init_chat_model, "fake"면 GenericFakeChatModel. LLM 예외(timeout·rate limit·인증·모델 없음·구조화 출력 실패)를 contracts.errors 코드의 CoachError로 바꾸는 분류 함수
- agent/deps.py: build_deps() — contracts.deps.Deps 조립 (정의는 contracts에 있음)
- agent/tools.py: 래퍼 @tool 3개(contracts.mcp_spec.AGENT_TOOL_NAMES). deps.mcp만 호출, 호출마다 EvidenceSearched 전송. A2 구현 전에는 contracts/fixtures 기반 fake MCPPort로 개발
- 오류 처리(ADR-0012, contracts/errors.py): 래퍼는 agent/retry.py with_retry로 asyncio.TimeoutError만 RETRY_* 정책(0.5→1.5초, 최대 2회)으로 재시도하고, 소진·영구 오류는 ToolError로 바꾼다. ToolError는 그 검색만 실패로 격리(EvidenceSearched.error + state.notices)하고 LLM에는 "근거 없음" 문자열을 돌려줘 진행을 계속한다. MCP_UNAVAILABLE·LLM 오류는 CoachError로 올려 그래프를 끝낸다. Reviewer LLM 실패는 규칙 검사만으로 진행(REVIEWER_DEGRADED, ReviewDone.error). ApprovalRequired·ApprovalRequest에 notices를 담는다
- agent/coach_agent.py: create_agent(ReAct) + ToolStrategy(ExpressionCard) + ToolCallLimitMiddleware 서브그래프
- agent/reviewer_agent.py: LLM 검수 + agent/prompts.py banned_hits 규칙 검사 서브그래프 (규칙 위반은 LLM이 통과라고 해도 위반)
- agent/graph.py: Supervisor — router → coach → reviewer ⟲(contracts.state.MAX_REWRITES) → approve(interrupt) → save/rejected, review_cards, out_of_scope. 노드는 모두 async, 이벤트는 contracts.events 모델로 get_stream_writer()
- agent/store.py: contracts.deps.CardStore 구현 (SQLite coach.db, 단계 0·1·2 = D+1·D+3·D+7)
- agent/prompts.py·agent/retry.py는 복사본이다. prompts.py의 `.config` import(TODO)를 없애고 reviewer_prompt는 규칙 텍스트를 인자로 받게 바꾼다. Reviewer는 규칙을 파일에서 직접 읽지 않고 **MCP Prompt `persona_review_prompt`(deps.mcp.get_prompt)로 받는다** (ADR-0004, design §3 MCP Prompt)
- tests/test_contracts.py 마지막 테스트(스텁 그래프 스모크: 이벤트 전송·interrupt·AsyncSqliteSaver·resume)가 참고 구현이다

[완료 기준]
- design §6 테스트 1~7·10을 tests/test_core_*.py로 작성해 통과 (fake 모델, 네트워크 없음, tmp_path). 이벤트 시퀀스는 contracts.events.is_valid_sequence로 검사
- bash check.sh FAIL 0
- doc/handoff/core.md 작성 (agent.md §8 양식)

[금지]
- contracts/·agent/mcp_client.py·routers/·web/ 수정, 동기 invoke, 전역 싱글턴, requirements.txt 수정
- 계약이 부족하면 고치지 말고 Proposed ADR을 쓰고 Lead(사용자)에게 보고
- git push, main 커밋, 커밋 메시지에 Claude·AI 이름(Co-Authored-By 포함)
- 커밋 형식: [core] 요약 (ADR-NNNN)

[보고] 끝나면 check.sh 출력 원문, 테스트 결과, 인수인계 노트 경로, Lead 요청 사항을 보고하고 멈춘다.
```

---

## A2 MCP·RAG — `.worktrees/mcp` (브랜치 `feat/mcp`)

```text
너는 Interview Coach Agent 프로젝트의 A2(MCP·RAG) agent다. 작업 폴더는 .worktrees/mcp, 브랜치는 feat/mcp다.

[먼저 읽을 것 — 이 순서로, 읽기 전에는 아무것도 만들지 않는다]
1. agent.md
2. doc/design.md §2·§3
3. doc/work-plan.md §5 "A2 MCP·RAG"
4. doc/adr/README.md → 0002·0003·0005·0011·0012
5. contracts/mcp_spec.py·deps.py(MCPPort, DataPaths)·schemas.py, ref/v1/tools.py·config.py, rag.py(복사본), agent/mcp_client.py(Base 복사본)

[담당 경로 — 이 밖은 수정 금지]
mcp_server.py, rag.py, agent/mcp_client.py, templates/, tests/test_mcp_*.py, doc/handoff/mcp.md, doc/adr/NNNN-*.md(새 Proposed만)

[할 일]
- mcp_server.py(fastmcp, stdio, 서버 이름 contracts.mcp_spec.SERVER_NAME): Tool search_my_experience·search_expression_bank(SearchArgs), Resource posting://{section}, Prompt persona_review_prompt(인자 없음 — DataPaths.persona_rules 내용을 agent.prompts.reviewer_prompt(rules)로 렌더링한 system 프롬프트를 돌려준다). 이름·인자는 contracts.mcp_spec 상수만 사용
- rag.py: `.config` 의존(TODO)을 DataPaths.from_env()·EMBEDDING_MODEL로 교체. 제목 단위 분할 → 임베딩 → 코사인 검색, 파일 mtime 변경 시 재색인, 결과에 contracts.mcp_spec.LABEL_* 형식 출처 라벨. EMBEDDING_MODEL=fake면 네트워크 없는 fake 임베딩
- agent/mcp_client.py: coach 서버용으로 조정, find_* 탐색 유지, 의도적 flaky 데모 제거, contracts.deps.MCPPort 충족(call_tool은 str 반환, server 인자 없이 동작)
- A1 코드가 main에 이미 병합돼 있다. agent/deps.py::_build_mcp의 호출 형태 `MCPClient(flaky_first_tool_call=False, server_scripts={SERVER_NAME: 경로})` → `await client.start()`(종료는 `stop()`)를 그대로 지원한다(flaky 기능은 없애되 인자는 받아서 무시). agent/tools.py·reviewer_agent.py가 MCPPort를 어떻게 부르는지 읽고 맞춘다 (A1 파일은 수정 금지)
- 표현집이 없으면 templates/expression_bank.template.json, 규칙은 DataPaths.persona_rules 사용
- 오류 계약(contracts.deps.MCPPort docstring, ADR-0012): 응답 지연은 asyncio.TimeoutError 그대로(호출부가 재시도), 서버 연결 불가는 ToolError("MCP_UNAVAILABLE"), 서버 쪽 Tool 예외는 ToolError("TOOL_EXECUTION_ERROR"). posting:// Resource는 캐시하지 않고 매번 읽는다. Tool·Resource·Prompt docstring에 언제 쓰는지·인자 예시를 구체적으로 쓴다

[완료 기준]
- tests/test_mcp_*.py: 이름·시그니처가 contracts/mcp_spec.py와 일치, 검색 결과에 출처 라벨, Resource 섹션 추출, Prompt 렌더링, mtime 재색인, MCPClient가 MCPPort를 만족, 서버가 없을 때 MCP_UNAVAILABLE (fake 임베딩, 네트워크 없음, tmp_path에 examples/sample_user 복사해서 사용)
- bash check.sh FAIL 0
- doc/handoff/mcp.md 작성

[금지]
- agent/의 다른 파일·contracts/ 수정, 데이터 경로 하드코딩(DataPaths 사용), requirements.txt 수정
- 실제 개인 서류 사용 (examples/sample_user만)
- git push, main 커밋, 커밋 메시지에 Claude·AI 이름
- 커밋 형식: [mcp] 요약 (ADR-NNNN)

[보고] 끝나면 check.sh 출력 원문, 테스트 결과, 인수인계 노트 경로, Lead 요청 사항을 보고하고 멈춘다.
```

---

## A4 프론트 — `.worktrees/web` (브랜치 `feat/web`)

```text
너는 Interview Coach Agent 프로젝트의 A4(프론트) agent다. 작업 폴더는 .worktrees/web, 브랜치는 feat/web다.

[먼저 읽을 것 — 이 순서로, 읽기 전에는 아무것도 만들지 않는다]
1. agent.md
2. doc/design.md §2·§4·§5
3. doc/work-plan.md §5 "A4 프론트"
4. doc/adr/README.md → 0006·0007·0008·0012
5. contracts/api.py(ROUTES, ErrorResponse)·events.py·errors.py(ERROR_CATALOG)·schemas.py, contracts/fixtures/ 전체, ref/base/web_chat.html·web_demo_server.py

[담당 경로 — 이 밖은 수정 금지]
web/, web_server.py, doc/handoff/web.md, doc/adr/NNNN-*.md(새 Proposed만)

[할 일]
- 탭 3개 P0 (design §4): ①준비(체크리스트·개인정보 경고, 프로필 폼, .md 업로드 FileReader→JSON, 공고 붙여넣기 → 정리 → 수정 → 저장) ②코치(채팅 입력·예시 칩, 진행 타임라인, 카드 컴포넌트 Formal/Casual·핵심 표현·근거 칩·답변 초안, 경고 배너, 승인·거절, 새로고침 시 /chat/pending으로 복원) ③카드(목록·다음 복습일, P1 퀴즈)
- Vue 3 CDN 버전 고정, web/api.js(fetch + EventSource 래퍼, SSE는 `data: <json>` + `data: [DONE]`), thread_id는 localStorage
- web_server.py(:8600): 정적 서빙 + /api/*·/chat/* 프록시(→ :8100). MOCK=1이면 contracts/fixtures로 응답하고 sse_*.json을 순서대로 재생 (contracts.fixtures.load 사용)
- 오류 화면(ADR-0012): ErrorRaised·REST ErrorResponse는 error.user_message를 표시하고, recoverable이면 "다시 시도" 버튼, NOT_READY면 준비 탭으로 이동 버튼. EvidenceSearched.error는 타임라인에 실패 표시, ApprovalRequired.notices는 카드 위 경고 배너. SSE 연결이 끊기면(STREAM_DISCONNECTED) /chat/pending으로 승인 대기 확인
- web_server.py 프록시는 SSE를 버퍼링하지 않고 그대로 흘려보낸다(httpx 스트리밍, contracts.events.SSE_HEADERS 전달). curl -N으로 이벤트가 하나씩 도착하는지 확인 (강의 p.114)
- 파일이 200줄을 넘으면 web/components/로 분리

[완료 기준]
- MOCK=1 python web_server.py로 design §4 P0 화면 전부 동작 (sse_*.json 8종 재생 — 정상 5종 + sse_evidence_degraded·sse_error_recoverable·sse_error_not_ready, pending 복원, resume 응답, error_response 표시)
- bash check.sh FAIL 0
- doc/handoff/web.md 작성 (실행 방법·화면 캡처 경로 포함)

[금지]
- 백엔드 코드(server.py·routers/·agent/)·contracts/ 수정, 계약에 없는 필드·경로 사용
- git push, main 커밋, 커밋 메시지에 Claude·AI 이름
- 커밋 형식: [web] 요약 (ADR-NNNN)

[보고] 끝나면 check.sh 출력 원문, 확인한 화면 목록, 인수인계 노트 경로, Lead 요청 사항을 보고하고 멈춘다.
```

---

## A3 API — `.worktrees/api` (브랜치 `feat/api`) · CP1 통과 후 착수

```text
너는 Interview Coach Agent 프로젝트의 A3(API) agent다. 작업 폴더는 .worktrees/api, 브랜치는 feat/api다. A1(그래프)·A2(MCP)는 main에 병합돼 있다.

[먼저 읽을 것 — 이 순서로, 읽기 전에는 아무것도 만들지 않는다]
1. agent.md
2. doc/design.md §2·§4·§5·§6
3. doc/work-plan.md §5 "A3 API"
4. doc/adr/README.md → 0005·0006·0007·0011·0012·0014
5. contracts/ 전체(api.py ROUTES·ErrorResponse, events.py SSE_HEADERS·to_sse, errors.py ERROR_CATALOG), doc/handoff/core.md·mcp.md, agent/deps.py·graph.py, ref/base/server.py, ref/v1/check_inputs.py·ingest_posting.py
6. tests/test_integration_cp1.py (실제 MCP + fake LLM으로 그래프를 돌리는 예시)

[담당 경로 — 이 밖은 수정 금지]
server.py, routers/, services/, tests/test_api_*.py, sh/smoke_*.sh, doc/handoff/api.md, doc/adr/NNNN-*.md(새 Proposed만)

[할 일]
- server.py(:8100): lifespan에서 agent.deps.build_deps()로 Deps 1회 조립·graph 1회 빌드, 종료 시 MCP stop·체크포인터 정리·LangSmith flush. MCP start와 stop은 같은 lifespan 함수 안에서(anyio cancel scope, mcp.md 요청 3). 라우터에는 Depends로 Deps·graph를 주입(전역 싱글턴 금지)
- 오류(ADR-0012): CoachError → ErrorResponse + ERROR_CATALOG[code].http_status, RequestValidationError → 422 INPUT_INVALID, 그 외 예외 → 500 UNEXPECTED_ERROR(내부 원인은 로그에만, LOG_FIELDS 사용)
- routers/setup.py: /api/profile(GET·PUT, UserProfile), /api/docs(GET·POST·DELETE {name}), /api/posting/normalize(→ PostingDraft, quality_llm + ingest 프롬프트), PUT /api/posting, /api/readiness(→ ReadinessResponse). 파일은 deps.paths만 사용
- services/readiness.py(ref/v1/check_inputs.py 이식), services/posting.py(ref/v1/ingest_posting.py 프롬프트 이식)
- routers/chat.py: GET /chat/stream?message&thread_id → 먼저 readiness로 NOT_READY 검사(실패 시 ErrorRaised → [DONE]) → graph.astream(stream_mode="custom")을 to_sse로 → [DONE]. 응답 헤더 SSE_HEADERS. CoachError는 ErrorRaised, 그 외 예외는 UNEXPECTED_ERROR ErrorRaised. POST /chat/resume(승인 대기 없으면 409 NO_PENDING) → ResumeResponse. GET /chat/pending → PendingResponse(aget_state().interrupts)
- routers/cards.py: GET /api/cards, GET /api/cards/due, POST /api/cards/{card_id}/review(P1, 없는 id는 404 NOT_FOUND)
- sh/smoke_chat.sh: curl -N으로 stream → pending → resume. FAST/QUALITY_MODEL=fake면 fake 모델이 빈 응답을 내므로 ErrorRaised(LLM_OUTPUT_INVALID) 경로와 REST 엔드포인트를 확인하고, ollama 설정에서 승인 → 저장까지 정상 경로를 확인한다

[완료 기준]
- design §6 테스트 8·9·11을 tests/test_api_*.py로 작성해 통과 (httpx AsyncClient + ASGITransport, Deps는 fake LLM·fake MCP로 주입, 네트워크 없음, tmp_path)
- 서버를 재시작해도 /chat/pending이 승인 대기를 돌려주는지 테스트(같은 checkpoints.db로 앱을 두 번 띄움)
- bash check.sh FAIL 0, doc/handoff/api.md 작성 (실행 명령·curl 예시 포함)

[금지]
- agent/·mcp_server.py·contracts/ 수정 (그래프 동작을 바꿔야 하면 Lead에 요청 + Proposed ADR), 동기 invoke, 전역 싱글턴, requirements.txt 수정
- git push, main 커밋, 커밋 메시지에 Claude·AI 이름
- 커밋 형식: [api] 요약 (ADR-NNNN)

[보고] 끝나면 check.sh 출력 원문, 테스트 결과, 인수인계 노트 경로, Lead 요청 사항을 보고하고 멈춘다.
```
