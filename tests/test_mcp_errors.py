"""A2 — agent/mcp_client.py 오류 계약 (ADR-0012, contracts.deps.MCPPort):
응답 지연 → asyncio.TimeoutError 그대로 / 연결 불가·서버 종료 → ToolError("MCP_UNAVAILABLE") / 서버 쪽 예외 → ToolError("TOOL_EXECUTION_ERROR").

실제 mcp_server.py(또는 죽거나 느린 최소 서버)를 stdio subprocess로 띄운다. fake 임베딩·tmp_path만 쓴다 (네트워크 없음).
"""

import asyncio
import shutil
from pathlib import Path

import pytest

from agent.mcp_client import MCPClient
from agent.retry import with_retry
from contracts import mcp_spec
from contracts.deps import DataPaths
from contracts.errors import ToolError
from contracts.mcp_spec import SERVER_NAME

REPO = Path(__file__).resolve().parents[1]
SAMPLE_USER = REPO / "examples" / "sample_user"

# 죽거나 느린 서버를 흉내 내는 최소 서버 (tmp_path에 써서 쓴다)
MISBEHAVING_SERVER = '''
import asyncio, os
from fastmcp import FastMCP

mcp = FastMCP("coach")

@mcp.tool(name="search_my_experience")
async def search(query: str, k: int = 3) -> str:
    if query == "die":
        os._exit(1)
    if query == "slow":
        await asyncio.sleep(5)
    return "[ok > fast]"

if __name__ == "__main__":
    mcp.run(transport="stdio", show_banner=False)
'''


@pytest.fixture
def paths(tmp_path, monkeypatch) -> DataPaths:
    root = tmp_path / "user"
    shutil.copytree(SAMPLE_USER, root)
    monkeypatch.setenv("COACH_DATA_DIR", str(root))
    monkeypatch.setenv("EMBEDDING_MODEL", "fake")
    return DataPaths(root)


def _client(script: Path = REPO / "mcp_server.py", **kwargs) -> MCPClient:
    """agent/deps.py::_build_mcp와 같은 호출 형태 (flaky 인자는 받아서 무시한다)."""
    return MCPClient(flaky_first_tool_call=False, server_scripts={SERVER_NAME: script}, **kwargs)


@pytest.fixture
def misbehaving_script(tmp_path) -> Path:
    script = tmp_path / "misbehaving_server.py"
    script.write_text(MISBEHAVING_SERVER, encoding="utf-8")
    return script


# ---------- 오류 계약 (ADR-0012) ----------

async def test_server_side_exceptions_become_tool_execution_error(paths):
    async with _client() as client:
        with pytest.raises(ToolError) as bad_args:                       # 서버의 입력 검증 실패 (k는 1~5)
            await client.call_tool(mcp_spec.TOOL_SEARCH_MY_EXPERIENCE, {"query": "x", "k": 99})
        paths.job_posting.unlink()
        with pytest.raises(ToolError) as bad_resource:                   # Resource를 읽다 서버가 예외
            await client.read_resource(mcp_spec.posting_uri("주요 업무"))
        with pytest.raises(ToolError) as unknown_tool:
            await client.call_tool("no_such_tool", {})
    for exc in (bad_args, bad_resource, unknown_tool):
        assert exc.value.info.code == "TOOL_EXECUTION_ERROR" and exc.value.info.fatal is False
    assert bad_args.value.tool_name == mcp_spec.TOOL_SEARCH_MY_EXPERIENCE


async def test_server_that_cannot_start_is_mcp_unavailable(tmp_path):
    client = _client(tmp_path / "missing_server.py")
    with pytest.raises(ToolError) as exc:
        await client.start()
    assert exc.value.info.code == "MCP_UNAVAILABLE" and exc.value.info.fatal and exc.value.info.recoverable

    with pytest.raises(ToolError) as later:                              # 연결 없이 부르면 같은 오류
        await client.call_tool(mcp_spec.TOOL_SEARCH_MY_EXPERIENCE, {"query": "x"})
    assert later.value.info.code == "MCP_UNAVAILABLE"


async def test_calls_before_start_and_after_stop_are_mcp_unavailable(paths):
    client = _client()
    with pytest.raises(ToolError) as before:
        await client.read_resource(mcp_spec.posting_uri("전체"))
    assert before.value.info.code == "MCP_UNAVAILABLE"

    async with client:
        await client.get_prompt(mcp_spec.PROMPT_PERSONA_REVIEW, {})
    with pytest.raises(ToolError) as after:
        await client.get_prompt(mcp_spec.PROMPT_PERSONA_REVIEW, {})
    assert after.value.info.code == "MCP_UNAVAILABLE"


async def test_server_dying_midway_is_mcp_unavailable(misbehaving_script):
    async with _client(misbehaving_script) as client:
        assert await client.call_tool(mcp_spec.TOOL_SEARCH_MY_EXPERIENCE, {"query": "fine"}) == "[ok > fast]"
        for _ in range(2):                                               # 죽는 호출, 그리고 죽은 뒤의 호출
            with pytest.raises(ToolError) as exc:
                await client.call_tool(mcp_spec.TOOL_SEARCH_MY_EXPERIENCE, {"query": "die"})
            assert exc.value.info.code == "MCP_UNAVAILABLE" and exc.value.info.fatal


async def test_slow_response_raises_asyncio_timeout_and_connection_survives(misbehaving_script):
    async with _client(misbehaving_script, call_timeout=0.5) as client:
        with pytest.raises(asyncio.TimeoutError):                        # ToolError로 바꾸지 않고 그대로 올려 호출부가 재시도한다
            await client.call_tool(mcp_spec.TOOL_SEARCH_MY_EXPERIENCE, {"query": "slow"})
        assert await client.call_tool(mcp_spec.TOOL_SEARCH_MY_EXPERIENCE, {"query": "fast"}) == "[ok > fast]"


async def test_caller_retry_policy_sees_the_timeout(misbehaving_script):
    """A1의 with_retry는 asyncio.TimeoutError만 재시도한다. 클라이언트가 그 예외를 그대로 줘야 재시도·소진이 성립한다."""
    async with _client(misbehaving_script, call_timeout=0.3) as client:
        with pytest.raises(asyncio.TimeoutError):
            await with_retry(client.call_tool, mcp_spec.TOOL_SEARCH_MY_EXPERIENCE, {"query": "slow"}, retries=2, base_delay=0.01)
