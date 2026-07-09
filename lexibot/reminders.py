from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiogram import Bot

from lexibot.db import CardRepository, ReminderCandidate
from lexibot.generator import LANGUAGE_NAMES
from lexibot.keyboards import main_menu


logger = logging.getLogger(__name__)


def reminder_message(candidate: ReminderCandidate) -> str:
    word_form = "карточек"
    if candidate.due_count % 10 == 1 and candidate.due_count % 100 != 11:
        word_form = "карточка"
    elif candidate.due_count % 10 in (2, 3, 4) and candidate.due_count % 100 not in (12, 13, 14):
        word_form = "карточки"

    return (
        "⏰ Пора повторить слова\n\n"
        f"В разделе {LANGUAGE_NAMES[candidate.language]} готово к повторению: "
        f"{candidate.due_count} {word_form}.\n\n"
        "Нажми 🎓 Учить — это займёт всего несколько минут."
    )


async def send_due_reminders(
    bot: Bot, repo: CardRepository, timezone_name: str, limit: int = 100,
) -> int:
    try:
        timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        logger.warning("Unknown reminder timezone %s, falling back to UTC", timezone_name)
        timezone = ZoneInfo("UTC")

    local_now = datetime.now(timezone)
    candidates = await repo.reminder_candidates(
        current_time=local_now.strftime("%H:%M"),
        current_date=local_now.date(),
        limit=limit,
    )

    sent = 0
    for candidate in candidates:
        try:
            await bot.send_message(
                candidate.user_id,
                reminder_message(candidate),
                reply_markup=main_menu(),
            )
            sent += 1
        except Exception:
            logger.exception("Failed to send reminder to user %s", candidate.user_id)
        finally:
            await repo.mark_reminder_sent(candidate.user_id, local_now.date())
    return sent


async def reminder_loop(
    bot: Bot, repo: CardRepository, timezone_name: str, interval_seconds: int,
) -> None:
    logger.info(
        "Reminder scheduler started: timezone=%s interval=%ss",
        timezone_name,
        interval_seconds,
    )
    while True:
        try:
            sent = await send_due_reminders(bot, repo, timezone_name)
            if sent:
                logger.info("Sent %s due-word reminders", sent)
        except asyncio.CancelledError:
            logger.info("Reminder scheduler stopped")
            raise
        except Exception:
            logger.exception("Reminder scheduler iteration failed")
        await asyncio.sleep(interval_seconds)
