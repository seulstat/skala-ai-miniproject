"""design §6 테스트 3~6 — 재작성 상한 경고, 승인 후 저장, 거절 시 미저장, 재시작 후 승인 대기 복원."""

import json
from pathlib import Path

from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command

from agent.graph import build_graph
from agent.llm import ToolCallingFakeChatModel
from agent.store import SQLiteCardStore
from contracts import events, schemas
from contracts.deps import DataPaths, Deps
from contracts.fixtures import load
from contracts.state import ResumeValue

CFG = {"configurable": {"thread_id": "t1"}}


def _tc(name: str, args: dict, cid: str) -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args, "id": cid}])


def _route(intent: str = "express") -> AIMessage:
    return _tc("Route", {"intent": intent, "reason": "r"}, "route")


def _card(cid: str) -> AIMessage:
    return _tc("ExpressionCard", load("card_express.json"), cid)


def _review(passed: bool, cid: str) -> AIMessage:
    payload = load("review_passed.json") if passed else load("review_failed.json")
    return _tc("ReviewResult", payload, cid)


class _FakeMCP:
    async def call_tool(self, name, arguments):
        return "[experience.md > x]\n내용"

    async def read_resource(self, uri):
        return "[job_posting > 전체]\n내용"

    async def get_prompt(self, name, arguments):
        return "검수 규칙"


def _seed_data_dir(tmp_path: Path) -> DataPaths:
    (tmp_path / "docs").mkdir(exist_ok=True)
    (tmp_path / "profile.json").write_text(
        json.dumps({"goal": "데이터 분석가가 되고 싶다", "target_role": "데이터 분석가"}), encoding="utf-8"
    )
    return DataPaths(tmp_path)


async def test_rewrite_limit_sets_warning_and_goes_to_approve(tmp_path):
    paths = _seed_data_dir(tmp_path)
    fast = ToolCallingFakeChatModel(messages=iter([_route()]))
    quality = ToolCallingFakeChatModel(messages=iter([
        _card("c1"), _review(False, "r1"),
        _card("c2"), _review(False, "r2"),
        _card("c3"), _review(False, "r3"),
    ]))
    deps = Deps(fast_llm=fast, quality_llm=quality, mcp=_FakeMCP(), store=SQLiteCardStore(paths.coach_db),
                checkpointer=InMemorySaver(), paths=paths)
    graph = build_graph(deps)

    got = [e async for e in graph.astream({"user_input": "hi", "today": "2026-10-20"}, CFG, stream_mode="custom")]
    types = [events.parse_event(e).type for e in got] + ["[DONE]"]
    assert events.is_valid_sequence(types), types

    state = await graph.aget_state(CFG)
    assert state.values["retry_count"] == 2
    assert len(state.values["review_log"]) == 3
    assert state.values["warning"] and "재작성 2회" in state.values["warning"]
    assert state.interrupts  # approve에서 멈췄다 (경고를 달고도 승인 단계로 진행)


async def test_approve_saves_card(tmp_path):
    paths = _seed_data_dir(tmp_path)
    fast = ToolCallingFakeChatModel(messages=iter([_route()]))
    quality = ToolCallingFakeChatModel(messages=iter([_card("c1"), _review(True, "r1")]))
    store = SQLiteCardStore(paths.coach_db)
    deps = Deps(fast_llm=fast, quality_llm=quality, mcp=_FakeMCP(), store=store,
                checkpointer=InMemorySaver(), paths=paths)
    graph = build_graph(deps)

    async for _ in graph.astream({"user_input": "hi", "today": "2026-10-20"}, CFG, stream_mode="custom"):
        pass
    final = await graph.ainvoke(Command(resume=ResumeValue(approve=True)), CFG)

    assert final["approved"] is True
    assert final["saved_card_id"] == "C0001"
    assert final["next_review"] == "2026-10-21"
    saved = await store.list_cards()
    assert [c.id for c in saved] == ["C0001"]


async def test_reject_does_not_save_card(tmp_path):
    paths = _seed_data_dir(tmp_path)
    fast = ToolCallingFakeChatModel(messages=iter([_route()]))
    quality = ToolCallingFakeChatModel(messages=iter([_card("c1"), _review(True, "r1")]))
    store = SQLiteCardStore(paths.coach_db)
    deps = Deps(fast_llm=fast, quality_llm=quality, mcp=_FakeMCP(), store=store,
                checkpointer=InMemorySaver(), paths=paths)
    graph = build_graph(deps)

    async for _ in graph.astream({"user_input": "hi", "today": "2026-10-20"}, CFG, stream_mode="custom"):
        pass
    final = await graph.ainvoke(Command(resume=ResumeValue(approve=False)), CFG)

    assert final["approved"] is False
    assert final.get("saved_card_id") is None   # 새 턴 초기화로 None일 수 있다 (ADR-0017)
    assert final["final_message"].startswith("저장하지 않았습니다")
    assert await store.list_cards() == []


async def test_pending_restores_after_rebuilding_graph_with_new_checkpointer(tmp_path):
    """그래프를 새로 빌드해도 체크포인트에서 승인 대기가 복원된다 (서버 재시작 시뮬레이션)."""
    paths = _seed_data_dir(tmp_path)
    db_path = str(paths.checkpoints_db)

    async with AsyncSqliteSaver.from_conn_string(db_path) as saver1:
        fast = ToolCallingFakeChatModel(messages=iter([_route()]))
        quality = ToolCallingFakeChatModel(messages=iter([_card("c1"), _review(True, "r1")]))
        store1 = SQLiteCardStore(paths.coach_db)
        deps1 = Deps(fast_llm=fast, quality_llm=quality, mcp=_FakeMCP(), store=store1,
                     checkpointer=saver1, paths=paths)
        graph1 = build_graph(deps1)
        async for _ in graph1.astream({"user_input": "hi", "today": "2026-10-20"}, CFG, stream_mode="custom"):
            pass
    # saver1(연결)은 여기서 닫힌다 — 서버 프로세스 재시작을 흉내 낸다

    async with AsyncSqliteSaver.from_conn_string(db_path) as saver2:
        store2 = SQLiteCardStore(paths.coach_db)
        deps2 = Deps(fast_llm=None, quality_llm=None, mcp=_FakeMCP(), store=store2,
                     checkpointer=saver2, paths=paths)
        graph2 = build_graph(deps2)

        pending = (await graph2.aget_state(CFG)).interrupts[0].value
        req = schemas.ApprovalRequest.model_validate(pending)
        assert req.card.korean_prompt == load("card_express.json")["korean_prompt"]

        final = await graph2.ainvoke(Command(resume=ResumeValue(approve=True)), CFG)
        assert final["saved_card_id"] == "C0001"
        assert [c.id for c in await store2.list_cards()] == ["C0001"]
