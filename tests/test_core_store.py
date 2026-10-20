"""design §6 테스트 7 — 복습 단계 전환 (안다 / 다시, 단계 0·1·2 = D+1·D+3·D+7)."""

from datetime import date

from agent.store import SQLiteCardStore
from contracts.schemas import Chunk, ExpressionCard


def _card() -> ExpressionCard:
    return ExpressionCard(
        korean_prompt="민원을 줄였다고 말하고 싶어",
        formal_expression="I cut complaints.",
        casual_expression="I cut complaints a bit.",
        chunks=[Chunk(phrase="cut complaints", note="민원을 줄이다")],
        note="근거",
        evidence=["[experience.md > x]"],
    )


async def test_known_advances_stage_and_again_resets(tmp_path):
    store = SQLiteCardStore(tmp_path / "coach.db")
    saved = await store.save_card(_card(), today=date(2026, 10, 20))
    assert saved.stage == 0 and saved.next_review == "2026-10-21"  # D+1

    r1 = await store.review(saved.id, "known", today=date(2026, 10, 21))
    assert r1.stage == 1 and r1.next_review == "2026-10-24"  # D+3

    r2 = await store.review(saved.id, "known", today=date(2026, 10, 24))
    assert r2.stage == 2 and r2.next_review == "2026-10-31"  # D+7

    r3 = await store.review(saved.id, "known", today=date(2026, 10, 31))
    assert r3.stage == 2  # 최고 단계에서 더 올라가지 않는다

    r4 = await store.review(saved.id, "again", today=date(2026, 11, 7))
    assert r4.stage == 0 and r4.next_review == "2026-11-08"  # D+1로 복귀


async def test_due_cards_and_known_chunks(tmp_path):
    store = SQLiteCardStore(tmp_path / "coach.db")
    saved = await store.save_card(_card(), today=date(2026, 10, 20))

    assert [c.id for c in await store.due_cards(today=date(2026, 10, 21))] == [saved.id]  # 저장일 D+1
    assert await store.due_cards(today=date(2026, 10, 20)) == []  # 저장 당일은 아직 복습일이 아니다
    assert await store.known_chunks() == ["cut complaints"]
    assert [c.id for c in await store.list_cards()] == [saved.id]
