"""server.py: 라우트 표, lifespan(Deps 1회 조립·종료 정리), 오류 변환(ADR-0012). fake Deps·tmp_path, 네트워크 없음."""

import logging
from dataclasses import replace

import pytest
from test_api_support import FakeMCP, deps_factory, running_app, seed

from contracts.api import ROUTES, ErrorResponse
from contracts.deps import Deps
from contracts.errors import ERROR_CATALOG, CoachError, ToolError


def test_every_contract_route_is_registered():
    from server import app  # import만으로는 모델·DB를 만들지 않는다 (lifespan에서 조립)
    paths = app.openapi()["paths"]
    missing = [name for name, (method, path) in ROUTES.items() if method.lower() not in paths.get(path, {})]
    assert missing == []


async def test_deps_are_built_once_per_app_and_closed_on_shutdown(tmp_path):
    paths = seed(tmp_path)
    built: list[Deps] = []
    inner = deps_factory(paths, [], [])

    class StoppableMCP(FakeMCP):
        stopped = 0

        async def stop(self):
            type(self).stopped += 1

    async def factory() -> Deps:
        deps = await inner()
        deps = replace(deps, mcp=StoppableMCP())
        built.append(deps)
        return deps

    async with running_app(factory) as client:
        for _ in range(3):
            await client.get("/api/readiness")
        assert len(built) == 1 and client.app.state.deps is built[0]   # 요청마다 다시 만들지 않는다
        conn = built[0].checkpointer.conn
        await conn.execute("select 1")                                  # 서버가 도는 동안 체크포인터 연결이 열려 있다
    assert StoppableMCP.stopped == 1                                    # MCP stop은 lifespan 종료 때 한 번
    with pytest.raises(ValueError):
        await conn.execute("select 1")                                  # 체크포인터 연결도 닫혔다


async def test_shutdown_failure_is_logged_and_does_not_block_other_cleanup(tmp_path, caplog):
    inner = deps_factory(seed(tmp_path), [], [])

    class BrokenMCP(FakeMCP):
        async def stop(self):
            raise RuntimeError("stop failed")

    async def factory() -> Deps:
        deps = await inner()
        return replace(deps, mcp=BrokenMCP())

    with caplog.at_level(logging.WARNING, logger="coach.api"):
        async with running_app(factory) as client:
            conn = client.app.state.deps.checkpointer.conn
    assert "MCP stop" in caplog.text and "stop failed" in caplog.text
    with pytest.raises(ValueError):
        await conn.execute("select 1")


@pytest.mark.parametrize("code", sorted(ERROR_CATALOG))
async def test_coach_error_becomes_error_response_with_catalog_status(tmp_path, code):
    async with running_app(deps_factory(seed(tmp_path), [], [])) as client:
        async def fail():
            raise CoachError(code, detail="내부 원인 text")

        client.app.add_api_route("/__fail", fail)
        r = await client.get("/__fail")
    spec = ERROR_CATALOG[code]
    assert r.status_code == (spec.http_status or 500)
    error = ErrorResponse.model_validate(r.json()).error
    assert (error.code, error.layer, error.recoverable, error.fatal) == (code, spec.layer, spec.recoverable, spec.fatal)
    assert error.user_message == spec.user_message and error.trace_id
    assert "내부 원인" not in r.text


async def test_tool_error_keeps_its_code(tmp_path):
    async with running_app(deps_factory(seed(tmp_path), [], [])) as client:
        async def fail():
            raise ToolError("MCP_UNAVAILABLE", "search_my_experience", "서버 죽음")

        client.app.add_api_route("/__fail", fail)
        r = await client.get("/__fail")
    assert r.status_code == 503 and r.json()["error"]["code"] == "MCP_UNAVAILABLE"


async def test_unclassified_exception_is_500_unexpected_error_with_cause_only_in_log(tmp_path, caplog):
    async with running_app(deps_factory(seed(tmp_path), [], []), raise_app_exceptions=False) as client:
        async def fail():
            raise RuntimeError("secret=hunter2")

        client.app.add_api_route("/__fail", fail)
        with caplog.at_level(logging.WARNING, logger="coach.api"):
            r = await client.get("/__fail")
    assert r.status_code == 500
    error = ErrorResponse.model_validate(r.json()).error
    assert error.code == "UNEXPECTED_ERROR" and error.recoverable is False
    assert "hunter2" not in r.text and "RuntimeError" not in r.text
    assert "secret=hunter2" in caplog.text and error.trace_id in caplog.text
    assert all(f in caplog.text for f in ("thread_id=", "node=", "tool=", "layer=application", "error_code=UNEXPECTED_ERROR"))
