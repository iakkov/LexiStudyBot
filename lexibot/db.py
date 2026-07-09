from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any

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


@dataclass(frozen=True)
class UserSettings:
    user_id: int
    language: str = "en"
    onboarding_completed: bool = False
    learning_goal: str = "general"
    learning_level: str = "beginner"
    reminder_time: str | None = None
    last_reminder_sent_on: date | None = None


@dataclass(frozen=True)
class ReminderCandidate:
    user_id: int
    language: str
    due_count: int


@dataclass(frozen=True)
class CardStats:
    total: int = 0
    new: int = 0
    weak: int = 0
    good: int = 0
    almost_learned: int = 0
    learned: int = 0


@dataclass(frozen=True)
class ProductAnalytics:
    total_users: int = 0
    active_users_today: int = 0
    active_users_7d: int = 0
    started_today: int = 0
    started_7d: int = 0
    onboarding_completed_today: int = 0
    onboarding_completed_7d: int = 0
    cards_added_today: int = 0
    cards_added_7d: int = 0
    study_started_today: int = 0
    study_started_7d: int = 0
    cards_reviewed_today: int = 0
    cards_reviewed_7d: int = 0
    study_completed_today: int = 0
    study_completed_7d: int = 0
    reminders_sent_today: int = 0
    reminders_sent_7d: int = 0
    tts_clicked_today: int = 0
    tts_clicked_7d: int = 0
    settings_opened_today: int = 0
    stats_opened_today: int = 0


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
            await connection.execute(
                """ALTER TABLE user_settings
                   ADD COLUMN IF NOT EXISTS onboarding_completed BOOLEAN NOT NULL DEFAULT FALSE"""
            )
            await connection.execute(
                """ALTER TABLE user_settings
                   ADD COLUMN IF NOT EXISTS learning_goal TEXT NOT NULL DEFAULT 'general'"""
            )
            await connection.execute(
                """ALTER TABLE user_settings
                   ADD COLUMN IF NOT EXISTS learning_level TEXT NOT NULL DEFAULT 'beginner'"""
            )
            await connection.execute(
                "ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS reminder_time TEXT"
            )
            await connection.execute(
                "ALTER TABLE user_settings ADD COLUMN IF NOT EXISTS last_reminder_sent_on DATE"
            )
            await connection.execute("""
                CREATE TABLE IF NOT EXISTS study_days (
                    user_id BIGINT NOT NULL,
                    studied_on DATE NOT NULL,
                    reviews_count INTEGER NOT NULL DEFAULT 0,
                    PRIMARY KEY (user_id, studied_on)
                )
            """)
            await connection.execute("""
                CREATE TABLE IF NOT EXISTS analytics_events (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT,
                    event_name TEXT NOT NULL,
                    event_data JSONB NOT NULL DEFAULT '{}'::jsonb,
                    created_at TIMESTAMPTZ NOT NULL
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
            await connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_study_days_user_date ON study_days(user_id, studied_on)"
            )
            await connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_analytics_events_created_at ON analytics_events(created_at)"
            )
            await connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_analytics_events_name_created_at ON analytics_events(event_name, created_at)"
            )
            await connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_analytics_events_user_created_at ON analytics_events(user_id, created_at)"
            )

    async def close(self) -> None:
        if self.pool:
            await self.pool.close()

    def _pool(self) -> asyncpg.Pool:
        if not self.pool:
            raise RuntimeError("Репозиторий не инициализирован")
        return self.pool

    async def track_event(
        self, user_id: int | None, event_name: str,
        event_data: Mapping[str, Any] | None = None,
    ) -> None:
        payload = json.dumps(dict(event_data or {}), ensure_ascii=False)
        async with self._pool().acquire() as connection:
            await connection.execute(
                """INSERT INTO analytics_events
                   (user_id, event_name, event_data, created_at)
                   VALUES ($1, $2, $3::jsonb, $4)""",
                user_id, event_name, payload, utc_now(),
            )

    async def product_analytics(self) -> ProductAnalytics:
        async with self._pool().acquire() as connection:
            row = await connection.fetchrow(
                """WITH boundaries AS (
                       SELECT
                         date_trunc('day', now()) AS today_start,
                         now() - interval '7 days' AS week_start
                   )
                   SELECT
                     count(DISTINCT user_id) FILTER (WHERE user_id IS NOT NULL)::int AS total_users,
                     count(DISTINCT user_id) FILTER (
                       WHERE user_id IS NOT NULL AND created_at >= today_start
                     )::int AS active_users_today,
                     count(DISTINCT user_id) FILTER (
                       WHERE user_id IS NOT NULL AND created_at >= week_start
                     )::int AS active_users_7d,
                     count(*) FILTER (
                       WHERE event_name = 'bot_started' AND created_at >= today_start
                     )::int AS started_today,
                     count(*) FILTER (
                       WHERE event_name = 'bot_started' AND created_at >= week_start
                     )::int AS started_7d,
                     count(*) FILTER (
                       WHERE event_name = 'onboarding_completed' AND created_at >= today_start
                     )::int AS onboarding_completed_today,
                     count(*) FILTER (
                       WHERE event_name = 'onboarding_completed' AND created_at >= week_start
                     )::int AS onboarding_completed_7d,
                     count(*) FILTER (
                       WHERE event_name = 'card_added' AND created_at >= today_start
                     )::int AS cards_added_today,
                     count(*) FILTER (
                       WHERE event_name = 'card_added' AND created_at >= week_start
                     )::int AS cards_added_7d,
                     count(*) FILTER (
                       WHERE event_name = 'study_started' AND created_at >= today_start
                     )::int AS study_started_today,
                     count(*) FILTER (
                       WHERE event_name = 'study_started' AND created_at >= week_start
                     )::int AS study_started_7d,
                     count(*) FILTER (
                       WHERE event_name = 'study_card_reviewed' AND created_at >= today_start
                     )::int AS cards_reviewed_today,
                     count(*) FILTER (
                       WHERE event_name = 'study_card_reviewed' AND created_at >= week_start
                     )::int AS cards_reviewed_7d,
                     count(*) FILTER (
                       WHERE event_name = 'study_completed' AND created_at >= today_start
                     )::int AS study_completed_today,
                     count(*) FILTER (
                       WHERE event_name = 'study_completed' AND created_at >= week_start
                     )::int AS study_completed_7d,
                     count(*) FILTER (
                       WHERE event_name = 'reminder_sent' AND created_at >= today_start
                     )::int AS reminders_sent_today,
                     count(*) FILTER (
                       WHERE event_name = 'reminder_sent' AND created_at >= week_start
                     )::int AS reminders_sent_7d,
                     count(*) FILTER (
                       WHERE event_name = 'tts_clicked' AND created_at >= today_start
                     )::int AS tts_clicked_today,
                     count(*) FILTER (
                       WHERE event_name = 'tts_clicked' AND created_at >= week_start
                     )::int AS tts_clicked_7d,
                     count(*) FILTER (
                       WHERE event_name = 'settings_opened' AND created_at >= today_start
                     )::int AS settings_opened_today,
                     count(*) FILTER (
                       WHERE event_name = 'stats_opened' AND created_at >= today_start
                     )::int AS stats_opened_today
                   FROM analytics_events, boundaries"""
            )
        return ProductAnalytics(**dict(row))

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

    async def get_settings(self, user_id: int) -> UserSettings:
        async with self._pool().acquire() as connection:
            row = await connection.fetchrow(
                "SELECT * FROM user_settings WHERE user_id = $1", user_id
            )
        if not row:
            return UserSettings(user_id=user_id)
        return UserSettings(
            user_id=row["user_id"],
            language=row["language"],
            onboarding_completed=row["onboarding_completed"],
            learning_goal=row["learning_goal"],
            learning_level=row["learning_level"],
            reminder_time=row["reminder_time"],
            last_reminder_sent_on=row["last_reminder_sent_on"],
        )

    async def set_language(self, user_id: int, language: str) -> None:
        async with self._pool().acquire() as connection:
            await connection.execute(
                """INSERT INTO user_settings (user_id, language) VALUES ($1, $2)
                   ON CONFLICT (user_id) DO UPDATE SET language = EXCLUDED.language""",
                user_id, language,
            )

    async def set_learning_goal(self, user_id: int, learning_goal: str) -> None:
        async with self._pool().acquire() as connection:
            await connection.execute(
                """INSERT INTO user_settings (user_id, learning_goal)
                   VALUES ($1, $2)
                   ON CONFLICT (user_id) DO UPDATE SET
                       learning_goal = EXCLUDED.learning_goal""",
                user_id, learning_goal,
            )

    async def set_learning_level(self, user_id: int, learning_level: str) -> None:
        async with self._pool().acquire() as connection:
            await connection.execute(
                """INSERT INTO user_settings (user_id, learning_level)
                   VALUES ($1, $2)
                   ON CONFLICT (user_id) DO UPDATE SET
                       learning_level = EXCLUDED.learning_level""",
                user_id, learning_level,
            )

    async def set_reminder_time(self, user_id: int, reminder_time: str | None) -> None:
        async with self._pool().acquire() as connection:
            await connection.execute(
                """INSERT INTO user_settings
                   (user_id, reminder_time, last_reminder_sent_on)
                   VALUES ($1, $2, NULL)
                   ON CONFLICT (user_id) DO UPDATE SET
                       reminder_time = EXCLUDED.reminder_time,
                       last_reminder_sent_on = NULL""",
                user_id, reminder_time,
            )

    async def save_onboarding(
        self, user_id: int, language: str, learning_goal: str,
        learning_level: str, reminder_time: str | None,
    ) -> None:
        async with self._pool().acquire() as connection:
            await connection.execute(
                """INSERT INTO user_settings
                   (user_id, language, onboarding_completed, learning_goal,
                    learning_level, reminder_time)
                   VALUES ($1, $2, TRUE, $3, $4, $5)
                   ON CONFLICT (user_id) DO UPDATE SET
                       language = EXCLUDED.language,
                       onboarding_completed = TRUE,
                       learning_goal = EXCLUDED.learning_goal,
                       learning_level = EXCLUDED.learning_level,
                       reminder_time = EXCLUDED.reminder_time,
                       last_reminder_sent_on = NULL""",
                user_id, language, learning_goal, learning_level, reminder_time,
            )

    async def reminder_candidates(
        self, current_time: str, current_date: date, limit: int = 100,
    ) -> list[ReminderCandidate]:
        async with self._pool().acquire() as connection:
            rows = await connection.fetch(
                """SELECT us.user_id, us.language, count(c.id)::int AS due_count
                   FROM user_settings us
                   JOIN cards c ON c.user_id = us.user_id
                    AND c.language = us.language
                    AND c.learning_level < 5
                    AND c.due_at <= $3
                   WHERE us.onboarding_completed = TRUE
                    AND us.reminder_time IS NOT NULL
                    AND us.reminder_time <= $1
                    AND (
                        us.last_reminder_sent_on IS NULL
                        OR us.last_reminder_sent_on < $2
                    )
                   GROUP BY us.user_id, us.language, us.reminder_time
                   ORDER BY us.reminder_time, us.user_id
                   LIMIT $4""",
                current_time, current_date, utc_now(), limit,
            )
        return [
            ReminderCandidate(
                user_id=row["user_id"], language=row["language"], due_count=row["due_count"]
            )
            for row in rows
        ]

    async def mark_reminder_sent(self, user_id: int, sent_on: date) -> None:
        async with self._pool().acquire() as connection:
            await connection.execute(
                """UPDATE user_settings
                   SET last_reminder_sent_on = $1
                   WHERE user_id = $2""",
                sent_on, user_id,
            )

    async def card_stats(self, user_id: int, language: str) -> CardStats:
        async with self._pool().acquire() as connection:
            row = await connection.fetchrow(
                """SELECT
                       count(*)::int AS total,
                       count(*) FILTER (WHERE learning_level = 1)::int AS new,
                       count(*) FILTER (WHERE learning_level = 2)::int AS weak,
                       count(*) FILTER (WHERE learning_level = 3)::int AS good,
                       count(*) FILTER (WHERE learning_level = 4)::int AS almost_learned,
                       count(*) FILTER (WHERE learning_level = 5)::int AS learned
                   FROM cards
                   WHERE user_id = $1 AND language = $2""",
                user_id, language,
            )
        return CardStats(
            total=row["total"],
            new=row["new"],
            weak=row["weak"],
            good=row["good"],
            almost_learned=row["almost_learned"],
            learned=row["learned"],
        )

    async def record_study_day(self, user_id: int, studied_on: date) -> None:
        async with self._pool().acquire() as connection:
            await connection.execute(
                """INSERT INTO study_days (user_id, studied_on, reviews_count)
                   VALUES ($1, $2, 1)
                   ON CONFLICT (user_id, studied_on) DO UPDATE SET
                       reviews_count = study_days.reviews_count + 1""",
                user_id, studied_on,
            )

    async def studied_on(self, user_id: int, studied_on: date) -> bool:
        async with self._pool().acquire() as connection:
            value = await connection.fetchval(
                """SELECT EXISTS(
                       SELECT 1 FROM study_days
                       WHERE user_id = $1 AND studied_on = $2
                   )""",
                user_id, studied_on,
            )
        return bool(value)

    async def streak_days(self, user_id: int, current_date: date) -> int:
        async with self._pool().acquire() as connection:
            rows = await connection.fetch(
                """SELECT studied_on
                   FROM study_days
                   WHERE user_id = $1 AND studied_on <= $2
                   ORDER BY studied_on DESC""",
                user_id, current_date,
            )
        if not rows:
            return 0
        first_day = rows[0]["studied_on"]
        if first_day == current_date:
            expected = current_date
        elif first_day == current_date - timedelta(days=1):
            expected = current_date - timedelta(days=1)
        else:
            return 0
        streak = 0
        for row in rows:
            studied_on = row["studied_on"]
            if studied_on == expected:
                streak += 1
                expected = expected - timedelta(days=1)
                continue
            if studied_on < expected:
                break
        return streak

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
