from datetime import datetime, timezone

from lexibot.db import Card
from lexibot.scheduler import schedule


NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def card(repetitions=0, interval=0, ease=2.5, level=1):
    return Card(1, 1, "word", "слово", "Без группы", repetitions, interval, ease, NOW, level)


def test_first_success_is_due_tomorrow():
    result = schedule(card(), 4, NOW)
    assert result.repetitions == 1
    assert result.interval_days == 1
    assert (result.due_at - NOW).days == 1
    assert result.learning_level == 2


def test_failure_resets_and_retries_in_fifteen_minutes():
    result = schedule(card(3, 10), 0, NOW)
    assert result.repetitions == 0
    assert result.interval_days == 0
    assert int((result.due_at - NOW).total_seconds()) == 900


def test_fourth_success_marks_card_as_learned():
    result = schedule(card(level=4), 4, NOW)
    assert result.learning_level == 5


def test_hard_answer_keeps_current_level():
    result = schedule(card(level=3), 3, NOW)
    assert result.learning_level == 3


def test_ease_never_drops_below_floor():
    result = schedule(card(ease=1.3), 0, NOW)
    assert result.ease_factor == 1.3
