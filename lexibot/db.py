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
    language: str = "en"
    example: str = ""
    explanation: str = ""
    comment: str = ""


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
                "ALTER TABLE cards ADD COLUMN IF NOT EXISTS language TEXT NOT NULL DEFAULT 'en'"
            )
            await connection.execute(
                "ALTER TABLE cards ADD COLUMN IF NOT EXISTS example TEXT NOT NULL DEFAULT ''"
            )
            await connection.execute(
                "ALTER TABLE cards ADD COLUMN IF NOT EXISTS explanation TEXT NOT NULL DEFAULT ''"
            )
            await connection.execute(
                "ALTER TABLE cards ADD COLUMN IF NOT EXISTS comment TEXT NOT NULL DEFAULT ''"
            )
            await connection.execute("""
                CREATE TABLE IF NOT EXISTS user_settings (
                    user_id BIGINT PRIMARY KEY,
                    language TEXT NOT NULL DEFAULT 'en' CHECK (language IN ('en', 'es'))
                )
            """)
            await connection.execute("DROP INDEX IF EXISTS idx_cards_user_word")
            await connection.execute(
                """CREATE UNIQUE INDEX IF NOT EXISTS idx_cards_user_word
                   ON cards(user_id, language, lower(word))"""
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

    async def add(
        self, user_id: int, word: str, translation: str, language: str,
        example: str = "", explanation: str = "", comment: str = "",
    ) -> bool:
        now = utc_now()
        try:
            async with self._pool().acquire() as connection:
                await connection.execute(
                    """INSERT INTO cards
                       (user_id, word, meaning, group_name, due_at, created_at,
                        language, example, explanation, comment)
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)""",
                    user_id, word.strip(), translation.strip(), language, now, now,
                    language, example.strip(), explanation.strip(), comment.strip(),
                )
            return True
        except asyncpg.UniqueViolationError:
            return False

    async def list_grouped(self, user_id: int, language: str = "en") -> dict[str, list[Card]]:
        async with self._pool().acquire() as connection:
            rows = await connection.fetch(
                """SELECT * FROM cards WHERE user_id = $1 AND language = $2
                   ORDER BY lower(word)""",
                user_id, language,
            )
        result: dict[str, list[Card]] = {}
        for row in rows:
            card = self._card(row)
            result.setdefault(card.group_name, []).append(card)
        return result

    async def due(self, user_id: int, language: str = "en", limit: int = 20) -> list[Card]:
        async with self._pool().acquire() as connection:
            rows = await connection.fetch(
                """SELECT * FROM cards
                   WHERE user_id = $1 AND language = $2
                     AND learning_level < 5 AND due_at <= $3
                   ORDER BY due_at, id LIMIT $4""",
                user_id, language, utc_now(), limit,
            )
        return [self._card(row) for row in rows]

    async def find_by_word(self, user_id: int, word: str, language: str = "en") -> Card | None:
        async with self._pool().acquire() as connection:
            row = await connection.fetchrow(
                """SELECT * FROM cards
                   WHERE user_id = $1 AND language = $2 AND lower(word) = lower($3)""",
                user_id, language, word.strip(),
            )
        return self._card(row) if row else None

    async def update(
        self, card_id: int, user_id: int, word: str, translation: str,
        example: str, explanation: str, comment: str,
    ) -> bool:
        try:
            async with self._pool().acquire() as connection:
                result = await connection.execute(
                    """UPDATE cards SET word = $1, meaning = $2, example = $3,
                       explanation = $4, comment = $5 WHERE id = $6 AND user_id = $7""",
                    word.strip(), translation.strip(), example.strip(), explanation.strip(),
                    comment.strip(), card_id, user_id,
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

    async def get_language(self, user_id: int) -> str:
        async with self._pool().acquire() as connection:
            value = await connection.fetchval(
                "SELECT language FROM user_settings WHERE user_id = $1", user_id
            )
        return value or "en"

    async def set_language(self, user_id: int, language: str) -> None:
        async with self._pool().acquire() as connection:
            await connection.execute(
                """INSERT INTO user_settings (user_id, language) VALUES ($1, $2)
                   ON CONFLICT (user_id) DO UPDATE SET language = EXCLUDED.language""",
                user_id, language,
            )

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
            language=row["language"], example=row["example"],
            explanation=row["explanation"], comment=row["comment"],
        )
