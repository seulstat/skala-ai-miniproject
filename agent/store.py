# 출처: skala-ai-agent/practice/dapdap/tools.py의 save_card·get_due_cards (Phase 0 복사 후 SQLite·async로 재작성)
"""카드 저장소 (contracts.deps.CardStore 구현). coach.db(SQLite), aiosqlite로 async 네이티브 접근 (ADR-0005)."""

import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import aiosqlite

from contracts.errors import CoachError
from contracts.schemas import REVIEW_INTERVALS_DAYS, ExpressionCard, ReviewOutcome, SavedCard

_SCHEMA = """
CREATE TABLE IF NOT EXISTS cards (
    id TEXT PRIMARY KEY,
    created TEXT NOT NULL,
    next_review TEXT NOT NULL,
    stage INTEGER NOT NULL,
    data TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS known_chunks (phrase TEXT PRIMARY KEY);
"""


class SQLiteCardStore:
    def __init__(self, db_path: Path):
        self._db_path = db_path

    @staticmethod
    def _row_to_card(row) -> SavedCard:
        card_id, created, next_review, stage, data = row
        return SavedCard(**json.loads(data), id=card_id, created=created, next_review=next_review, stage=stage)

    async def save_card(self, card: ExpressionCard, today: Optional[date] = None) -> SavedCard:
        base = today or date.today()
        try:
            async with aiosqlite.connect(self._db_path) as conn:
                await conn.executescript(_SCHEMA)
                async with conn.execute("SELECT COUNT(*) FROM cards") as cur:
                    (count,) = await cur.fetchone()
                card_id = f"C{count + 1:04d}"
                next_review = (base + timedelta(days=REVIEW_INTERVALS_DAYS[0])).isoformat()
                saved = SavedCard(**card.model_dump(), id=card_id, created=base.isoformat(),
                                   next_review=next_review, stage=0)
                await conn.execute(
                    "INSERT INTO cards (id, created, next_review, stage, data) VALUES (?, ?, ?, ?, ?)",
                    (saved.id, saved.created, saved.next_review, saved.stage, card.model_dump_json()),
                )
                for chunk in card.chunks:
                    await conn.execute("INSERT OR IGNORE INTO known_chunks (phrase) VALUES (?)", (chunk.phrase,))
                await conn.commit()
                return saved
        except sqlite3.Error as e:
            raise CoachError("STORE_ERROR", detail=str(e)) from e

    async def list_cards(self) -> list[SavedCard]:
        try:
            async with aiosqlite.connect(self._db_path) as conn:
                await conn.executescript(_SCHEMA)
                async with conn.execute(
                    "SELECT id, created, next_review, stage, data FROM cards ORDER BY created"
                ) as cur:
                    rows = await cur.fetchall()
                return [self._row_to_card(r) for r in rows]
        except sqlite3.Error as e:
            raise CoachError("STORE_ERROR", detail=str(e)) from e

    async def due_cards(self, today: Optional[date] = None) -> list[SavedCard]:
        base = (today or date.today()).isoformat()
        try:
            async with aiosqlite.connect(self._db_path) as conn:
                await conn.executescript(_SCHEMA)
                async with conn.execute(
                    "SELECT id, created, next_review, stage, data FROM cards WHERE next_review <= ? "
                    "ORDER BY next_review",
                    (base,),
                ) as cur:
                    rows = await cur.fetchall()
                return [self._row_to_card(r) for r in rows]
        except sqlite3.Error as e:
            raise CoachError("STORE_ERROR", detail=str(e)) from e

    async def review(self, card_id: str, outcome: ReviewOutcome, today: Optional[date] = None) -> SavedCard:
        base = today or date.today()
        try:
            async with aiosqlite.connect(self._db_path) as conn:
                await conn.executescript(_SCHEMA)
                async with conn.execute(
                    "SELECT id, created, next_review, stage, data FROM cards WHERE id = ?", (card_id,)
                ) as cur:
                    row = await cur.fetchone()
                if row is None:
                    raise CoachError("NOT_FOUND", detail=f"card_id={card_id}")
                card = self._row_to_card(row)
                stage = min(card.stage + 1, len(REVIEW_INTERVALS_DAYS) - 1) if outcome == "known" else 0
                next_review = (base + timedelta(days=REVIEW_INTERVALS_DAYS[stage])).isoformat()
                await conn.execute(
                    "UPDATE cards SET stage = ?, next_review = ? WHERE id = ?", (stage, next_review, card_id)
                )
                await conn.commit()
                return card.model_copy(update={"stage": stage, "next_review": next_review})
        except sqlite3.Error as e:
            raise CoachError("STORE_ERROR", detail=str(e)) from e

    async def known_chunks(self) -> list[str]:
        try:
            async with aiosqlite.connect(self._db_path) as conn:
                await conn.executescript(_SCHEMA)
                async with conn.execute("SELECT phrase FROM known_chunks") as cur:
                    rows = await cur.fetchall()
                return [r[0] for r in rows]
        except sqlite3.Error as e:
            raise CoachError("STORE_ERROR", detail=str(e)) from e
