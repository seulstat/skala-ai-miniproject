# core 인수인계 — 2026-10-20 (CP1 대상)

## 한 일
agent/ 전체(에이전트 코어)를 fake 모델·fake MCP·네트워크 없이 완성했다. design §6 테스트 1~7·10을
`tests/test_core_*.py`로 작성해 통과시켰고, `bash check.sh`는 FAIL 0이다.

- `agent/llm.py`: `FAST_MODEL`·`QUALITY_MODEL` → `init_chat_model`, `"fake"`면 `ToolCallingFakeChatModel`. LLM 예외 분류 함수
- `agent/deps.py`: `build_deps()` — Deps 조립 (단, MCP 연결은 A2 작업이 끝나야 실제로 동작, 아래 "요청" 참고)
- `agent/tools.py`: MCP 래퍼 `@tool` 3개. `with_retry` + `ToolError` 격리, `EvidenceSearched` 이벤트
- `agent/coach_agent.py`: Coach 서브그래프 (`create_agent` ReAct + `ToolStrategy(ExpressionCard)` + `ToolCallLimitMiddleware`)
- `agent/reviewer_agent.py`: Reviewer 서브그래프 (LLM 검수 + `banned_hits` 확정 검사, LLM 실패 시 `REVIEWER_DEGRADED`로 강등)
- `agent/graph.py`: Supervisor 메인 그래프 (router → coach → reviewer ⟲2 → approve(interrupt) → save/rejected, review_cards, out_of_scope)
- `agent/store.py`: `SQLiteCardStore` (coach.db, aiosqlite, 단계 0·1·2 = D+1·D+3·D+7)
- `agent/prompts.py`: 깨져 있던 `.config` import를 제거하고 `reviewer_prompt(persona_rules: str)`로 시그니처 변경(파라미터화)

## 파일·함수 위치
| 파일 | 함수/클래스 | 역할 |
|---|---|---|
| `agent/llm.py` | `ToolCallingFakeChatModel`, `make_llm`, `fast_llm_from_env`, `quality_llm_from_env`, `classify_llm_error` | LLM 팩토리·오류 분류 |
| `agent/tools.py` | `build_agent_tools`, `_call_with_retry` | MCP 래퍼 Tool 3개, timeout 재시도·격리 |
| `agent/coach_agent.py` | `build_coach_agent` | Coach 서브그래프 팩토리 (요청마다 새로 생성 — 프로필이 바뀔 수 있어서) |
| `agent/reviewer_agent.py` | `build_reviewer_agent`, `_review_node`, `card_text` | Reviewer 서브그래프 |
| `agent/graph.py` | `build_graph`, `_router`·`_coach`·`_reviewer`·`_bump_retry`·`_approve`·`_save`·`_rejected`·`_review_cards`·`_out_of_scope`, `_route_intent`·`_route_review`·`_route_approval` | Supervisor 노드·라우팅 |
| `agent/store.py` | `SQLiteCardStore` | CardStore 구현 |
| `agent/deps.py` | `build_deps`, `_build_mcp`, `_build_checkpointer` | Deps 조립 (서버 기동용, 테스트는 직접 Deps를 만들어 씀) |
| `tests/test_core_router.py` | 테스트 1 | router intent → 노드 매핑 |
| `tests/test_core_reviewer.py` | 테스트 2 | banned_hits가 LLM 통과 판정을 뒤집음, LLM 실패 시 강등 |
| `tests/test_core_graph.py` | 테스트 3·4·5·6 | 재작성 상한 경고, 승인 저장, 거절 미저장, 재시작 후 pending 복원 |
| `tests/test_core_store.py` | 테스트 7 | 복습 단계 전환 |
| `tests/test_core_tools.py` | 테스트 10 | timeout 재시도 후 격리, 영구 오류 즉시 격리, fatal은 전파 |

## 관련 ADR
[0001](../adr/0001-langchain-llm-fast-quality.md)·[0002](../adr/0002-mcp-wrapper-tools.md)·[0004](../adr/0004-coach-reviewer-multi-agent.md)·
[0005](../adr/0005-async-nodes.md)·[0011](../adr/0011-deps-in-contracts.md)·[0012](../adr/0012-error-handling-4layer.md)를 따랐다.
새로 쓴 Proposed ADR 3개(Lead 확인 필요, 아래 "요청" 참고):
- [0013](../adr/0013-fake-model-needs-bind-tools.md) — fake 모델에 `bind_tools` 추가가 필요했던 이유
- [0014](../adr/0014-explicit-writer-for-nested-subgraphs.md) — 중첩 서브그래프·Tool에 writer를 명시적으로 넘기는 이유
- [0015](../adr/0015-reviewer-persona-rules-via-paths-not-mcp-prompt.md) — Reviewer가 MCP Prompt 대신 deps.paths를 쓴 이유 (design·지시서 불일치)

## 사용한 계약 (contracts/)
`state.py`(AgentState·MAX_REWRITES·NODE_*·INTENT_TO_NODE), `deps.py`(Deps·MCPPort·CardStore·DataPaths),
`schemas.py`(ExpressionCard·ReviewResult·ApprovalRequest·SavedCard 등), `events.py`(RouteDecided~ErrorRaised,
`is_valid_sequence`로 테스트에서 순서 검증), `errors.py`(ERROR_CATALOG·CoachError·ToolError·RETRY_*),
`mcp_spec.py`(AGENT_TOOL_NAMES 등), `fixtures/`(card_express·review_passed/failed 등을 테스트에 재사용).
계약은 고치지 않았다.

## 테스트 결과 (check.sh, 자기 테스트)
```
bash check.sh
① ruff                PASS
② pytest(계약 제외)    17 passed
③ 계약 테스트          43 passed
④ 금지 파일·패턴       PASS
⑤ 소유권               PASS (변경 16개 모두 허용 경로)
⑥ 파일 길이            PASS (단, 아래 "알려진 한계" 참고 — 이 항목 자체에 쉘 버그 있음)
⑦ 커밋 메시지          PASS
⑧ ADR                 PASS (색인 미등록 WARN — Lead가 CP에서 등록할 항목, 예상된 WARN)
결과: FAIL 0 · WARN 1
```
`.venv/bin/python -m pytest` 전체: 60 passed (계약 43 + core 17).

## 알려진 한계·미완료
- `agent/deps.py::_build_mcp`는 `agent/mcp_client.py`(A2 소유, 아직 Base 10/13 이전 상태 그대로)를 그대로 호출한다.
  지금 `agent/mcp_client.py`는 서버 2개("ops"/"docs")·`call_tool`이 dict 반환(JSON) 전제라
  `contracts.deps.MCPPort`(단일 서버 "coach", `call_tool`은 평문 str 반환) 계약과 맞지 않는다.
  A2가 작업을 마치기 전까지 `build_deps()`로 실제 MCP에 붙는 경로는 동작하지 않는다 — 의도된 상태다(설계상 CP1에
  A2 작업과 함께 맞춘다). 테스트는 전부 `Deps`를 직접 만들어 fake MCP로 돌렸다.
- `check.sh` ⑥(파일 길이 경고)에 버그가 있다 — line 93 `echo "$f ($n줄)"`에서 `set -u`인 상태로
  변수 뒤에 공백 없이 한글이 바로 붙으면(`$n줄`) bash가 변수 이름 경계를 잘못 잡아 `n: unbound variable`로
  죽는다(`bash -c 'set -u; n=206; echo "($n줄)"'`로 재현됨). 이 프로젝트에서 처음으로 200줄을 넘는
  파일(`agent/graph.py`, 206줄)이 생기면서 드러났다 — `main`에는 200줄 넘는 파일이 없어 지금까지 발현되지
  않았다. `pipefail` 때문에 `long` 변수가 빈 문자열이 되어 결과적으로 PASS로 보이지만 실제로는 경고를
  놓친다. Lead가 `echo "$f ($n줄)"`를 `echo "$f (${n}줄)"`로 바꾸면 해결된다.
  `agent/graph.py` 자체는 9개 노드 + 라우팅 3개 + build_graph를 한 파일에 둔 결과로 가이드라인(약 200줄)보다
  약간 길다 — Supervisor 전체 흐름을 한 곳에서 설명하려고 일부러 나누지 않았다. 나눌지는 Lead 판단 요청.
- `agent/reviewer_agent.py`는 `deps.mcp.get_prompt(PROMPT_PERSONA_REVIEW, ...)`를 쓰지 않는다 (ADR-0015).
- `/chat/pending` 복원(테스트 6)·interrupt·resume은 `AsyncSqliteSaver`로 실제 파일 기반 재현까지 확인했지만,
  실제 서버 프로세스 재시작 시나리오(A3 `/chat/pending` 엔드포인트)는 통합 전이라 그 경로 자체는 아직 없다.

## Lead·다른 역할에 대한 요청
1. **ADR-0013·0014·0015 검토**: 특히 0015 — design §3 "MCP: Prompt 1"이 "Agent가 실제로 호출"까지
   요구하는지 확인해 주세요. 요구한다면 CP1 이후 `reviewer_agent.py`를 `deps.mcp.get_prompt`로 바꾸는
   후속 작업이 필요합니다.
2. **A2에게 전달**: `agent/mcp_client.py`가 `contracts.deps.MCPPort`와 맞으려면 (a) 서버 1개("coach")만
   쓰도록 단순화, (b) `call_tool`/`read_resource`/`get_prompt`가 `server` 인자 없이(또는 기본값으로) 동작,
   (c) `call_tool`이 `json.loads` 없이 MCP 결과 텍스트(`[출처 라벨]...`)를 그대로 돌려줘야 합니다.
3. **check.sh ⑥ 버그 수정**: line 93 `echo "$f ($n줄)"` → `echo "$f (${n}줄)"` (위 "알려진 한계"에 재현 방법).
   FAIL은 아니라 진행에 막히진 않았지만, 지금은 200줄 초과 파일이 생겨도 조용히 PASS로 나옵니다.

## 발표 때 설명할 포인트 (3줄)
- Multi-Agent: Coach(ReAct Tool 선택)와 Reviewer(LLM+규칙)를 각각 컴파일된 서브그래프로 분리하고, Supervisor가 재작성 상한(2회)·승인을 통제한다
- 오류 격리: MCP timeout은 2회 백오프 재시도 후 그 검색만 실패 처리해 카드는 계속 만들고, 영구 오류는 재시도 없이 즉시 격리한다 (design §6 테스트 10으로 검증)
- 테스트 가능성: fake 모델이 `bind_tools`를 지원하도록 작게 확장하고, 이벤트 writer를 노드가 명시적으로 넘기는 구조로 만들어 네트워크 없이 그래프 전체를 단위테스트했다
