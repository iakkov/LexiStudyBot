from openai import AsyncOpenAI
from pydantic import BaseModel, Field


LANGUAGE_NAMES = {"en": "English", "es": "Español"}


class GeneratedCard(BaseModel):
    normalized_word: str = Field(description="Correct dictionary form of the submitted word")
    example: str = Field(description="A natural example sentence containing the word")
    explanation: str = Field(description="A concise definition in the language being learned")
    translation: str = Field(description="A concise Russian translation")


class CardGenerator:
    def __init__(self, api_key: str, model: str):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def generate(self, word: str, language: str, comment: str) -> GeneratedCard:
        language_name = LANGUAGE_NAMES[language]
        response = await self.client.responses.parse(
            model=self.model,
            input=[
                {
                    "role": "system",
                    "content": (
                        "You create accurate vocabulary flashcards. "
                        f"The target language is {language_name}. "
                        "Use the target language for the example and explanation, "
                        "and Russian only for translation. Keep every field concise. "
                        "Correct obvious spelling or inflection issues in normalized_word. "
                        "The example must contain normalized_word exactly, preserving its spelling."
                    ),
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
