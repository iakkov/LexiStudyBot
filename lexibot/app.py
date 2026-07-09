import asyncio
import contextlib
import logging

from aiogram import Bot, Dispatcher

from lexibot.config import load_config
from lexibot.db import CardRepository
from lexibot.handlers import create_router
from lexibot.generator import CardGenerator
from lexibot.reminders import reminder_loop


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    config = load_config()
    repo = CardRepository(config.database_url)
    await repo.init()
    generator = CardGenerator(config.openai_api_key, config.openai_model)

    dispatcher = Dispatcher()
    dispatcher.include_router(create_router(repo, generator))
    bot = Bot(config.bot_token)
    reminders_task = asyncio.create_task(
        reminder_loop(
            bot,
            repo,
            config.reminder_timezone,
            config.reminder_check_interval_seconds,
        )
    )
    try:
        await dispatcher.start_polling(bot)
    finally:
        reminders_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await reminders_task
        await bot.session.close()
        await repo.close()
