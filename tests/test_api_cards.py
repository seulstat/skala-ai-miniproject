"""/api/cards · /api/cards/due · /api/cards/{id}/review (design §4 ③ 카드·복습, P1). fake Deps·tmp_path, 네트워크 없음."""

from datetime import date

from test_api_support import deps_factory, error_code, running_app, seed

from agent.store import SQLiteCardStore
from contracts.errors import ERROR_CATALOG
from contracts.fixtures import load
from contracts.schemas import REVIEW_INTERVALS_DAYS, ExpressionCard, SavedCard


async def _two_cards(paths) -> tuple[SavedCard, SavedCard]:
    """하나는 예전에 저장해 복습 대상, 하나는 먼 미래에 저장해 아직 아님. 오늘 날짜에 의존하지 않는다."""
    store = SQLiteCardStore(paths.coach_db)
    base = ExpressionCard.model_validate(load("card_express.json"))
    old = await store.save_card(base, today=date(2000, 1, 1))
    future = await store.save_card(base.model_copy(update={"korean_prompt": "나중 카드"}), today=date(2999, 1, 1))
    return old, future


async def test_list_cards_empty_then_all(tmp_path):
    paths = seed(tmp_path)
    async with running_app(deps_factory(paths, [], [])) as client:
        assert (await client.get("/api/cards")).json() == []
        old, future = await _two_cards(paths)
        listed = [SavedCard.model_validate(c) for c in (await client.get("/api/cards")).json()]
    assert [c.id for c in listed] == [old.id, future.id] and listed[0] == old


async def test_due_cards_only_include_cards_whose_review_day_came(tmp_path):
    paths = seed(tmp_path)
    async with running_app(deps_factory(paths, [], [])) as client:
        old, _ = await _two_cards(paths)
        due = (await client.get("/api/cards/due")).json()
    assert [c["id"] for c in due] == [old.id]


async def test_review_known_advances_stage_and_again_resets_it(tmp_path):
    paths = seed(tmp_path)
    async with running_app(deps_factory(paths, [], [])) as client:
        old, _ = await _two_cards(paths)
        url = f"/api/cards/{old.id}/review"
        first = SavedCard.model_validate((await client.post(url, json={"result": "known"})).json())
        assert first.stage == 1 and _days_from_today(first.next_review) == REVIEW_INTERVALS_DAYS[1]
        second = SavedCard.model_validate((await client.post(url, json={"result": "known"})).json())
        assert second.stage == 2 and _days_from_today(second.next_review) == REVIEW_INTERVALS_DAYS[2]
        capped = SavedCard.model_validate((await client.post(url, json={"result": "known"})).json())
        assert capped.stage == 2                                           # 최대 단계에서 더 오르지 않는다
        reset = SavedCard.model_validate((await client.post(url, json={"result": "again"})).json())
        assert reset.stage == 0 and _days_from_today(reset.next_review) == REVIEW_INTERVALS_DAYS[0]
        stored = next(c for c in (await client.get("/api/cards")).json() if c["id"] == old.id)
    assert stored["stage"] == 0                                            # 응답만이 아니라 저장소에 반영됐다


async def test_review_unknown_card_is_404_not_found(tmp_path):
    async with running_app(deps_factory(seed(tmp_path), [], [])) as client:
        r = await client.post("/api/cards/C9999/review", json={"result": "known"})
    assert r.status_code == ERROR_CATALOG["NOT_FOUND"].http_status == 404
    assert error_code(r) == "NOT_FOUND" and "C9999" not in r.text         # id는 로그에만


async def test_review_rejects_invalid_result(tmp_path):
    paths = seed(tmp_path)
    async with running_app(deps_factory(paths, [], [])) as client:
        old, _ = await _two_cards(paths)
        r = await client.post(f"/api/cards/{old.id}/review", json={"result": "maybe"})
    assert (r.status_code, error_code(r)) == (422, "INPUT_INVALID")


def _days_from_today(iso_date: str) -> int:
    return (date.fromisoformat(iso_date) - date.today()).days
