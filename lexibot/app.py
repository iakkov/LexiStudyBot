import logging

from aiogram import Bot, Dispatcher

from lexibot.config import load_config
from lexibot.db import CardRepository
from lexibot.handlers import create_router


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    config = load_config()
    repo = CardRepository(config.database_url)
    await repo.init()

    dispatcher = Dispatcher()
    dispatcher.include_router(create_router(repo))
    bot = Bot(config.bot_token)
    try:
        await dispatcher.start_polling(bot)
    finally:
        await bot.session.close()
        await repo.close()
