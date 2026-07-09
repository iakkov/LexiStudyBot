from datetime import datetime, timezone

from lexibot.db import Card
from lexibot.handlers import highlight_word, study_prompt


def test_highlights_word_case_insensitively():
    assert highlight_word("Apple is an apple.", "apple") == (
        "<b>Apple</b> is an <b>apple</b>."
    )


def test_does_not_highlight_inside_another_word():
    assert highlight_word("A cat is in a category.", "cat") == (
        "A <b>cat</b> is in a category."
    )


def test_escapes_html_around_highlight():
    assert highlight_word("Use <run> & run.", "run") == (
        "Use &lt;<b>run</b>&gt; &amp; <b>run</b>."
    )


def sample_card():
    return Card(
        1, 1, "negotiate", "договариваться", "Без группы",
        0, 0, 2.5, datetime.now(timezone.utc), 1, "en",
        "We need to negotiate the contract.",
        "to discuss something to reach an agreement",
        "work",
    )


def test_study_prompt_word_to_translation():
    assert "слово → перевод" in study_prompt(sample_card(), "word_to_translation")
    assert "<b>negotiate</b>" in study_prompt(sample_card(), "word_to_translation")


def test_study_prompt_translation_to_word():
    assert "перевод → слово" in study_prompt(sample_card(), "translation_to_word")
    assert "<b>договариваться</b>" in study_prompt(sample_card(), "translation_to_word")


def test_study_prompt_explanation_to_word():
    assert "объяснение → слово" in study_prompt(sample_card(), "explanation_to_word")
    assert "to discuss something" in study_prompt(sample_card(), "explanation_to_word")
