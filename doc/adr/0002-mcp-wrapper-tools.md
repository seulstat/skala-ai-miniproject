# ADR-0002: MCP Tool을 create_agent에 래퍼 Tool로 연결

- 상태: Accepted
- 날짜: 2026-10-20
- 작성: Lead
- 관련: design.md §2 "MCP ↔ create_agent", §3 MCP 행, contracts/mcp_spec.py

## 배경
평가 기준에 MCP가 있고, Base에는 서버를 이름으로 찾는 `MCPClient`(`find_*`, `_attr`)가 있다.
Coach는 10/13처럼 `create_agent`(ReAct)가 Tool을 고르는 구조를 유지해야 한다. 이 둘을 어떻게 잇는지 정해지지 않았었다.
화면 타임라인에는 Tool 호출마다 `EvidenceSearched{tool, query}` 이벤트가 필요하다.

## 결정
Agent에는 얇은 LangChain `@tool` 래퍼 3개(`search_my_experience`·`search_expression_bank`·`get_job_posting`)만 노출한다.
래퍼는 `deps.mcp`(MCPPort)의 `call_tool`·`read_resource`를 호출하고 `EvidenceSearched` 이벤트를 보낸다. 이름·인자는 `contracts/mcp_spec.py` 상수로 고정한다.

## 대안 비교
| 대안 | 장점 | 단점 | 기각 이유 |
|---|---|---|---|
| `langchain-mcp-adapters`의 `MultiServerMCPClient.get_tools()` (강의자료 p.67) | 설정 dict 하나로 Tool 일괄 변환, 다중 서버 병합 | `get_tools()`는 **Tool만** 가져와 Resource(`posting://`)·Prompt(`persona_review_prompt`)는 따로 호출해야 함, 의존성 추가, Tool 호출마다 `EvidenceSearched`·재시도·ToolError 변환을 끼워 넣기 어려움, Base `find_*` 재사용 못 함 | 서버가 하나이고 Resource·Prompt까지 써야 하므로 래퍼가 더 단순 |
| MCP 없이 Python 함수 직접 호출(10/13) | 가장 빠름 | MCP 요구사항 미충족 | 평가 기준 미충족 |
| Coach가 MCP 클라이언트를 직접 소유 | 래퍼 불필요 | Agent 코드가 MCP 세부에 묶이고 fake로 대체하기 어려움 | DI·테스트 용이성 저하 |

## 결과
- 긍정: Agent 코드는 10/13과 같은 형태로 남는다. 테스트에서는 fixture 기반 fake MCPPort로 대체할 수 있다. Tool 호출이 이벤트·trace로 바로 보인다.
- 부정(트레이드오프): stdio 왕복 오버헤드가 생긴다(design §7 한계 1). 래퍼와 서버의 Tool 설명이 따로 관리된다.
- 후속 조치: A1은 `agent/tools.py`, A2는 `mcp_server.py`·`agent/mcp_client.py`를 구현한다. Before/After에서 호출당 ms를 측정한다.
- 검증 방법: `tests/test_contracts.py`의 MCP 이름 검사, A2 `test_mcp_*`의 이름·시그니처 일치 검사, CP1 실제 MCP 서버 E2E.
