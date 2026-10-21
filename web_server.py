# 출처: ref/base/web_demo_server.py (정적 서빙 + 프록시 구조)
"""web_server.py — 정적 서빙(:8600) + /api/*·/chat/* 프록시(→ server.py :8100). 담당 A4.

    python web_server.py          # 실제 백엔드(BACKEND_URL, 기본 http://127.0.0.1:8100)로 프록시
    MOCK=1 python web_server.py   # 백엔드 없이 contracts/fixtures로 응답, sse_*.json 재생 (web/mock_backend.py)

SSE는 버퍼링하지 않고 청크가 오는 대로 흘려보낸다 (강의 p.114, contracts.events.SSE_HEADERS).
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from contracts.api import ErrorResponse
from contracts.errors import error_info
from contracts.events import SSE_HEADERS

BACKEND = os.environ.get("BACKEND_URL", "http://127.0.0.1:8100")
PORT = int(os.environ.get("WEB_PORT", "8600"))
WEB_DIR = Path(__file__).parent / "web"
METHODS = ["GET", "POST", "PUT", "DELETE"]
# 프록시가 그대로 넘기면 안 되는 요청 헤더. 압축을 풀지 않고 raw로 중계하므로 identity만 요청한다
SKIP_REQUEST_HEADERS = {"host", "content-length", "connection", "accept-encoding"}


class WebFiles(StaticFiles):
    """개발 중 캐시를 막고 web/ 안의 .py(mock 서버 코드)는 내려주지 않는다."""

    async def get_response(self, path, scope):
        if path.endswith(".py"):
            raise HTTPException(status_code=404)
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 읽기 제한 시간은 없다: SSE는 오래 열려 있고 공고 정리·카드 생성은 LLM 호출이라 느릴 수 있다
    async with httpx.AsyncClient(base_url=BACKEND, timeout=httpx.Timeout(None, connect=5.0)) as client:
        app.state.client = client
        yield


async def proxy(request: Request):
    """요청을 그대로 백엔드로 보내고, 응답은 받는 대로 흘려보낸다 (SSE 포함)."""
    target = request.scope["raw_path"].decode("ascii")
    if request.url.query:
        target += "?" + request.url.query
    headers = {k: v for k, v in request.headers.items() if k.lower() not in SKIP_REQUEST_HEADERS}
    headers["accept-encoding"] = "identity"
    client: httpx.AsyncClient = request.app.state.client
    try:
        upstream = await client.send(
            client.build_request(request.method, target, headers=headers, content=await request.body()), stream=True)
    except httpx.TransportError:
        info = error_info("STREAM_DISCONNECTED", f"백엔드 서버({BACKEND})에 연결할 수 없어요. server.py가 실행 중인지 확인한 뒤 다시 시도해 주세요.")
        return JSONResponse(ErrorResponse(error=info).model_dump(mode="json"), status_code=502)

    content_type = upstream.headers.get("content-type", "")
    out = {"content-type": content_type} if content_type else {}
    if content_type.startswith("text/event-stream"):
        out |= SSE_HEADERS

    async def relay():
        try:
            async for chunk in upstream.aiter_raw():
                yield chunk
        finally:
            await upstream.aclose()

    return StreamingResponse(relay(), status_code=upstream.status_code, headers=out)


async def mock_off():
    return {"mock": False}


def create_app(mock: bool | None = None) -> FastAPI:
    mock = os.environ.get("MOCK") == "1" if mock is None else mock
    app = FastAPI(lifespan=lifespan)
    if mock:
        from web.mock_backend import create_mock_router
        app.include_router(create_mock_router())
    else:
        app.add_api_route("/mock-info", mock_off, methods=["GET"])   # 화면이 MOCK 여부를 묻는 경로 (404 노이즈 방지)
        app.add_api_route("/api/{path:path}", proxy, methods=METHODS)
        app.add_api_route("/chat/{path:path}", proxy, methods=METHODS)
    app.mount("/", WebFiles(directory=WEB_DIR, html=True), name="web")   # 라우트 뒤에 마운트해야 /api가 가려지지 않는다
    return app


app = create_app()

if __name__ == "__main__":
    mode = "MOCK (contracts/fixtures)" if os.environ.get("MOCK") == "1" else f"프록시 → {BACKEND}"
    print(f"브라우저에서 http://localhost:{PORT} 을 열어보세요 — {mode}")
    uvicorn.run(app, host="127.0.0.1", port=PORT)
