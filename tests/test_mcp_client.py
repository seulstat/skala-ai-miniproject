"""A2 — agent/mcp_client.py: 실제 mcp_server.py를 stdio subprocess로 띄워 MCPPort 계약(Tool·Resource·Prompt, find_*, A1 호출 형태)을 검증한다.
오류 계약(ADR-0012)은 test_mcp_errors.py.

fake 임베딩·tmp_path만 쓴다 (네트워크 없음). 서버 subprocess는 COACH_DATA_DIR·EMBEDDING_MODEL 환경변수를 상속하므로 monkeypatch로 넘긴다.
MCPClient의 start()/stop()은 anyio cancel scope 때문에 같은 task에서 불러야 하므로, 각 테스트 본문 안에서 `async with`로 연다.
"""

import asyncio
import shutil
from pathlib import Path

import pytest

from agent.deps import _build_mcp
from agent.mcp_client import MCPClient
from agent.prompts import reviewer_prompt
from agent.retry import with_retry
from agent.tools import build_agent_tools
from contracts import mcp_spec
from contracts.deps import DataPaths, Deps, MCPPort
from contracts.errors import ToolError
from contracts.mcp_spec import SERVER_NAME

REPO = Path(__file__).resolve().parents[1]
SAMPLE_USER = REPO / "examples" / "sample_user"


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


# ---------- MCPPort 충족 ----------

async def test_client_satisfies_mcp_port_and_serves_tool_resource_prompt(paths):
    async with _client() as client:
        assert isinstance(client, MCPPort)

        evidence = await client.call_tool(mcp_spec.TOOL_SEARCH_MY_EXPERIENCE, {"query": "배송 지연 민원", "k": 1})
        assert isinstance(evidence, str)                                 # dict가 아니라 str (Base와 달라진 점)
        assert evidence.startswith("[experience.md > 물류 스타트업 데이터 분석 인턴 (2개월)]")

        bank = await client.call_tool(mcp_spec.TOOL_SEARCH_EXPRESSION_BANK, {"query": "협업", "k": 2})
        assert bank.count("verified=") == 2

        posting = await client.read_resource(mcp_spec.posting_uri("영어 면접 안내"))
        assert posting.startswith("[job_posting > 영어 면접 안내]") and "약 8분" in posting

        prompt = await client.get_prompt(mcp_spec.PROMPT_PERSONA_REVIEW, {})
        assert prompt == reviewer_prompt(paths.persona_rules.read_text(encoding="utf-8"))


async def test_build_mcp_in_agent_deps_works_with_this_client(paths):
    """A1의 agent/deps.py::_build_mcp가 쓰는 형태(`MCPClient(...)` → `await start()` → `await stop()`) 그대로 동작한다."""
    client = await _build_mcp(paths)
    try:
        assert isinstance(client, MCPPort)
        assert (await client.read_resource(mcp_spec.posting_uri("전체"))).startswith("[job_posting > 전체]")
    finally:
        await client.stop()


async def test_find_methods_locate_the_coach_server(paths):
    async with _client() as client:
        assert await client.find_tool(mcp_spec.TOOL_SEARCH_MY_EXPERIENCE) == SERVER_NAME
        assert await client.find_prompt(mcp_spec.PROMPT_PERSONA_REVIEW) == SERVER_NAME
        assert await client.find_resource_template("posting") == (SERVER_NAME, mcp_spec.RESOURCE_POSTING)
        assert await client.find_resource_server(mcp_spec.posting_uri("주요 업무")) == SERVER_NAME
        for finder, name in ((client.find_tool, "no_such_tool"), (client.find_prompt, "no_such_prompt"),
                             (client.find_resource_template, "no_such_template"), (client.find_resource_server, "nope://x")):
            with pytest.raises(ToolError) as exc:
                await finder(name)
            assert exc.value.info.code == "TOOL_EXECUTION_ERROR"


async def test_agent_wrapper_tools_work_through_the_real_server(paths):
    """A1의 래퍼 @tool(agent/tools.py)이 실제 MCP 서버 위에서 출처 라벨 붙은 근거를 받는다 (ADR-0002)."""
    async with _client() as client:
        events, notices = [], []
        tools = {t.name: t for t in build_agent_tools(
            Deps(fast_llm=None, quality_llm=None, mcp=client, store=None, checkpointer=None, paths=paths),
            events.append, notices, [])}
        assert set(tools) == set(mcp_spec.AGENT_TOOL_NAMES)

        assert (await tools["search_my_experience"].ainvoke({"query": "배송 지연"})).startswith("[experience.md > ")
        assert (await tools["get_job_posting"].ainvoke({"section": "주요 업무"})).startswith("[job_posting > 주요 업무]")
        assert (await tools["search_expression_bank"].ainvoke({"query": "협업"})).startswith("[E")
        assert [e["tool"] for e in events] == ["search_my_experience", "get_job_posting", "search_expression_bank"]
        assert all(e.get("error") is None for e in events) and notices == []


async def test_reviewer_style_get_prompt_with_retry_returns_ready_system_prompt(paths):
    """agent/reviewer_agent.py::_llm_review와 같은 호출: with_retry(get_prompt, 이름, {}) → 받은 문자열을 그대로 system으로 쓴다."""
    async with _client() as client:
        system_prompt, retried = await with_retry(client.get_prompt, mcp_spec.PROMPT_PERSONA_REVIEW, {}, retries=3, base_delay=0.01)
    assert retried == 0 and system_prompt.startswith("당신은 영어 면접 코치이자")
    assert system_prompt.count("[검사 방법]") == 1                       # 지시문이 이중으로 들어 있지 않다


# ---------- 데이터 변경 반영 (프로세스 경계 너머) ----------

async def test_new_document_is_searchable_after_mtime_change(paths):
    async with _client() as client:
        assert "해커톤" not in await client.call_tool(mcp_spec.TOOL_SEARCH_MY_EXPERIENCE, {"query": "해커톤 우승", "k": 5})
        (paths.docs_dir / "hackathon.md").write_text("# 사내 해커톤\n추천 알고리즘으로 해커톤에서 우승했습니다.\n", encoding="utf-8")
        found = await client.call_tool(mcp_spec.TOOL_SEARCH_MY_EXPERIENCE, {"query": "해커톤 우승", "k": 1})
    assert found.startswith("[hackathon.md > 사내 해커톤]")


async def test_posting_resource_is_never_cached(paths):
    async with _client() as client:
        uri = mcp_spec.posting_uri("주요 업무")
        before = await client.read_resource(uri)
        paths.job_posting.write_text(
            paths.job_posting.read_text(encoding="utf-8").replace("물류 병목 구간 탐지", "수요 예측 모델 운영"), encoding="utf-8")
        after = await client.read_resource(uri)
    assert "물류 병목 구간 탐지" in before and "수요 예측 모델 운영" in after and before != after


async def test_concurrent_calls_share_one_connection(paths):
    async with _client() as client:
        results = await asyncio.gather(
            *[client.call_tool(mcp_spec.TOOL_SEARCH_MY_EXPERIENCE, {"query": q}) for q in ("배송 지연", "고객 이탈", "지원동기")],
            client.call_tool(mcp_spec.TOOL_SEARCH_EXPRESSION_BANK, {"query": "협업"}),
            client.read_resource(mcp_spec.posting_uri("전체")),
            client.get_prompt(mcp_spec.PROMPT_PERSONA_REVIEW, {}),
        )
    assert all(isinstance(r, str) and r for r in results)
    assert results[0].startswith("[experience.md > 물류")
