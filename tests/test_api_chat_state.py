"""/chat/* 상태 흐름: 서버 재시작 후 pending 복원, 저장 실패 재시도, 동시 승인, 같은 thread의 새 메시지 (ADR-0006·0017).

fake LLM·fake MCP, 같은 tmp_path의 checkpoints.db·coach.db를 여러 앱이 공유한다. 네트워크 없음.
"""

import asyncio

from test_api_support import (
    THREAD,
    card,
    deps_factory,
    passing_turn,
    resume,
    review,
    route,
    running_app,
    seed,
    sse_events,
    stream,
)

from agent.store import SQLiteCardStore
from contracts import events
from contracts.api import ErrorResponse, PendingResponse, ResumeResponse
from contracts.errors import ERROR_CATALOG, CoachError


async def test_pending_survives_server_restart_with_same_checkpoints_db(tmp_path):
    paths = seed(tmp_path)
    fast, quality = passing_turn()
    async with running_app(deps_factory(paths, fast, quality)) as first:        # 서버 1: 카드 생성 후 승인 대기에서 종료
        asked = events.parse_event(sse_events(await stream(first))[-2])
    assert paths.checkpoints_db.exists()

    async with running_app(deps_factory(paths, [], [])) as second:              # 서버 2: 같은 checkpoints.db, LLM 큐는 비어 있다
        pending = PendingResponse.model_validate((await second.get("/chat/pending", params=THREAD)).json())
        assert pending.pending is not None and pending.pending.card == asked.card
        saved = ResumeResponse.model_validate((await resume(second)).json())
        assert saved.saved and saved.card_id == "C0001"
        assert (await second.get("/chat/pending", params=THREAD)).json()["pending"] is None
    async with running_app(deps_factory(paths, [], [])) as third:               # 서버 3: 저장된 카드도 coach.db에 남아 있다
        assert [c["id"] for c in (await third.get("/api/cards")).json()] == ["C0001"]


async def test_store_error_on_approve_can_be_retried(tmp_path):
    paths = seed(tmp_path)
    store = SQLiteCardStore(paths.coach_db)
    real_save, calls = store.save_card, []

    async def flaky_save(card_, today=None):
        calls.append(card_)
        if len(calls) == 1:
            raise CoachError("STORE_ERROR", detail="disk full")
        return await real_save(card_, today)

    store.save_card = flaky_save
    fast, quality = passing_turn()
    async with running_app(deps_factory(paths, fast, quality, store=store), raise_app_exceptions=False) as client:
        await stream(client)
        failed = await resume(client)
        assert failed.status_code == ERROR_CATALOG["STORE_ERROR"].http_status == 500
        assert ErrorResponse.model_validate(failed.json()).error.recoverable   # 다시 시도 버튼
        assert (await client.get("/api/cards")).json() == []
        retried = await resume(client)                                         # "승인 버튼을 다시 눌러 주세요"
        assert retried.status_code == 200 and retried.json()["card_id"] == "C0001"
        assert len((await client.get("/api/cards")).json()) == 1 and len(calls) == 2
        assert (await resume(client)).status_code == 409                       # 이번에는 정말 처리 끝


async def test_concurrent_resume_saves_only_once(tmp_path):
    fast, quality = passing_turn()
    async with running_app(deps_factory(seed(tmp_path), fast, quality)) as client:
        await stream(client)
        first, second = await asyncio.gather(resume(client), resume(client))
        assert sorted([first.status_code, second.status_code]) == [200, 409]
        assert len((await client.get("/api/cards")).json()) == 1


async def test_new_message_on_same_thread_does_not_inherit_previous_warning(tmp_path):
    """재작성 상한을 넘겨 경고가 달린 턴 다음 턴에, 이전 경고·검수 결과가 새 카드에 묻어오지 않는다 (ADR-0017)."""
    failed = review("review_failed.json")
    fast = [route(), route()]
    quality = [card(), failed, card(), failed, card(), failed, card(), review()]   # 턴1: 3라운드 실패 → 경고, 턴2: 통과
    async with running_app(deps_factory(seed(tmp_path), fast, quality)) as client:
        first = events.parse_event(sse_events(await stream(client))[-2])
        assert first.warning and "재작성" in first.warning
        await resume(client, approve=False)
        second = events.parse_event(sse_events(await stream(client, message="두 번째"))[-2])
        assert second.type == "ApprovalRequired" and second.warning is None
        pending = (await client.get("/chat/pending", params=THREAD)).json()["pending"]
        assert pending["warning"] is None and pending["review"]["passed"] is True


async def test_new_message_replaces_unanswered_approval_on_same_thread(tmp_path):
    fast, quality = [route(), route()], [card(), review(), card(), review()]
    async with running_app(deps_factory(seed(tmp_path), fast, quality)) as client:
        await stream(client, message="첫 번째")
        await stream(client, message="두 번째")
        pending = (await client.get("/chat/pending", params=THREAD)).json()["pending"]
        assert pending is not None
        assert (await resume(client)).status_code == 200
        assert len((await client.get("/api/cards")).json()) == 1               # 대기 카드는 하나뿐이라 한 장만 저장
        assert (await resume(client)).status_code == 409
