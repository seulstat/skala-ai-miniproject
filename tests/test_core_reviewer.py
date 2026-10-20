"""design §6 테스트 2 — Reviewer의 banned_hits 확정 검사는 LLM이 통과라고 해도 위반을 잡는다."""

import functools

from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from agent.graph import _reviewer
from agent.llm import ToolCallingFakeChatModel
from contracts.deps import DataPaths, Deps
from contracts.fixtures import load
from contracts.state import AgentState


def _review_tool_call(passed: bool, cid: str = "c1") -> AIMessage:
    payload = {"passed": passed, "violations": [], "feedback": "ok" if passed else "다시 쓰세요"}
    return AIMessage(content="", tool_calls=[{"name": "ReviewResult", "args": payload, "id": cid}])


class _FakeMCP:
    async def call_tool(self, name, arguments):
        return "[ok]"

    async def read_resource(self, uri):
        return "[ok]"

    async def get_prompt(self, name, arguments):
        return "검수 규칙"


async def _run_reviewer(deps, card: dict, retry_count: int = 0) -> tuple[dict, list]:
    g = StateGraph(AgentState)
    g.add_node("reviewer", functools.partial(_reviewer, deps=deps))
    g.add_edge(START, "reviewer")
    g.add_edge("reviewer", END)
    graph = g.compile(checkpointer=InMemorySaver())
    cfg = {"configurable": {"thread_id": "t"}}
    events_got = [
        e async for e in graph.astream({"card": card, "retry_count": retry_count}, cfg, stream_mode="custom")
    ]
    final = await graph.aget_state(cfg)
    return final.values, events_got


async def test_llm_pass_is_overridden_by_banned_pattern(data_paths: DataPaths):
    card = load("card_express.json") | {
        "formal_expression": "I persuaded them to change the plan.",  # R3 금지 패턴 포함
    }
    quality_llm = ToolCallingFakeChatModel(messages=iter([_review_tool_call(passed=True)]))
    deps = Deps(fast_llm=quality_llm, quality_llm=quality_llm, mcp=_FakeMCP(), store=None,
                checkpointer=None, paths=data_paths)

    final, events_got = await _run_reviewer(deps, card)

    assert final["review"]["passed"] is False
    assert any(v["rule_id"] == "R3" for v in final["review"]["violations"])
    review_done = next(e for e in events_got if e["type"] == "ReviewDone")
    assert review_done["passed"] is False
    assert review_done["error"] is None  # LLM 호출 자체는 성공했다


async def test_llm_pass_and_no_banned_pattern_passes(data_paths: DataPaths):
    card = load("card_express.json")
    quality_llm = ToolCallingFakeChatModel(messages=iter([_review_tool_call(passed=True)]))
    deps = Deps(fast_llm=quality_llm, quality_llm=quality_llm, mcp=_FakeMCP(), store=None,
                checkpointer=None, paths=data_paths)

    final, _ = await _run_reviewer(deps, card)

    assert final["review"]["passed"] is True


async def test_llm_failure_degrades_to_rule_check_only(data_paths: DataPaths):
    card = load("card_express.json") | {"formal_expression": "I persuaded them."}

    class _BrokenLLM:
        def with_structured_output(self, schema):
            raise RuntimeError("구조화 출력 실패")

    deps = Deps(fast_llm=_BrokenLLM(), quality_llm=_BrokenLLM(), mcp=_FakeMCP(), store=None,
                checkpointer=None, paths=data_paths)

    final, events_got = await _run_reviewer(deps, card)

    assert final["review"]["passed"] is False  # banned_hits 위반은 여전히 잡힌다
    review_done = next(e for e in events_got if e["type"] == "ReviewDone")
    assert review_done["error"]["code"] == "REVIEWER_DEGRADED"
    assert review_done["error"]["fatal"] is False
