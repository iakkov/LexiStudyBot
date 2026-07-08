from dataclasses import dataclass
import os

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    bot_token: str
    database_url: str
    openai_api_key: str
    openai_model: str


def load_config() -> Config:
    load_dotenv()
    token = os.getenv("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN не задан. Скопируйте .env.example в .env и добавьте токен.")
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL не задан. Укажите адрес PostgreSQL в .env.")
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY не задан. Добавьте ключ OpenAI API в .env.")
    return Config(
        bot_token=token,
        database_url=database_url,
        openai_api_key=api_key,
        openai_model=os.getenv("OPENAI_MODEL", "gpt-5.4-nano").strip(),
    )
