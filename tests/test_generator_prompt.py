from lexibot.generator import CardGenerator


def test_prompt_uses_travel_goal_context():
    prompt = CardGenerator.system_prompt("en", "travel", "beginner")

    assert "airports" in prompt
    assert "hotels" in prompt
    assert "A1-A2" in prompt


def test_prompt_uses_work_goal_context():
    prompt = CardGenerator.system_prompt("en", "work", "intermediate")

    assert "business" in prompt
    assert "meetings" in prompt
    assert "B1-B2" in prompt


def test_prompt_uses_exam_goal_context_and_advanced_level():
    prompt = CardGenerator.system_prompt("es", "exam", "advanced")

    assert "exam-preparation" in prompt
    assert "C1+" in prompt
    assert "Español" in prompt
