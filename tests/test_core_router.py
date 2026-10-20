"""design §6 테스트 1 — router intent → 노드 매핑."""

import functools
from typing import get_args

import pytest
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from agent.graph import _route_intent, _router
from agent.llm import ToolCallingFakeChatModel
from contracts.deps import Deps
from contracts.schemas import Intent
from contracts.state import INTENT_TO_NODE, NODE_COACH, NODE_OUT_OF_SCOPE, NODE_REVIEW_CARDS, AgentState


def _route_tool_call(intent: str) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": "Route", "args": {"intent": intent, "reason": "r"}, "id": "c1"}])


async def _run_router(deps, user_input: str) -> dict:
    """router 노드는 get_stream_writer()를 쓰므로 실제 그래프 실행 안에서 호출해야 한다."""
    g = StateGraph(AgentState)
    g.add_node("router", functools.partial(_router, deps=deps))
    g.add_edge(START, "router")
    g.add_edge("router", END)
    graph = g.compile(checkpointer=InMemorySaver())
    cfg = {"configurable": {"thread_id": "t"}}
    return await graph.ainvoke({"user_input": user_input}, cfg)


@pytest.mark.parametrize("intent", get_args(Intent))
async def test_router_sets_intent_from_llm_and_maps_to_expected_node(intent):
    fast_llm = ToolCallingFakeChatModel(messages=iter([_route_tool_call(intent)]))
    deps = Deps(fast_llm=fast_llm, quality_llm=fast_llm, mcp=None, store=None, checkpointer=None, paths=None)

    final_state = await _run_router(deps, "아무 입력")

    assert final_state["intent"] == intent
    assert final_state["retry_count"] == 0
    assert _route_intent(final_state) == INTENT_TO_NODE[intent]


def test_node_mapping_matches_design():
    assert INTENT_TO_NODE["express"] == NODE_COACH
    assert INTENT_TO_NODE["answer"] == NODE_COACH
    assert INTENT_TO_NODE["review"] == NODE_REVIEW_CARDS
    assert INTENT_TO_NODE["out_of_scope"] == NODE_OUT_OF_SCOPE
    assert _route_intent({"intent": "모르는의도"}) == NODE_OUT_OF_SCOPE
