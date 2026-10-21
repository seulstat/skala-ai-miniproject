"""CP1 통합 스모크 (Lead 소유): 실제 MCP 서버(stdio subprocess) + fake LLM으로 그래프 E2E.

A1(그래프)과 A2(MCP 서버·클라이언트·RAG)가 계약대로 맞물리는지 본다. 네트워크 없음(EMBEDDING_MODEL=fake).
"""

import shutil
from pathlib import Path

from langchain_core.messages import AIMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command

from agent.graph import build_graph
from agent.llm import ToolCallingFakeChatModel
from agent.mcp_client import MCPClient
from agent.store import SQLiteCardStore
from contracts import events, mcp_spec, schemas
from contracts.deps import DataPaths, Deps
from contracts.fixtures import load
from contracts.mcp_spec import SERVER_NAME
from contracts.state import ResumeValue

ROOT = Path(__file__).resolve().parents[1]
CFG = {"configurable": {"thread_id": "cp1"}}


def _tc(name: str, args: dict, cid: str) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": cid}])


async def test_graph_e2e_with_real_mcp_server(tmp_path, monkeypatch):
    shutil.copytree(ROOT / "examples" / "sample_user", tmp_path, dirs_exist_ok=True)
    monkeypatch.setenv("COACH_DATA_DIR", str(tmp_path))     # 서버 subprocess가 상속한다
    monkeypatch.setenv("EMBEDDING_MODEL", "fake")
    paths = DataPaths(tmp_path)

    client = MCPClient(server_scripts={SERVER_NAME: ROOT / "mcp_server.py"})
    await client.start()
    try:
        # MCP 경계: Tool·Resource·Prompt가 계약 형식으로 응답하는지
        hits = await client.call_tool(mcp_spec.TOOL_SEARCH_MY_EXPERIENCE, {"query": "배송 지연 원인 분석", "k": 2})
        assert hits.startswith("[experience.md > ")
        posting = await client.read_resource(mcp_spec.posting_uri("주요 업무"))
        assert posting.startswith("[job_posting > 주요 업무]")
        system_prompt = await client.get_prompt(mcp_spec.PROMPT_PERSONA_REVIEW, {})
        assert system_prompt.startswith("당신은 영어 면접 코치")

        # 그래프 E2E: router → coach(실제 MCP 검색 1회) → reviewer(실제 MCP Prompt) → approve → resume → save
        fast = ToolCallingFakeChatModel(messages=iter([_tc("Route", {"intent": "express", "reason": "r"}, "r0")]))
        quality = ToolCallingFakeChatModel(messages=iter([
            _tc(mcp_spec.AGENT_TOOL_SEARCH_MY_EXPERIENCE, {"query": "배송 지연 민원 감소"}, "t1"),
            _tc("ExpressionCard", load("card_express.json"), "c1"),
            _tc("ReviewResult", load("review_passed.json"), "v1"),
        ]))
        async with AsyncSqliteSaver.from_conn_string(str(paths.checkpoints_db)) as saver:
            deps = Deps(fast_llm=fast, quality_llm=quality, mcp=client, store=SQLiteCardStore(paths.coach_db),
                        checkpointer=saver, paths=paths)
            graph = build_graph(deps)
            got = [e async for e in graph.astream({"user_input": "민원을 줄였다고 말하고 싶어", "today": "2026-10-21"},
                                                  CFG, stream_mode="custom")]
            parsed = [events.parse_event(e) for e in got]
            assert events.is_valid_sequence([e.type for e in parsed] + ["[DONE]"]), [e.type for e in parsed]
            searched = [e for e in parsed if e.type == "EvidenceSearched"]
            assert searched and all(e.error is None for e in searched)   # 실제 MCP 검색이 격리 없이 성공

            pending = (await graph.aget_state(CFG)).interrupts[0].value
            assert schemas.ApprovalRequest.model_validate(pending).card.korean_prompt

            final = await graph.ainvoke(Command(resume=ResumeValue(approve=True)), CFG)
            assert final["saved_card_id"] == "C0001" and final["next_review"] == "2026-10-22"
    finally:
        await client.stop()
