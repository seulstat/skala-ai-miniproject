"""design §6 테스트 10 — MCP 검색 timeout은 백오프 재시도 후 ToolError로 격리하고 카드는 계속 생성한다.
영구 오류는 재시도 없이 즉시 그 검색만 실패 처리한다. fatal(MCP_UNAVAILABLE)은 그대로 올라온다.
"""

import asyncio

import pytest

from agent.tools import build_agent_tools
from contracts.deps import Deps
from contracts.errors import RETRY_MAX, ToolError


class _TimeoutMCP:
    def __init__(self):
        self.calls = 0

    async def call_tool(self, name, arguments):
        self.calls += 1
        raise asyncio.TimeoutError("slow")

    async def read_resource(self, uri):
        return "[ok]"

    async def get_prompt(self, name, arguments):
        return "p"


class _PermanentErrorMCP:
    def __init__(self):
        self.calls = 0

    async def call_tool(self, name, arguments):
        self.calls += 1
        raise ToolError("TOOL_EXECUTION_ERROR", tool_name=name, detail="bad response")

    async def read_resource(self, uri):
        return "[ok]"

    async def get_prompt(self, name, arguments):
        return "p"


class _FatalMCP:
    async def call_tool(self, name, arguments):
        raise ToolError("MCP_UNAVAILABLE", tool_name=name, detail="connection refused")

    async def read_resource(self, uri):
        return "[ok]"

    async def get_prompt(self, name, arguments):
        return "p"


def _tools(mcp):
    events, notices, used = [], [], []
    deps = Deps(fast_llm=None, quality_llm=None, mcp=mcp, store=None, checkpointer=None, paths=None)
    tools = build_agent_tools(deps, events.append, notices, used)
    return tools, events, notices, used


async def test_timeout_retries_then_isolates_as_tool_error():
    mcp = _TimeoutMCP()
    tools, events, notices, used = _tools(mcp)

    result = await tools[0].ainvoke({"query": "배송 지연"})

    assert result == "근거 없음"                 # 카드는 "근거 없음"으로 생성이 계속된다
    assert mcp.calls == RETRY_MAX + 1             # 최초 1회 + 재시도 2회 = 3번 시도
    assert events[0]["error"]["code"] == "TOOL_TIMEOUT_AFTER_RETRY"
    assert events[0]["error"]["fatal"] is False
    assert notices[0].code == "TOOL_TIMEOUT_AFTER_RETRY"
    assert used == [{"tool": "search_my_experience", "query": "배송 지연"}]


async def test_permanent_error_fails_immediately_without_retry():
    mcp = _PermanentErrorMCP()
    tools, events, notices, used = _tools(mcp)

    result = await tools[0].ainvoke({"query": "q"})

    assert result == "근거 없음"
    assert mcp.calls == 1                         # 재시도 없이 즉시 실패
    assert events[0]["error"]["code"] == "TOOL_EXECUTION_ERROR"
    assert events[0]["error"]["fatal"] is False


async def test_fatal_mcp_error_propagates():
    mcp = _FatalMCP()
    tools, events, notices, used = _tools(mcp)

    with pytest.raises(ToolError) as exc_info:
        await tools[0].ainvoke({"query": "q"})

    assert exc_info.value.info.code == "MCP_UNAVAILABLE"
    assert events == []  # 이 검색에 대한 EvidenceSearched는 보내지 않는다 (그래프 자체가 끝난다)
