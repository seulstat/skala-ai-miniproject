# ADR-0015: Reviewer는 persona_rules를 deps.paths에서 직접 읽는다 (MCP Prompt 미사용) — Lead 확인 필요

- 상태: Proposed
- 날짜: 2026-10-20
- 작성: core
- 관련: design.md §3 "MCP" 행("Prompt 1"), ADR-0002·ADR-0004("Reviewer는 MCP Prompt persona_review_prompt로
  검수 규칙을 받고"), contracts/mcp_spec.py(PROMPT_PERSONA_REVIEW), work-plan.md §5 A1 지시서

## 배경
ADR-0002·0004는 Reviewer가 MCP Prompt `persona_review_prompt`로 검수 규칙을 받는다고 적었다.
반면 work-plan.md §5의 A1 작업 지시서(및 착수 프롬프트)는 "`agent/prompts.py`의 `.config` import(TODO)를
**deps.paths 기반으로** 바꾼다"라고 구체적으로 지시한다. `agent/prompts.py::reviewer_prompt()`는
원래 로컬 파일(`PERSONA_RULES_PATH`)을 읽는 함수였다. 두 문서가 "규칙 텍스트를 어디서 가져오는지"에
대해 서로 다른 경로(MCP vs 로컬 파일)를 가리키고 있어, 둘 다 만족시킬 수 없었다.

## 결정
지시서 문구를 따라 `reviewer_prompt(persona_rules: str)`로 시그니처만 바꾸고, Reviewer
서브그래프(`agent/reviewer_agent.py`)는 `deps.paths.persona_rules`를 직접 읽어 그 내용을 넘긴다.
`deps.mcp.get_prompt(mcp_spec.PROMPT_PERSONA_REVIEW, {})`는 호출하지 않는다.
A2의 MCP 서버가 완성되면 이 결정을 재검토해야 한다 — 특히 design §3 "MCP: Tool 2·Resource 1·**Prompt 1**"
항목이 "Agent가 실제로 Prompt를 호출한다"를 뜻한다면, 현재 구현은 이 기술 요소를 충족하지 못한다.

## 대안 비교
| 대안 | 장점 | 단점 | 기각 이유 |
|---|---|---|---|
| deps.paths.persona_rules 직접 읽기 (채택) | 지시서 문구와 정확히 일치, A2 MCP 서버 완성 전에도 바로 테스트 가능 | ADR-0002·0004의 "MCP Prompt로 받는다"와 어긋남, G2 "Prompt 1" 기술 요소가 코드상 미사용으로 남을 수 있음 | 지시서가 더 최신·구체적이라고 판단해 우선 채택 |
| deps.mcp.get_prompt(PROMPT_PERSONA_REVIEW, {}) 호출 | ADR-0002·0004·mcp_spec 설계와 일치, MCP Prompt 기술 요소 충족 | A2의 mcp_server.py·agent/mcp_client.py가 아직 스켈레톤이라 CP1 전에는 테스트 불가, 지시서 문구("deps.paths 기반")와 다름 | A1 단독 작업 범위에서 당장 검증 불가능 |
| 둘 다: 우선 deps.mcp.get_prompt 시도, 실패하면 deps.paths로 폴백 | 두 경로 모두 만족 | 복잡도 증가, "MCP 호출 실패를 정상 경로로 흡수"하는 모양이 되어 오류 분류(ADR-0012)와 겹침 | 과설계, 지금 결정할 필요 없음 — Lead 확인 후 정할 문제 |

## 결과
- 긍정: 당장 fake MCP·fake LLM만으로 design §6 테스트 2를 작성·통과할 수 있었다.
- 부정(트레이드오프): MCP Prompt(`persona_review_prompt`)가 Agent 쪽에서 미사용 상태로 남는다. CP1에서
  A2 MCP 서버가 준비되면 재논의가 필요하다.
- 후속 조치: Lead가 design §3 "Prompt 1"의 의도를 확인하고, 필요하면 이 ADR을 Accepted/Superseded로 확정하며
  reviewer_agent.py가 deps.mcp.get_prompt를 쓰도록 바꾸는 후속 작업을 A1(또는 CP1 이후 통합 작업)에 배정한다.
- 검증 방법: tests/test_core_reviewer.py (현재는 deps.paths 경로만 검증). MCP 경로로 바뀌면 fake MCP의
  get_prompt 반환값을 reviewer_prompt에 그대로 넣는 테스트로 교체.
