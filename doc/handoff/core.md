# core 인수인계 — 2026-10-21 (CP1 대상)

## 한 일
agent/ 전체(에이전트 코어)를 fake 모델·fake MCP·네트워크 없이 완성했다. design §6 테스트 1~7·10을
`tests/test_core_*.py`로 작성해 통과시켰고, `bash check.sh`는 FAIL 0이다.

1차 제출 후 Lead 리뷰 반영: `git merge main`(check.sh ⑥ 버그 수정 반영), Reviewer가 `deps.mcp.get_prompt`로
검수 규칙을 받도록 수정(ADR-0015 반려 반영), `agent/graph.py`를 200줄 이하로 분리.
2차 리뷰 반영: `get_prompt`가 돌려주는 값은 이미 렌더링된 system 프롬프트라, Reviewer가 `reviewer_prompt()`로
다시 감싸지 않고 그대로 system 메시지로 쓰도록 수정 (이중 지시문 방지).

- `agent/llm.py`: `FAST_MODEL`·`QUALITY_MODEL` → `init_chat_model`, `"fake"`면 `ToolCallingFakeChatModel`. LLM 예외 분류 함수
- `agent/deps.py`: `build_deps()` — Deps 조립 (단, MCP 연결은 A2 작업이 끝나야 실제로 동작, 아래 "요청" 참고)
- `agent/tools.py`: MCP 래퍼 `@tool` 3개. `with_retry` + `ToolError` 격리, `EvidenceSearched` 이벤트
- `agent/coach_agent.py`: Coach 서브그래프 (`create_agent` ReAct + `ToolStrategy(ExpressionCard)` + `ToolCallLimitMiddleware`)
- `agent/reviewer_agent.py`: Reviewer 서브그래프. `deps.mcp.get_prompt(PROMPT_PERSONA_REVIEW, {})`가 돌려주는
  값은 **이미 렌더링된 system 프롬프트**이므로 그대로 `("system", system_prompt)`로 써서 LLM 검수 +
  `banned_hits` 확정 검사를 한다 (ADR-0004). `agent/prompts.py::reviewer_prompt()`로 다시 감싸지 않는다 —
  감싸면 MCP 서버가 이미 넣은 지시문이 이중으로 들어간다. `get_prompt`의 `asyncio.TimeoutError`는 `with_retry`로
  재시도, 재시도 소진·치명 아닌 `ToolError`는 `REVIEWER_DEGRADED`로 강등(규칙 검사만), 치명(`MCP_UNAVAILABLE`)은
  그대로 전파한다. `deps.paths` 폴백은 없다.
- `agent/graph.py`: Supervisor 메인 그래프 (router → coach → reviewer ⟲2 → approve(interrupt) → save/rejected, review_cards, out_of_scope)
- `agent/routing.py`: 조건부 엣지 라우팅 함수 3개(`route_intent`·`route_review`·`route_approval`) + `NODE_BUMP_RETRY`.
  `graph.py`를 200줄 이하로 두려고 분리했다
- `agent/store.py`: `SQLiteCardStore` (coach.db, aiosqlite, 단계 0·1·2 = D+1·D+3·D+7)
- `agent/prompts.py`: 깨져 있던 `.config` import를 제거하고 `reviewer_prompt(persona_rules: str)`로 시그니처
  변경(파라미터화). 이 함수는 더 이상 `agent/reviewer_agent.py`가 부르지 않고 A2의 `mcp_server.py`가
  `persona_review_prompt` Prompt를 렌더링할 때 서버 쪽에서 쓴다 (Lead 2차 리뷰 반영)

## 파일·함수 위치
| 파일 | 함수/클래스 | 역할 |
|---|---|---|
| `agent/llm.py` | `ToolCallingFakeChatModel`, `make_llm`, `fast_llm_from_env`, `quality_llm_from_env`, `classify_llm_error` | LLM 팩토리·오류 분류 |
| `agent/tools.py` | `build_agent_tools`, `_call_with_retry` | MCP 래퍼 Tool 3개, timeout 재시도·격리 |
| `agent/coach_agent.py` | `build_coach_agent` | Coach 서브그래프 팩토리 (요청마다 새로 생성 — 프로필이 바뀔 수 있어서) |
| `agent/reviewer_agent.py` | `build_reviewer_agent`, `_review_node`, `_llm_review`, `card_text` | Reviewer 서브그래프. `_llm_review`가 get_prompt 재시도·강등 처리 |
| `agent/graph.py` | `build_graph`, `_router`·`_coach`·`_reviewer`·`_bump_retry`·`_approve`·`_save`·`_rejected`·`_review_cards`·`_out_of_scope` | Supervisor 노드 |
| `agent/routing.py` | `route_intent`·`route_review`·`route_approval`, `NODE_BUMP_RETRY` | Supervisor 조건부 엣지 |
| `agent/store.py` | `SQLiteCardStore` | CardStore 구현 |
| `agent/deps.py` | `build_deps`, `_build_mcp`, `_build_checkpointer` | Deps 조립 (서버 기동용, 테스트는 직접 Deps를 만들어 씀) |
| `tests/test_core_router.py` | 테스트 1 | router intent → 노드 매핑 |
| `tests/test_core_reviewer.py` | 테스트 2 | banned_hits가 LLM 통과 판정을 뒤집음, get_prompt 호출·system 프롬프트 반영, get_prompt timeout/fatal 처리, LLM 실패 시 강등 |
| `tests/test_core_graph.py` | 테스트 3·4·5·6 | 재작성 상한 경고, 승인 저장, 거절 미저장, 재시작 후 pending 복원 |
| `tests/test_core_store.py` | 테스트 7 | 복습 단계 전환 |
| `tests/test_core_tools.py` | 테스트 10 | timeout 재시도 후 격리, 영구 오류 즉시 격리, fatal은 전파 |

## 관련 ADR
[0001](../adr/0001-langchain-llm-fast-quality.md)·[0002](../adr/0002-mcp-wrapper-tools.md)·[0004](../adr/0004-coach-reviewer-multi-agent.md)·
[0005](../adr/0005-async-nodes.md)·[0011](../adr/0011-deps-in-contracts.md)·[0012](../adr/0012-error-handling-4layer.md)를 따랐다.
Proposed ADR 3개를 썼고 Lead 리뷰 결과는 다음과 같다:
- [0013](../adr/0013-fake-model-needs-bind-tools.md) — 승인. fake 모델에 `bind_tools` 추가가 필요했던 이유
- [0014](../adr/0014-explicit-writer-for-nested-subgraphs.md) — 승인. 중첩 서브그래프·Tool에 writer를 명시적으로 넘기는 이유
- [0015](../adr/0015-reviewer-persona-rules-via-paths-not-mcp-prompt.md) — **반려**. Reviewer는 ADR-0004·design §3대로
  MCP Prompt로 규칙을 받아야 하고, 지시서의 "deps.paths 기반" 문구가 Lead 쪽 오류였다. 파일은 Lead 요청대로
  삭제하지 않고 그대로 두었다(상태·색인 확정은 Lead가 CP1에서 한다). `agent/reviewer_agent.py`는 반려
  결정에 따라 `deps.mcp.get_prompt`를 쓰도록 되돌렸다.

## 사용한 계약 (contracts/)
`state.py`(AgentState·MAX_REWRITES·NODE_*·INTENT_TO_NODE), `deps.py`(Deps·MCPPort·CardStore·DataPaths),
`schemas.py`(ExpressionCard·ReviewResult·ApprovalRequest·SavedCard 등), `events.py`(RouteDecided~ErrorRaised,
`is_valid_sequence`로 테스트에서 순서 검증), `errors.py`(ERROR_CATALOG·CoachError·ToolError·RETRY_*),
`mcp_spec.py`(AGENT_TOOL_NAMES·PROMPT_PERSONA_REVIEW 등), `fixtures/`(card_express·review_passed/failed 등을
테스트에 재사용). 계약은 고치지 않았다.

## 테스트 결과 (check.sh, 자기 테스트)
```
bash check.sh
① ruff                PASS
② pytest(계약 제외)    20 passed
③ 계약 테스트          43 passed
④ 금지 파일·패턴       PASS
⑤ 소유권               PASS (변경 18개 모두 허용 경로)
⑥ 파일 길이            PASS (agent/graph.py 190줄로 줄었다)
⑦ 커밋 메시지          PASS
⑧ ADR                 PASS (색인 미등록 WARN — Lead가 CP에서 등록할 항목, 예상된 WARN)
결과: FAIL 0 · WARN 1
```
`.venv/bin/python -m pytest` 전체: 63 passed (계약 43 + core 20).

## 알려진 한계·미완료
- `agent/deps.py::_build_mcp`는 `agent/mcp_client.py`(A2 소유, 아직 Base 10/13 이전 상태 그대로)를 그대로 호출한다.
  지금 `agent/mcp_client.py`는 서버 2개("ops"/"docs")·`call_tool`이 dict 반환(JSON) 전제라
  `contracts.deps.MCPPort`(단일 서버 "coach", `call_tool`은 평문 str 반환) 계약과 맞지 않는다.
  A2가 작업을 마치기 전까지 `build_deps()`로 실제 MCP에 붙는 경로는 동작하지 않는다 — 의도된 상태다(설계상 CP1에
  A2 작업과 함께 맞춘다). 테스트는 전부 `Deps`를 직접 만들어 fake MCP로 돌렸다. `agent/reviewer_agent.py`가
  이제 `deps.mcp.get_prompt`를 실제로 호출하므로, A2의 `mcp_server.py`가 `persona_review_prompt`를
  **완성된 system 프롬프트**(이미 `reviewer_prompt(rules)`로 렌더링된 텍스트)로 돌려줘야 한다 — Agent는
  받은 문자열을 그대로 쓰고 추가로 감싸지 않는다.
- `/chat/pending` 복원(테스트 6)·interrupt·resume은 `AsyncSqliteSaver`로 실제 파일 기반 재현까지 확인했지만,
  실제 서버 프로세스 재시작 시나리오(A3 `/chat/pending` 엔드포인트)는 통합 전이라 그 경로 자체는 아직 없다.

## Lead·다른 역할에 대한 요청
1. **A2에게 전달**: `agent/mcp_client.py`가 `contracts.deps.MCPPort`와 맞으려면 (a) 서버 1개("coach")만
   쓰도록 단순화, (b) `call_tool`/`read_resource`/`get_prompt`가 `server` 인자 없이(또는 기본값으로) 동작,
   (c) `call_tool`이 `json.loads` 없이 MCP 결과 텍스트(`[출처 라벨]...`)를 그대로 돌려줘야 합니다.
   (d) `mcp_server.py`의 `persona_review_prompt`는 `agent/prompts.py::reviewer_prompt(rules)`로 **서버 쪽에서**
   완성된 system 프롬프트를 렌더링해 돌려줘야 합니다 — Reviewer(Agent)는 `get_prompt`가 돌려준 문자열을
   그대로 system 메시지로 쓰고 다시 감싸지 않습니다.
2. CP1에서 실제 MCP 서버가 붙으면 `tests/test_core_reviewer.py`의 fake `get_prompt` 응답 형식이 A2의 실제
   렌더링 결과와 맞는지 한 번 더 확인해 주세요.

## 발표 때 설명할 포인트 (3줄)
- Multi-Agent: Coach(ReAct Tool 선택)와 Reviewer(LLM+규칙)를 각각 컴파일된 서브그래프로 분리하고, Supervisor가 재작성 상한(2회)·승인을 통제한다
- 오류 격리: MCP timeout은 2회 백오프 재시도 후 그 검색만(또는 검수 규칙 조회만) 실패 처리해 진행을 계속하고, 영구 오류는 재시도 없이 즉시 격리, 치명 오류만 전파한다 (design §6 테스트 10, Reviewer get_prompt 테스트로 검증)
- 테스트 가능성: fake 모델이 `bind_tools`를 지원하도록 작게 확장하고, 이벤트 writer를 노드가 명시적으로 넘기는 구조로 만들어 네트워크 없이 그래프 전체를 단위테스트했다
