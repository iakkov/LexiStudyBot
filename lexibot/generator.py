from openai import AsyncOpenAI
from pydantic import BaseModel, Field


LANGUAGE_NAMES = {"en": "English", "es": "Español"}

GOAL_PROMPTS = {
    "work": (
        "Prefer work, business, meetings, email, negotiations, management, "
        "sales, finance, product, hiring, and professional communication contexts."
    ),
    "travel": (
        "Prefer travel contexts such as airports, hotels, restaurants, transport, "
        "directions, booking, tickets, sightseeing, and everyday tourist situations."
    ),
    "exam": (
        "Prefer exam-preparation contexts: clear academic-style examples, precise usage, "
        "common test vocabulary, paraphrasing, and definitions useful for language exams."
    ),
    "media": (
        "Prefer exam-preparation contexts: clear academic-style examples, precise usage, "
        "common test vocabulary, paraphrasing, and definitions useful for language exams."
    ),
    "general": (
        "Prefer practical everyday contexts that are useful for general language learning."
    ),
}

LEVEL_PROMPTS = {
    "beginner": (
        "Use simple A1-A2 vocabulary and short sentences. Keep the explanation very easy."
    ),
    "intermediate": (
        "Use natural B1-B2 language with moderately complex sentences and useful collocations."
    ),
    "advanced": (
        "Use richer C1+ language, more nuanced examples, and a more precise explanation."
    ),
}


class GeneratedCard(BaseModel):
    normalized_word: str = Field(description="Correct dictionary form of the submitted word")
    example: str = Field(description="A natural example sentence containing the word")
    explanation: str = Field(description="A concise definition in the language being learned")
    translation: str = Field(description="A concise Russian translation")


class CardGenerator:
    def __init__(self, api_key: str, model: str):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    @staticmethod
    def system_prompt(language: str, learning_goal: str, learning_level: str) -> str:
        language_name = LANGUAGE_NAMES[language]
        goal_instruction = GOAL_PROMPTS.get(learning_goal, GOAL_PROMPTS["general"])
        level_instruction = LEVEL_PROMPTS.get(learning_level, LEVEL_PROMPTS["beginner"])
        return (
            "You create accurate vocabulary flashcards. "
            f"The target language is {language_name}. "
            "Use the target language for the example and explanation, "
            "and Russian only for translation. Keep every field concise. "
            "Correct obvious spelling or inflection issues in normalized_word. "
            "The example must contain normalized_word exactly, preserving its spelling. "
            f"Learning goal: {learning_goal}. {goal_instruction} "
            f"Learner level: {learning_level}. {level_instruction}"
        )

    async def generate(
        self, word: str, language: str, comment: str,
        learning_goal: str = "general", learning_level: str = "beginner",
    ) -> GeneratedCard:
        response = await self.client.responses.parse(
            model=self.model,
            input=[
                {
                    "role": "system",
                    "content": self.system_prompt(language, learning_goal, learning_level),
                },
                {
                    "role": "user",
                    "content": f"Word: {word}\nUser context: {comment or 'none'}",
                },
            ],
            text_format=GeneratedCard,
        )
        if not response.output_parsed:
            raise RuntimeError("OpenAI не вернул данные карточки")
        return response.output_parsed
