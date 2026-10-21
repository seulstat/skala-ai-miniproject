# 출처: all_total_vue_student/server.py (Phase 0 복사 후 Deps 주입·오류 변환 구조로 재작성, ADR-0011·0012)
"""FastAPI 앱 (:8100). lifespan에서 Deps·graph를 프로세스당 1회 만들어 app.state에 두고, 라우터는 Depends로 받는다.

- Deps 조립은 agent.deps.build_deps() 한 곳 (테스트는 deps_factory로 fake Deps를 넣는다)
- MCP start(build_deps 안)와 stop은 같은 lifespan 함수 안에서 부른다 — anyio cancel scope가 같은 task를 요구한다
- 오류(ADR-0012): CoachError → ErrorResponse + 카탈로그 HTTP 상태, 검증 실패 → 422 INPUT_INVALID, 그 외 → 500 UNEXPECTED_ERROR
"""

import asyncio
import logging
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import Awaitable, Callable, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from langchain_core.tracers.langchain import wait_for_all_tracers

from agent.deps import build_deps
from agent.graph import build_graph
from contracts.api import ErrorResponse
from contracts.deps import Deps
from contracts.errors import CoachError
from routers import cards, chat, setup
from services.errors import http_status, report_error

logger = logging.getLogger("coach.api")

DepsFactory = Callable[[], Awaitable[Deps]]


async def _close(label: str, closing: Awaitable) -> None:
    """종료 정리는 하나가 실패해도 나머지를 계속하고, 실패는 로그에 남긴다."""
    try:
        await closing
    except Exception:
        logger.warning("종료 중 %s 실패", label, exc_info=True)


async def _shutdown(deps: Deps) -> None:
    stop = getattr(deps.mcp, "stop", None)               # MCPClient만 있다 (fake MCP는 없을 수 있다)
    if stop is not None:
        await _close("MCP stop", stop())
    conn = getattr(deps.checkpointer, "conn", None)      # AsyncSqliteSaver의 aiosqlite 연결
    if conn is not None:
        await _close("체크포인터 close", conn.close())
    await _close("LangSmith flush", asyncio.to_thread(wait_for_all_tracers))   # kill 시 run이 pending으로 남는 것 방지


def _error_response(exc: BaseException, request: Request) -> JSONResponse:
    info = report_error(exc, thread_id=request.query_params.get("thread_id"))
    return JSONResponse(ErrorResponse(error=info).model_dump(mode="json"), status_code=http_status(info))


def create_app(deps_factory: Optional[DepsFactory] = None) -> FastAPI:
    """deps_factory가 없으면 .env를 읽고 build_deps()로 실제 Deps를 만든다. 테스트는 fake Deps 팩토리를 넣는다."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        factory = deps_factory
        if factory is None:
            load_dotenv()   # import 시점이 아니라 서버가 실제로 뜰 때만 (테스트가 .env의 LangSmith 설정을 끌어오지 않게)
            factory = build_deps
        deps = await factory()
        try:
            app.state.deps = deps
            app.state.graph = build_graph(deps)
            app.state.thread_locks = defaultdict(asyncio.Lock)
            yield
        finally:
            await _shutdown(deps)

    app = FastAPI(title="Interview Coach API", lifespan=lifespan)
    app.include_router(setup.router)
    app.include_router(chat.router)
    app.include_router(cards.router)

    @app.exception_handler(CoachError)
    async def coach_error(request: Request, exc: CoachError):
        return _error_response(exc, request)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, exc: RequestValidationError):
        return _error_response(CoachError("INPUT_INVALID", detail=str(exc.errors())), request)

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc: Exception):
        return _error_response(exc, request)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    uvicorn.run(app, host="127.0.0.1", port=8100, log_level="info")
