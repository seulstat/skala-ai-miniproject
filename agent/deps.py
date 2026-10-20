"""build_deps() — contracts.deps.Deps 조립 (정의는 contracts/deps.py, ADR-0011). 전역 싱글턴 금지, 호출마다 새로 만든다."""

import os
from pathlib import Path

import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from agent import llm as llm_module
from agent.store import SQLiteCardStore
from contracts.deps import DataPaths, Deps, MCPPort
from contracts.mcp_spec import SERVER_NAME

_REPO_ROOT = Path(__file__).resolve().parents[1]


async def _build_mcp(paths: DataPaths) -> MCPPort:
    """A2가 mcp_server.py·agent/mcp_client.py를 완성하기 전까지는 이 연결이 동작하지 않는다.
    server.py(A3) lifespan에서 A2 작업 완료 후 다시 확인한다 (handoff 요청 참고).
    """
    from agent.mcp_client import MCPClient  # A1은 agent/mcp_client.py를 수정하지 않는다 (agent.md §2)

    client = MCPClient(flaky_first_tool_call=False,
                        server_scripts={SERVER_NAME: _REPO_ROOT / "mcp_server.py"})
    await client.start()
    return client


async def _build_checkpointer(paths: DataPaths) -> AsyncSqliteSaver:
    conn = await aiosqlite.connect(str(paths.checkpoints_db))
    saver = AsyncSqliteSaver(conn)
    await saver.setup()
    return saver


async def build_deps() -> Deps:
    paths = DataPaths.from_env()
    fast_llm = llm_module.make_llm(os.getenv("FAST_MODEL", "fake"))
    quality_llm = llm_module.make_llm(os.getenv("QUALITY_MODEL", "fake"))
    mcp = await _build_mcp(paths)
    store = SQLiteCardStore(paths.coach_db)
    checkpointer = await _build_checkpointer(paths)
    return Deps(fast_llm=fast_llm, quality_llm=quality_llm, mcp=mcp, store=store,
                checkpointer=checkpointer, paths=paths)
