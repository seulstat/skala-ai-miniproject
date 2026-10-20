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
| [0006](0006-hitl-json-resume-pending.md) | HITL 재개는 JSON resume + pending 조회 | Accepted | 2026-10-20 | Lead | |
| [0007](0007-upload-filereader-json.md) | 문서 업로드는 FileReader → JSON | Accepted | 2026-10-20 | Lead | |
| [0008](0008-single-user-mvp-scope.md) | 단일 사용자 전제와 MVP 범위 컷 | Accepted | 2026-10-20 | Lead | |
| [0009](0009-before-after-conditions.md) | Before/After 측정 조건 고정 | Accepted | 2026-10-20 | Lead | |
| [0010](0010-roles-worktree-parallel.md) | 역할 분담과 worktree 병렬 진행 (테스트 7 → CP1) | Accepted | 2026-10-20 | Lead | |
| [0011](0011-deps-in-contracts.md) | Deps 정의를 contracts/deps.py로, 조립은 build_deps() | Accepted | 2026-10-20 | Lead | design 초안 "agent/deps.py에 Deps 정의"를 대체 |

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
