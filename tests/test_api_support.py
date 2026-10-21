"""API 테스트 공용 도구 (A3). fake MCP·fake LLM·tmp_path로 Deps를 만들고 앱을 lifespan째 띄운다. 네트워크 없음.

이 파일에는 테스트가 없다. 다른 test_api_*.py가 가져다 쓴다 (conftest.py는 Lead 소유라 여기에 둔다).
"""

import json
import shutil
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import aiosqlite
import httpx
from langchain_core.messages import AIMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from agent.llm import ToolCallingFakeChatModel
from agent.store import SQLiteCardStore
from contracts.deps import DataPaths, Deps
from contracts.fixtures import load
from server import DepsFactory, create_app

ROOT = Path(__file__).resolve().parents[1]
THREAD = {"thread_id": "t1"}


class FakeMCP:
    """MCPPort 구현 (네트워크·subprocess 없음). 검색은 고정 출처 라벨 문자열을 돌려준다."""

    async def call_tool(self, name: str, arguments: dict) -> str:
        return "[experience.md > 물류 스타트업 데이터 분석 인턴 (2개월)]\n배송 지연 원인을 분석해 민원을 400건에서 260건으로 줄였다."

    async def read_resource(self, uri: str) -> str:
        return "[job_posting > 주요 업무]\n- 주문·배송·고객 행동 데이터 분석"

    async def get_prompt(self, name: str, arguments: dict) -> str:
        return "당신은 영어 면접 코치이자 검수자입니다. 규칙을 어긴 표현을 찾아 주세요."


def seed(tmp_path: Path) -> DataPaths:
    """examples/sample_user를 tmp_path(COACH_DATA_DIR)에 복사한다 (실제 data/는 건드리지 않는다)."""
    shutil.copytree(ROOT / "examples" / "sample_user", tmp_path, dirs_exist_ok=True)
    return DataPaths(tmp_path)


def tool_call(name: str, args: dict, call_id: str) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": call_id}])


def route(intent: str = "express") -> AIMessage:
    return tool_call("Route", {"intent": intent, "reason": "r"}, "route")


def card() -> AIMessage:
    return tool_call("ExpressionCard", load("card_express.json"), "card")


def review(fixture: str = "review_passed.json") -> AIMessage:
    return tool_call("ReviewResult", load(fixture), "review")


def passing_turn() -> tuple[list[AIMessage], list[AIMessage]]:
    """(fast 큐, quality 큐) — 한 턴이 검수를 통과해 승인 대기까지 가는 시나리오."""
    return [route()], [card(), review()]


def deps_factory(paths: DataPaths, fast: list[AIMessage], quality: list[AIMessage], *, store=None) -> DepsFactory:
    """같은 paths로 여러 번 호출할 수 있다 (재시작 시뮬레이션). 체크포인터는 실제 checkpoints.db 파일이다."""

    async def factory() -> Deps:
        saver = AsyncSqliteSaver(await aiosqlite.connect(str(paths.checkpoints_db)))
        await saver.setup()
        return Deps(fast_llm=ToolCallingFakeChatModel(messages=iter(fast)),
                    quality_llm=ToolCallingFakeChatModel(messages=iter(quality)), mcp=FakeMCP(),
                    store=store or SQLiteCardStore(paths.coach_db), checkpointer=saver, paths=paths)

    return factory


@asynccontextmanager
async def running_app(factory: DepsFactory, *, raise_app_exceptions: bool = True):
    """lifespan(Deps·graph 조립, 종료 정리)을 한 task 안에서 돌리며 httpx 클라이언트를 준다."""
    app = create_app(factory)
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=raise_app_exceptions)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            client.app = app   # 테스트가 라우트를 덧붙이거나 app.state를 볼 수 있게
            yield client


def sse_events(response: httpx.Response) -> list[dict]:
    """SSE 본문을 이벤트 dict 목록으로. 마지막 [DONE]은 {"type": "[DONE]"}로 바꿔 둔다."""
    out = []
    for chunk in response.text.split("\n\n"):
        if not chunk:
            continue
        assert chunk.startswith("data: "), chunk
        data = chunk[len("data: "):]
        out.append({"type": "[DONE]"} if data == "[DONE]" else json.loads(data))
    return out


def types(events: list[dict]) -> list[str]:
    return [e["type"] for e in events]


def error_code(response: httpx.Response) -> Optional[str]:
    return response.json()["error"]["code"]


async def stream(client: httpx.AsyncClient, message: str = "민원을 줄였다고 말하고 싶어", **params) -> httpx.Response:
    return await client.get("/chat/stream", params={"message": message, **{**THREAD, **params}})


async def resume(client: httpx.AsyncClient, approve: bool = True, **body) -> httpx.Response:
    return await client.post("/chat/resume", json={**THREAD, "approve": approve, **body})
