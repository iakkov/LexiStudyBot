from dataclasses import dataclass
from datetime import datetime, timedelta

from lexibot.db import Card


@dataclass(frozen=True)
class ReviewResult:
    repetitions: int
    interval_days: int
    ease_factor: float
    due_at: datetime
    learning_level: int


def schedule(card: Card, quality: int, now: datetime) -> ReviewResult:
    """Уровни Эббингауза. quality: 0=не помню, 3=трудно, 4=помню, 5=легко."""
    if quality < 3:
        repetitions = 0
        interval = 0
        due_at = now + timedelta(minutes=15)
        level = max(1, card.learning_level - 1)
    elif quality == 3:
        repetitions = card.repetitions + 1
        interval = 1
        due_at = now + timedelta(days=interval)
        level = card.learning_level
    else:
        repetitions = card.repetitions + 1
        level = min(5, card.learning_level + 1)
        # Интервалы между успешными повторениями приближены к кривой забывания.
        interval = {2: 1, 3: 3, 4: 7, 5: 30}[level]
        due_at = now + timedelta(days=interval)

    ease = card.ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    ease = max(1.3, round(ease, 2))
    return ReviewResult(repetitions, interval, ease, due_at, level)
