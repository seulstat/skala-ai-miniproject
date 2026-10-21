"""/chat/stream · /chat/resume · /chat/pending (design §6 테스트 11, ADR-0006·0012). fake LLM·fake MCP, 네트워크 없음."""

import logging

from test_api_support import (
    THREAD,
    deps_factory,
    error_code,
    passing_turn,
    resume,
    route,
    running_app,
    seed,
    sse_events,
    stream,
    tool_call,
    types,
)

from agent.store import SQLiteCardStore
from contracts import events
from contracts.api import ErrorResponse, PendingResponse, ResumeResponse
from contracts.errors import ERROR_CATALOG
from contracts.events import SSE_HEADERS
from contracts.schemas import SavedCard

SECRET = "db-password=hunter2"


def _assert_error_event(response, code: str):
    """ErrorRaised 한 번 → [DONE]. 코드별 재시도 가능 여부·치명 여부는 ERROR_CATALOG와 같아야 한다."""
    evs = sse_events(response)
    assert types(evs)[-2:] == ["ErrorRaised", "[DONE]"] and events.is_valid_sequence(types(evs)), types(evs)
    error = events.parse_event(evs[-2]).error
    spec = ERROR_CATALOG[code]
    assert (error.code, error.recoverable, error.fatal) == (code, spec.recoverable, True)
    assert error.user_message == spec.user_message and error.trace_id
    return evs


# ---------- 테스트 11: 치명 오류 → 코드별 ErrorRaised → [DONE], 승인 대기 없음 → 409 NO_PENDING ----------

async def test_not_ready_is_error_raised_not_recoverable_then_done(data_paths):
    async with running_app(deps_factory(data_paths, [route()], [])) as client:   # 서류 없는 빈 폴더
        r = await stream(client)
    assert r.status_code == 200
    evs = _assert_error_event(r, "NOT_READY")
    assert types(evs) == ["ErrorRaised", "[DONE]"]       # 라우팅 전에 끝난다
    assert events.parse_event(evs[0]).error.recoverable is False


async def test_llm_output_invalid_is_error_raised_recoverable_then_done(tmp_path):
    bad_route = tool_call("Route", {"intent": "bogus"}, "route")   # 구조화 출력이 스키마를 어긴다
    async with running_app(deps_factory(seed(tmp_path), [bad_route], [])) as client:
        r = await stream(client)
    evs = _assert_error_event(r, "LLM_OUTPUT_INVALID")
    assert events.parse_event(evs[0]).error.recoverable is True
    assert "bogus" not in r.text                                 # 내부 원인(검증 메시지)은 화면으로 나가지 않는다


async def test_error_after_routing_keeps_events_before_it(tmp_path, caplog):
    paths = seed(tmp_path)
    store = SQLiteCardStore(paths.coach_db)

    async def boom():
        raise RuntimeError(SECRET)

    store.known_chunks = boom                                    # coach 노드가 부르는 첫 store 호출
    async with running_app(deps_factory(paths, [route()], [], store=store)) as client:
        with caplog.at_level(logging.WARNING, logger="coach.api"):
            r = await stream(client)
    evs = _assert_error_event(r, "UNEXPECTED_ERROR")
    assert types(evs) == ["RouteDecided", "ErrorRaised", "[DONE]"]
    assert SECRET not in r.text                                  # 응답에는 user_message뿐
    trace_id = events.parse_event(evs[1]).error.trace_id
    assert SECRET in caplog.text and trace_id in caplog.text     # 원인은 같은 trace_id로 로그에만
    assert "error_code=UNEXPECTED_ERROR" in caplog.text and "thread_id=t1" in caplog.text


async def test_resume_without_pending_is_409_no_pending(tmp_path):
    async with running_app(deps_factory(seed(tmp_path), [], [])) as client:
        r = await resume(client, thread_id="never-used")
    assert r.status_code == ERROR_CATALOG["NO_PENDING"].http_status == 409
    error = ErrorResponse.model_validate(r.json()).error
    assert (error.code, error.recoverable) == ("NO_PENDING", False) and error.trace_id


# ---------- 정상 경로: stream → pending → resume ----------

async def test_stream_pending_resume_approve_saves_card(tmp_path):
    paths = seed(tmp_path)
    fast, quality = passing_turn()
    async with running_app(deps_factory(paths, fast, quality)) as client:
        r = await stream(client)
        assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
        assert all(r.headers[k.lower()] == v for k, v in SSE_HEADERS.items() if k != "Connection")
        evs = sse_events(r)
        assert events.is_valid_sequence(types(evs)) and types(evs)[-2:] == ["ApprovalRequired", "[DONE]"]
        asked = events.parse_event(evs[-2])

        pending = PendingResponse.model_validate((await client.get("/chat/pending", params=THREAD)).json())
        assert pending.thread_id == "t1" and pending.pending.card == asked.card   # SSE와 같은 내용
        assert (await client.get("/api/cards")).json() == []                      # 승인 전에는 저장하지 않는다

        saved = ResumeResponse.model_validate((await resume(client)).json())
        assert saved.saved and saved.card_id == "C0001" and saved.next_review

        cards = [SavedCard.model_validate(c) for c in (await client.get("/api/cards")).json()]
        assert [c.id for c in cards] == ["C0001"] and cards[0].korean_prompt == asked.card.korean_prompt
        assert (await client.get("/chat/pending", params=THREAD)).json()["pending"] is None
        again = await resume(client)                                             # 이미 처리된 승인
        assert (again.status_code, error_code(again)) == (409, "NO_PENDING")


async def test_resume_reject_does_not_save(tmp_path):
    fast, quality = passing_turn()
    async with running_app(deps_factory(seed(tmp_path), fast, quality)) as client:
        await stream(client)
        r = await resume(client, approve=False)
        assert r.status_code == 200 and r.json() == {"saved": False, "card_id": None, "next_review": None}
        assert (await client.get("/api/cards")).json() == []
        assert (await client.get("/chat/pending", params=THREAD)).json()["pending"] is None


async def test_pending_is_null_for_unknown_thread(tmp_path):
    async with running_app(deps_factory(seed(tmp_path), [], [])) as client:
        r = await client.get("/chat/pending", params={"thread_id": "nobody"})
    assert r.status_code == 200 and r.json() == {"thread_id": "nobody", "pending": None}


async def test_stream_rejects_empty_message(tmp_path):
    async with running_app(deps_factory(seed(tmp_path), [], [])) as client:
        for message in ("", "   "):
            r = await stream(client, message=message)
            assert (r.status_code, error_code(r)) == (422, "INPUT_INVALID"), repr(message)


async def test_intents_without_card_end_with_final_answer(tmp_path):
    for intent in ("out_of_scope", "review"):
        async with running_app(deps_factory(seed(tmp_path / intent), [route(intent)], [])) as client:
            evs = sse_events(await stream(client))
            assert types(evs) == ["RouteDecided", "FinalAnswer", "[DONE]"], intent
            assert (await client.get("/chat/pending", params=THREAD)).json()["pending"] is None
