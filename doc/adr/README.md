# ADR 색인

"왜 이렇게 만들었나"의 기록. 고정 틀과 규칙은 [agent.md §9](../../agent.md), 운영은 [work-plan.md §8](../work-plan.md).
작업 전에 관련 ADR의 **대안 비교 표(기각된 대안)**를 확인한다. 기각된 대안으로 돌아가려면 새 근거를 담은 supersede ADR이 필요하다.

| 번호 | 제목 | 상태 | 날짜 | 작성 | 대체 관계 |
|---|---|---|---|---|---|
| [0001](0001-langchain-llm-fast-quality.md) | LLM 계층을 LangChain 모델로 통일하고 fast/quality 분리 | Accepted | 2026-10-20 | Lead | |
| [0002](0002-mcp-wrapper-tools.md) | MCP Tool을 create_agent에 래퍼 Tool로 연결 | Accepted | 2026-10-20 | Lead | |
| [0003](0003-rag-inside-mcp-server.md) | RAG를 MCP 서버 프로세스 안에 둔다 | Accepted | 2026-10-20 | Lead | |
| [0004](0004-coach-reviewer-multi-agent.md) | Coach·Reviewer 멀티에이전트로 전환 | Accepted | 2026-10-20 | Lead | supersedes 10/13 "단일 Agent + Reviewer 노드" |
| [0005](0005-async-nodes.md) | 모든 그래프 노드를 async로 | Accepted | 2026-10-20 | Lead | |
| [0006](0006-hitl-json-resume-pending.md) | HITL 재개는 JSON resume + pending 조회 | Accepted (일부 0012로 대체) | 2026-10-20 | Lead | |
| [0007](0007-upload-filereader-json.md) | 문서 업로드는 FileReader → JSON | Accepted | 2026-10-20 | Lead | |
| [0008](0008-single-user-mvp-scope.md) | 단일 사용자 전제와 MVP 범위 컷 | Accepted | 2026-10-20 | Lead | |
| [0009](0009-before-after-conditions.md) | Before/After 측정 조건 고정 | Accepted | 2026-10-20 | Lead | |
| [0010](0010-roles-worktree-parallel.md) | 역할 분담과 worktree 병렬 진행 (테스트 7 → CP1) | Accepted | 2026-10-20 | Lead | |
| [0011](0011-deps-in-contracts.md) | Deps 정의를 contracts/deps.py로, 조립은 build_deps() | Accepted | 2026-10-20 | Lead | design 초안 "agent/deps.py에 Deps 정의"를 대체 |
| [0012](0012-error-handling-4layer.md) | 오류 처리를 4계층 분류 + 재시도 가능 여부 + ErrorRaised 이벤트로 | Accepted | 2026-10-20 | Lead | 0006의 오류 처리 부분을 대체 |
| [0013](0013-fake-model-needs-bind-tools.md) | 테스트용 fake 모델에 bind_tools를 추가한 서브클래스 | Accepted | 2026-10-20 | core | ADR-0001 보완 |
| [0014](0014-explicit-writer-for-nested-subgraphs.md) | 중첩 서브그래프·Tool에는 바깥 노드가 writer를 넘긴다 | Accepted | 2026-10-20 | core | |
| [0015](0015-reviewer-persona-rules-via-paths-not-mcp-prompt.md) | Reviewer가 MCP Prompt 대신 paths로 규칙 읽기 | **Rejected** | 2026-10-20 | core | ADR-0004 유지 |
| [0016](0016-web-contract-gaps-rest-bodies-profile-404-proxy-error.md) | 웹 계약 보완: REST 응답 본문·프로필 404·BACKEND_UNAVAILABLE | Accepted | 2026-10-21 | web | |
| [0017](0017-api-drives-graph-turn-reset-lock-retry.md) | API가 새 턴 초기화·스레드 락·저장 재시도를 맡는다 | Accepted | 2026-10-21 | api | |
| [0018](0018-empty-structured-output-is-llm-output-invalid.md) | 빈 구조화 출력은 LLM_OUTPUT_INVALID | Accepted | 2026-10-21 | api | |
| [0019](0019-ollama-quality-model-qwen35-4b.md) | ollama 품질 모델을 qwen3.5:4b로 | Accepted | 2026-10-21 | Lead | |
| [0020](0020-ollama-thinking-off-posting-rule-fallback.md) | ollama thinking 끄기, 공고 정리 규칙 기반 대안, 복습 시 최근 카드 | Accepted | 2026-10-21 | Lead | |
| [0021](0021-per-tool-call-limits.md) | Coach 검색 상한은 '검색 Tool 숨기기'로 (무한 반복 수정) | Accepted | 2026-10-21 | Lead | |
| [0022](0022-eval-only-requirements.md) | 노트북 도구는 평가 전용 requirements-eval.txt로 | Accepted | 2026-10-21 | Lead | |

## design.md ↔ ADR 대응

| design.md | ADR |
|---|---|
| §2 LLM 계층, 모델 분리 | 0001 |
| §2 MCP ↔ create_agent | 0002 |
| §2 RAG 위치 | 0003 |
| §2 Multi-Agent | 0004 |
| §2 비동기 | 0005 |
| §2 HITL | 0006 |
| §2 업로드 | 0007 |
| §2 사용자, §8 범위 | 0008 |
| §7 Before/After | 0009 |
| §9 일정, work-plan §2·§6 | 0010 |
| §2 DI 위치, §3 DI | 0011 |
| §2 오류 처리, §5 ErrorRaised, §6 테스트 10·11 | 0012 |
