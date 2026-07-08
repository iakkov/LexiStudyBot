from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import asyncpg


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class Card:
    id: int
    user_id: int
    word: str
    meaning: str
    group_name: str
    repetitions: int
    interval_days: int
    ease_factor: float
    due_at: datetime
    learning_level: int = 1


class CardRepository:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.pool: asyncpg.Pool | None = None

    async def init(self) -> None:
        self.pool = await asyncpg.create_pool(self.database_url, min_size=1, max_size=10)
        async with self.pool.acquire() as connection:
            await connection.execute("""
                CREATE TABLE IF NOT EXISTS cards (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    word TEXT NOT NULL,
                    meaning TEXT NOT NULL,
                    group_name TEXT NOT NULL DEFAULT 'Без группы',
                    repetitions INTEGER NOT NULL DEFAULT 0,
                    interval_days INTEGER NOT NULL DEFAULT 0,
                    ease_factor DOUBLE PRECISION NOT NULL DEFAULT 2.5,
                    due_at TIMESTAMPTZ NOT NULL,
                    learning_level INTEGER NOT NULL DEFAULT 1
                        CHECK (learning_level BETWEEN 1 AND 5),
                    created_at TIMESTAMPTZ NOT NULL
                )
            """)
            await connection.execute(
                """CREATE UNIQUE INDEX IF NOT EXISTS idx_cards_user_word
                   ON cards(user_id, lower(word))"""
            )
            await connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_cards_due ON cards(user_id, due_at)"
            )

    async def close(self) -> None:
        if self.pool:
            await self.pool.close()

    def _pool(self) -> asyncpg.Pool:
        if not self.pool:
            raise RuntimeError("Репозиторий не инициализирован")
        return self.pool

    async def add(self, user_id: int, word: str, meaning: str, group_name: str) -> bool:
        now = utc_now()
        try:
            async with self._pool().acquire() as connection:
                await connection.execute(
                    """INSERT INTO cards
                       (user_id, word, meaning, group_name, due_at, created_at)
                       VALUES ($1, $2, $3, $4, $5, $6)""",
                    user_id, word.strip(), meaning.strip(), group_name.strip(), now, now,
                )
            return True
        except asyncpg.UniqueViolationError:
            return False

    async def list_grouped(self, user_id: int) -> dict[str, list[Card]]:
        async with self._pool().acquire() as connection:
            rows = await connection.fetch(
                """SELECT * FROM cards WHERE user_id = $1
                   ORDER BY lower(group_name), lower(word)""",
                user_id,
            )
        result: dict[str, list[Card]] = {}
        for row in rows:
            card = self._card(row)
            result.setdefault(card.group_name, []).append(card)
        return result

    async def due(self, user_id: int, limit: int = 20) -> list[Card]:
        async with self._pool().acquire() as connection:
            rows = await connection.fetch(
                """SELECT * FROM cards
                   WHERE user_id = $1 AND learning_level < 5 AND due_at <= $2
                   ORDER BY due_at, id LIMIT $3""",
                user_id, utc_now(), limit,
            )
        return [self._card(row) for row in rows]

    async def find_by_word(self, user_id: int, word: str) -> Card | None:
        async with self._pool().acquire() as connection:
            row = await connection.fetchrow(
                "SELECT * FROM cards WHERE user_id = $1 AND lower(word) = lower($2)",
                user_id, word.strip(),
            )
        return self._card(row) if row else None

    async def update(
        self, card_id: int, user_id: int, word: str, meaning: str, group_name: str,
    ) -> bool:
        try:
            async with self._pool().acquire() as connection:
                result = await connection.execute(
                    """UPDATE cards SET word = $1, meaning = $2, group_name = $3
                       WHERE id = $4 AND user_id = $5""",
                    word.strip(), meaning.strip(), group_name.strip(), card_id, user_id,
                )
            return result == "UPDATE 1"
        except asyncpg.UniqueViolationError:
            return False

    async def delete(self, card_id: int, user_id: int) -> bool:
        async with self._pool().acquire() as connection:
            result = await connection.execute(
                "DELETE FROM cards WHERE id = $1 AND user_id = $2", card_id, user_id
            )
        return result == "DELETE 1"

    async def get(self, card_id: int, user_id: int) -> Card | None:
        async with self._pool().acquire() as connection:
            row = await connection.fetchrow(
                "SELECT * FROM cards WHERE id = $1 AND user_id = $2", card_id, user_id
            )
        return self._card(row) if row else None

    async def save_review(
        self, card_id: int, user_id: int, repetitions: int,
        interval_days: int, ease_factor: float, due_at: datetime, learning_level: int,
    ) -> None:
        async with self._pool().acquire() as connection:
            await connection.execute(
                """UPDATE cards SET repetitions = $1, interval_days = $2,
                   ease_factor = $3, due_at = $4, learning_level = $5
                   WHERE id = $6 AND user_id = $7""",
                repetitions, interval_days, ease_factor, due_at,
                learning_level, card_id, user_id,
            )

    @staticmethod
    def _card(row: asyncpg.Record) -> Card:
        return Card(
            id=row["id"], user_id=row["user_id"], word=row["word"],
            meaning=row["meaning"], group_name=row["group_name"],
            repetitions=row["repetitions"], interval_days=row["interval_days"],
            ease_factor=row["ease_factor"], due_at=row["due_at"],
            learning_level=row["learning_level"],
        )
