"""design §6 테스트 2 — Reviewer의 banned_hits 확정 검사는 LLM이 통과라고 해도 위반을 잡는다.

Reviewer는 검수 규칙을 MCP Prompt persona_review_prompt로 받는다 (ADR-0004, Lead 반려: ADR-0015 폐기).
"""

import asyncio
import functools

import pytest
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from agent.graph import _reviewer
from agent.llm import ToolCallingFakeChatModel
from contracts import mcp_spec, schemas
from contracts.deps import DataPaths, Deps
from contracts.errors import RETRY_MAX, ToolError
from contracts.fixtures import load
from contracts.state import AgentState


def _review_tool_call(passed: bool, cid: str = "c1") -> AIMessage:
    payload = {"passed": passed, "violations": [], "feedback": "ok" if passed else "다시 쓰세요"}
    return AIMessage(content="", tool_calls=[{"name": "ReviewResult", "args": payload, "id": cid}])


class _FakeMCP:
    """get_prompt 호출 인자를 기록해 Reviewer가 올바른 이름으로 호출하는지 검증한다."""

    def __init__(self, prompt_text: str = "검수 규칙"):
        self.prompt_text = prompt_text
        self.get_prompt_calls: list[tuple[str, dict]] = []

    async def call_tool(self, name, arguments):
        return "[ok]"

    async def read_resource(self, uri):
        return "[ok]"

    async def get_prompt(self, name, arguments):
        self.get_prompt_calls.append((name, arguments))
        return self.prompt_text


class _RecordingLLM:
    """quality_llm 역할. 실제로 받은 system 메시지를 기록하고 고정된 ReviewResult를 돌려준다."""

    def __init__(self, result: schemas.ReviewResult):
        self._result = result
        self.received_system: str | None = None

    def with_structured_output(self, schema):
        parent = self

        class _Structured:
            async def ainvoke(self, messages):
                parent.received_system = messages[0][1]
                return parent._result

        return _Structured()


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


async def test_reviewer_fetches_persona_review_prompt_and_uses_it_as_system_message(data_paths: DataPaths):
    card = load("card_express.json")
    mcp = _FakeMCP(prompt_text="페르소나 규칙 본문")
    quality_llm = _RecordingLLM(schemas.ReviewResult(passed=True, violations=[], feedback="ok"))
    deps = Deps(fast_llm=quality_llm, quality_llm=quality_llm, mcp=mcp, store=None,
                checkpointer=None, paths=data_paths)

    final, _ = await _run_reviewer(deps, card)

    assert mcp.get_prompt_calls == [(mcp_spec.PROMPT_PERSONA_REVIEW, {})]
    assert quality_llm.received_system is not None
    assert "페르소나 규칙 본문" in quality_llm.received_system
    assert final["review"]["passed"] is True


async def test_get_prompt_timeout_retries_then_degrades_without_calling_llm(data_paths: DataPaths):
    class _TimeoutMCP:
        def __init__(self):
            self.calls = 0

        async def call_tool(self, name, arguments):
            return "[ok]"

        async def read_resource(self, uri):
            return "[ok]"

        async def get_prompt(self, name, arguments):
            self.calls += 1
            raise asyncio.TimeoutError("slow")

    mcp = _TimeoutMCP()
    card = load("card_express.json")
    # LLM이 실제로 호출되면 큐가 비어 StopIteration이 나므로, 호출되지 않았음을 이 큐로도 검증한다.
    quality_llm = ToolCallingFakeChatModel(messages=iter([]))
    deps = Deps(fast_llm=quality_llm, quality_llm=quality_llm, mcp=mcp, store=None,
                checkpointer=None, paths=data_paths)

    final, events_got = await _run_reviewer(deps, card)

    assert mcp.calls == RETRY_MAX + 1  # 최초 1회 + 재시도 2회
    assert final["review"]["passed"] is True  # 규칙 위반도 없으니 강등 상태로 통과
    review_done = next(e for e in events_got if e["type"] == "ReviewDone")
    assert review_done["error"]["code"] == "REVIEWER_DEGRADED"
    assert review_done["error"]["fatal"] is False


async def test_get_prompt_mcp_unavailable_propagates_as_fatal(data_paths: DataPaths):
    class _FatalMCP:
        async def call_tool(self, name, arguments):
            return "[ok]"

        async def read_resource(self, uri):
            return "[ok]"

        async def get_prompt(self, name, arguments):
            raise ToolError("MCP_UNAVAILABLE", tool_name=name, detail="connection refused")

    card = load("card_express.json")
    deps = Deps(fast_llm=None, quality_llm=None, mcp=_FatalMCP(), store=None,
                checkpointer=None, paths=data_paths)

    with pytest.raises(ToolError) as exc_info:
        await _run_reviewer(deps, card)
    assert exc_info.value.info.code == "MCP_UNAVAILABLE"


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
