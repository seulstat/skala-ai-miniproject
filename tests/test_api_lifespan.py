"""실제 조립 경로: create_app() 기본 팩토리 → build_deps() → 실제 MCP 서버(stdio subprocess) + fake LLM.

fake Deps로는 확인할 수 없는 것을 본다 — MCP start/stop이 같은 lifespan 안에서 짝이 맞는지, 종료 때 정리되는지.
네트워크 없음(FAST/QUALITY/EMBEDDING_MODEL=fake). 서버 subprocess를 띄우므로 느리다(약 1초).
"""

import httpx
import pytest
from test_api_support import error_code, seed, sse_events, types

import server
from contracts import mcp_spec
from contracts.errors import ToolError


async def test_default_factory_wires_real_mcp_and_cleans_up(tmp_path, monkeypatch):
    seed(tmp_path)
    for name, value in {"COACH_DATA_DIR": str(tmp_path), "FAST_MODEL": "fake", "QUALITY_MODEL": "fake",
                        "EMBEDDING_MODEL": "fake"}.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(server, "load_dotenv", lambda: None)   # 개발자의 .env(ollama·LangSmith 설정)를 끌어오지 않는다

    app = server.create_app()
    async with app.router.lifespan_context(app):
        client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")
        async with client:
            assert (await client.get("/api/readiness")).json()["ready"] is True
            mcp = app.state.deps.mcp
            posting = await mcp.read_resource(mcp_spec.posting_uri("주요 업무"))
            assert posting.startswith("[job_posting > 주요 업무]")          # 진짜 MCP 서버와 연결돼 있다

            # fake 모델은 빈 응답을 내므로 라우터가 구조화 출력을 못 얻는다 → 치명 오류 이벤트 후 [DONE]
            r = await client.get("/chat/stream", params={"message": "민원을 줄였어요", "thread_id": "w1"})
            assert types(sse_events(r)) == ["ErrorRaised", "[DONE]"]
            assert (await client.get("/chat/pending", params={"thread_id": "w1"})).json()["pending"] is None
            assert error_code(await client.post("/chat/resume", json={"thread_id": "w1", "approve": True})) == "NO_PENDING"
        conn = app.state.deps.checkpointer.conn
    assert (tmp_path / "checkpoints.db").exists()
    with pytest.raises(ToolError) as stopped:                              # lifespan 종료에서 MCP를 멈췄다
        await mcp.read_resource(mcp_spec.posting_uri("주요 업무"))
    assert stopped.value.info.code == "MCP_UNAVAILABLE"
    with pytest.raises(ValueError):                                        # 체크포인터 연결도 닫혔다
        await conn.execute("select 1")
