from lexibot.db import ReminderCandidate
from lexibot.reminders import reminder_message


def test_reminder_message_uses_singular_card_form():
    message = reminder_message(ReminderCandidate(user_id=1, language="en", due_count=1))

    assert "1 карточка" in message
    assert "English" in message


def test_reminder_message_uses_few_cards_form():
    message = reminder_message(ReminderCandidate(user_id=1, language="es", due_count=3))

    assert "3 карточки" in message
    assert "Español" in message


def test_reminder_message_uses_many_cards_form():
    message = reminder_message(ReminderCandidate(user_id=1, language="en", due_count=12))

    assert "12 карточек" in message
