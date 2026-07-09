import logging
import re
from datetime import datetime, timezone
from html import escape
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from lexibot.db import Card, CardRepository
from lexibot.generator import CardGenerator, LANGUAGE_NAMES
from lexibot.keyboards import (
    ADD_BUTTON,
    CANCEL_BUTTON,
    DELETE_BUTTON,
    EDIT_BUTTON,
    ENGLISH_BUTTON,
    LIST_BUTTON,
    SETTINGS_BUTTON,
    SPANISH_BUTTON,
    STATS_BUTTON,
    STUDY_BUTTON,
    cancel_menu,
    delete_keyboard,
    grade_keyboard,
    main_menu,
    onboarding_goal_keyboard,
    onboarding_language_keyboard,
    onboarding_level_keyboard,
    onboarding_reminder_keyboard,
    pronunciation_keyboard,
    reveal_keyboard,
    settings_goal_keyboard,
    settings_language_keyboard,
    settings_level_keyboard,
    settings_menu_keyboard,
    settings_reminder_keyboard,
)
from lexibot.scheduler import schedule
from lexibot.tts import synthesize_word


logger = logging.getLogger(__name__)


class AddCard(StatesGroup):
    word = State()
    comment = State()


class EditCard(StatesGroup):
    search = State()
    word = State()
    comment = State()


class DeleteCard(StatesGroup):
    search = State()
    confirm = State()


class Onboarding(StatesGroup):
    language = State()
    goal = State()
    level = State()
    reminder = State()


LEVEL_NAMES = {
    1: "новое",
    2: "плохо выучено",
    3: "хорошо выучено",
    4: "отлично · осталось 1 повторение",
    5: "выучено",
}

GOAL_NAMES = {
    "work": "работа и бизнес",
    "travel": "путешествия",
    "media": "фильмы и сериалы",
    "general": "общее обучение",
}

USER_LEVEL_NAMES = {
    "beginner": "A1–A2 · начинаю",
    "intermediate": "B1–B2 · уже говорю",
    "advanced": "C1+ · продвинутый",
}


def streak_badge(today_done: bool) -> str:
    return "🔥" if today_done else "⚪"


def highlight_word(text: str, word: str) -> str:
    """Escape HTML and bold exact whole-word occurrences."""
    pattern = re.compile(rf"(?<!\w){re.escape(word)}(?!\w)", re.IGNORECASE)
    pieces: list[str] = []
    position = 0
    for match in pattern.finditer(text):
        pieces.append(escape(text[position:match.start()]))
        pieces.append(f"<b>{escape(match.group())}</b>")
        position = match.end()
    pieces.append(escape(text[position:]))
    return "".join(pieces)


def full_card(card: Card) -> str:
    parts = [
        f"<b>{escape(card.word)}</b>",
        f"<b>Пример:</b> {highlight_word(card.example, card.word)}",
        f"<b>Объяснение:</b> {escape(card.explanation)}",
        f"<b>Перевод:</b> {escape(card.meaning)}",
    ]
    if card.comment:
        parts.append(f"<b>Комментарий:</b> {escape(card.comment)}")
    return "\n\n".join(parts)


def settings_text(settings) -> str:
    reminder = settings.reminder_time or "выключены"
    return (
        "⚙️ Настройки обучения\n\n"
        f"Язык: {LANGUAGE_NAMES[settings.language]}\n"
        f"Цель: {GOAL_NAMES.get(settings.learning_goal, settings.learning_goal)}\n"
        f"Уровень: {USER_LEVEL_NAMES.get(settings.learning_level, settings.learning_level)}\n"
        f"Напоминания: {reminder}\n\n"
        "Что хочешь изменить?"
    )


def create_router(
    repo: CardRepository, generator: CardGenerator, timezone_name: str = "Europe/Moscow",
) -> Router:
    router = Router()
    try:
        user_timezone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        logger.warning("Unknown user timezone %s, falling back to UTC", timezone_name)
        user_timezone = ZoneInfo("UTC")

    async def language(user_id: int) -> str:
        return await repo.get_language(user_id)

    def local_today():
        return datetime.now(user_timezone).date()

    async def streak_line(user_id: int) -> str:
        today = local_today()
        today_done = await repo.studied_on(user_id, today)
        streak = await repo.streak_days(user_id, today)
        return f"{streak_badge(today_done)} Серия дней подряд: {streak}"

    async def stats_text(user_id: int) -> str:
        active_language = await language(user_id)
        stats = await repo.card_stats(user_id, active_language)
        return (
            f"📊 <b>Статистика · {LANGUAGE_NAMES[active_language]}</b>\n\n"
            f"Всего слов добавлено: <b>{stats.total}</b>\n"
            f"Новых: <b>{stats.new}</b>\n"
            f"Плохо выученных: <b>{stats.weak}</b>\n"
            f"Хорошо: <b>{stats.good}</b>\n"
            f"Почти выучено: <b>{stats.almost_learned}</b>\n"
            f"Выучено: <b>{stats.learned}</b>\n\n"
            f"{await streak_line(user_id)}\n\n"
            "День засчитывается, когда ты повторил хотя бы одну карточку."
        )

    async def send_help(message: Message) -> None:
        active = LANGUAGE_NAMES[await language(message.from_user.id)]
        await message.answer(
            "Я создаю словарные карточки с помощью ИИ и помогаю их повторять.\n\n"
            f"Текущий режим: {active}\n"
            "Выбери язык кнопкой 🇬🇧 English или 🇪🇸 Español.\n\n"
            "/addnew — добавить слово и свой комментарий\n"
            "/list — показать словарь выбранного языка\n"
            "/study — начать повторение\n"
            "/stats — статистика и серия дней\n"
            "/edit — изменить и заново сгенерировать карточку\n"
            "/delete — удалить карточку\n"
            "/settings — настройки обучения\n"
            "/cancel — отменить ввод",
            reply_markup=main_menu(),
        )

    async def begin_onboarding(message: Message, state: FSMContext, restart: bool = False) -> None:
        await state.clear()
        await state.set_state(Onboarding.language)
        intro = (
            "Давай быстро настроим твой личный словарь — займёт меньше минуты.\n\n"
            "Как это работает:\n"
            "1) выбираешь язык;\n"
            "2) добавляешь слово и короткий комментарий;\n"
            "3) бот сам создаёт пример, объяснение, перевод и озвучку;\n"
            "4) кнопка 🎓 Учить показывает слова, которые пора повторить."
        )
        if restart:
            intro = "Окей, перенастроим обучение.\n\n" + intro
        await message.answer(
            intro + "\n\nС какого языка начнём?",
            reply_markup=onboarding_language_keyboard(),
        )

    @router.message(CommandStart())
    async def start_command(message: Message, state: FSMContext) -> None:
        settings = await repo.get_settings(message.from_user.id)
        if not settings.onboarding_completed:
            await begin_onboarding(message, state)
            return
        await send_help(message)

    @router.message(Command("help"))
    async def help_command(message: Message) -> None:
        await send_help(message)

    async def send_stats(message: Message, state: FSMContext | None = None) -> None:
        if state:
            await state.clear()
        await message.answer(
            await stats_text(message.from_user.id),
            parse_mode="HTML",
            reply_markup=main_menu(),
        )

    @router.message(Command("stats"))
    async def stats_command(message: Message) -> None:
        await send_stats(message)

    @router.message(F.text == STATS_BUTTON)
    async def stats_from_menu(message: Message, state: FSMContext) -> None:
        await send_stats(message, state)

    async def answer_settings(message: Message, state: FSMContext) -> None:
        await state.clear()
        settings = await repo.get_settings(message.from_user.id)
        await message.answer(
            settings_text(settings),
            reply_markup=settings_menu_keyboard(),
        )

    async def edit_settings(callback: CallbackQuery) -> None:
        settings = await repo.get_settings(callback.from_user.id)
        await callback.message.edit_text(
            settings_text(settings),
            reply_markup=settings_menu_keyboard(),
        )

    @router.message(Command("settings"))
    @router.message(F.text == SETTINGS_BUTTON)
    async def settings_command(message: Message, state: FSMContext) -> None:
        await answer_settings(message, state)

    @router.callback_query(F.data == "settings:edit:language")
    async def settings_edit_language(callback: CallbackQuery) -> None:
        await callback.message.edit_text(
            "Какой язык тренируем?",
            reply_markup=settings_language_keyboard(),
        )
        await callback.answer()

    @router.callback_query(F.data == "settings:edit:goal")
    async def settings_edit_goal(callback: CallbackQuery) -> None:
        await callback.message.edit_text(
            "Какая главная цель обучения?",
            reply_markup=settings_goal_keyboard(),
        )
        await callback.answer()

    @router.callback_query(F.data == "settings:edit:level")
    async def settings_edit_level(callback: CallbackQuery) -> None:
        await callback.message.edit_text(
            "Какой у тебя сейчас уровень?",
            reply_markup=settings_level_keyboard(),
        )
        await callback.answer()

    @router.callback_query(F.data == "settings:edit:reminder")
    async def settings_edit_reminder(callback: CallbackQuery) -> None:
        await callback.message.edit_text(
            "Когда удобно напоминать о повторении?",
            reply_markup=settings_reminder_keyboard(),
        )
        await callback.answer()

    @router.callback_query(F.data == "settings:back")
    async def settings_back(callback: CallbackQuery) -> None:
        await edit_settings(callback)
        await callback.answer()

    @router.callback_query(F.data == "settings:close")
    async def settings_close(callback: CallbackQuery) -> None:
        await callback.message.edit_text("Настройки закрыты ✅")
        await callback.message.answer("Выбери следующее действие:", reply_markup=main_menu())
        await callback.answer()

    @router.callback_query(F.data.startswith("settings:language:"))
    async def settings_save_language(callback: CallbackQuery) -> None:
        code = callback.data.split(":", 2)[2]
        if code not in LANGUAGE_NAMES:
            await callback.answer("Неизвестный язык", show_alert=True)
            return
        await repo.set_language(callback.from_user.id, code)
        await edit_settings(callback)
        await callback.answer("Язык обновлён")

    @router.callback_query(F.data.startswith("settings:goal:"))
    async def settings_save_goal(callback: CallbackQuery) -> None:
        goal = callback.data.split(":", 2)[2]
        if goal not in GOAL_NAMES:
            await callback.answer("Неизвестная цель", show_alert=True)
            return
        await repo.set_learning_goal(callback.from_user.id, goal)
        await edit_settings(callback)
        await callback.answer("Цель обновлена")

    @router.callback_query(F.data.startswith("settings:level:"))
    async def settings_save_level(callback: CallbackQuery) -> None:
        level = callback.data.split(":", 2)[2]
        if level not in USER_LEVEL_NAMES:
            await callback.answer("Неизвестный уровень", show_alert=True)
            return
        await repo.set_learning_level(callback.from_user.id, level)
        await edit_settings(callback)
        await callback.answer("Уровень обновлён")

    @router.callback_query(F.data.startswith("settings:reminder:"))
    async def settings_save_reminder(callback: CallbackQuery) -> None:
        reminder = callback.data.split(":", 2)[2]
        reminder_time = None if reminder == "off" else reminder
        await repo.set_reminder_time(callback.from_user.id, reminder_time)
        await edit_settings(callback)
        await callback.answer("Напоминание обновлено")

    @router.callback_query(Onboarding.language, F.data.startswith("onboarding:language:"))
    async def onboarding_language(callback: CallbackQuery, state: FSMContext) -> None:
        code = callback.data.split(":", 2)[2]
        if code not in LANGUAGE_NAMES:
            await callback.answer("Неизвестный язык", show_alert=True)
            return
        await state.update_data(language=code)
        await state.set_state(Onboarding.goal)
        await callback.message.edit_text(
            f"Отлично, режим: {LANGUAGE_NAMES[code]}.\n\n"
            "Какая главная цель у твоего словаря?",
            reply_markup=onboarding_goal_keyboard(),
        )
        await callback.answer()

    @router.callback_query(Onboarding.goal, F.data.startswith("onboarding:goal:"))
    async def onboarding_goal(callback: CallbackQuery, state: FSMContext) -> None:
        goal = callback.data.split(":", 2)[2]
        if goal not in GOAL_NAMES:
            await callback.answer("Неизвестная цель", show_alert=True)
            return
        await state.update_data(learning_goal=goal)
        await state.set_state(Onboarding.level)
        await callback.message.edit_text(
            f"Цель: {GOAL_NAMES[goal]}.\n\n"
            "Какой у тебя сейчас уровень?",
            reply_markup=onboarding_level_keyboard(),
        )
        await callback.answer()

    @router.callback_query(Onboarding.level, F.data.startswith("onboarding:level:"))
    async def onboarding_level(callback: CallbackQuery, state: FSMContext) -> None:
        level = callback.data.split(":", 2)[2]
        if level not in USER_LEVEL_NAMES:
            await callback.answer("Неизвестный уровень", show_alert=True)
            return
        await state.update_data(learning_level=level)
        await state.set_state(Onboarding.reminder)
        await callback.message.edit_text(
            f"Уровень: {USER_LEVEL_NAMES[level]}.\n\n"
            "Когда удобно напоминать о повторении?",
            reply_markup=onboarding_reminder_keyboard(),
        )
        await callback.answer()

    @router.callback_query(Onboarding.reminder, F.data.startswith("onboarding:reminder:"))
    async def onboarding_reminder(callback: CallbackQuery, state: FSMContext) -> None:
        reminder = callback.data.split(":", 2)[2]
        reminder_time = None if reminder == "off" else reminder
        data = await state.get_data()
        selected_language = data.get("language", "en")
        learning_goal = data.get("learning_goal", "general")
        learning_level = data.get("learning_level", "beginner")
        await repo.save_onboarding(
            callback.from_user.id,
            selected_language,
            learning_goal,
            learning_level,
            reminder_time,
        )
        await state.clear()
        reminder_text = reminder_time or "без напоминаний"
        await callback.message.edit_text(
            "Готово, словарь настроен ✅\n\n"
            f"Язык: {LANGUAGE_NAMES[selected_language]}\n"
            f"Цель: {GOAL_NAMES[learning_goal]}\n"
            f"Уровень: {USER_LEVEL_NAMES[learning_level]}\n"
            f"Напоминания: {reminder_text}\n\n"
            "Мини-инструкция:\n"
            "• ➕ Добавить — отправь слово и комментарий, я сделаю карточку.\n"
            "• 🎓 Учить — повторяй слова, когда подойдёт срок.\n"
            "• 📚 Словарь — смотри все сохранённые слова.\n"
            "• ⚙️ Настройки — измени язык, цель, уровень или время."
        )
        await callback.message.answer(
            "Попробуй начать с кнопки ➕ Добавить: введи первое слово, которое хочешь запомнить.",
            reply_markup=main_menu(),
        )
        await callback.answer()

    @router.message(Command("cancel"))
    @router.message(F.text == CANCEL_BUTTON)
    async def cancel(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer("Действие отменено.", reply_markup=main_menu())

    async def select_language(message: Message, state: FSMContext, code: str) -> None:
        await state.clear()
        await repo.set_language(message.from_user.id, code)
        await message.answer(
            f"Режим переключён: {LANGUAGE_NAMES[code]} ✅",
            reply_markup=main_menu(),
        )

    @router.message(F.text == ENGLISH_BUTTON)
    async def select_english(message: Message, state: FSMContext) -> None:
        await select_language(message, state, "en")

    @router.message(F.text == SPANISH_BUTTON)
    async def select_spanish(message: Message, state: FSMContext) -> None:
        await select_language(message, state, "es")

    async def begin_add(message: Message, state: FSMContext, initial_word: str = "") -> None:
        await state.clear()
        if initial_word:
            await state.update_data(word=initial_word.strip())
            await state.set_state(AddCard.comment)
            await message.answer(
                "Добавь свой комментарий или контекст. Отправь «-», если комментария нет:",
                reply_markup=cancel_menu(),
            )
        else:
            await state.set_state(AddCard.word)
            await message.answer("Напиши слово:", reply_markup=cancel_menu())

    @router.message(Command("addnew"))
    async def add_start(message: Message, command: CommandObject, state: FSMContext) -> None:
        await begin_add(message, state, command.args or "")

    @router.message(F.text == ADD_BUTTON)
    async def add_from_menu(message: Message, state: FSMContext) -> None:
        await begin_add(message, state)

    @router.message(AddCard.word, F.text)
    async def add_word(message: Message, state: FSMContext) -> None:
        await state.update_data(word=message.text.strip())
        await state.set_state(AddCard.comment)
        await message.answer(
            "Добавь свой комментарий или контекст. Отправь «-», если комментария нет:"
        )

    async def generate_and_add(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        comment = "" if message.text.strip() == "-" else message.text.strip()
        active_language = await language(message.from_user.id)
        waiting = await message.answer("Создаю карточку с помощью ИИ… ✨")
        try:
            generated = await generator.generate(data["word"], active_language, comment)
            created = await repo.add(
                message.from_user.id,
                generated.normalized_word,
                generated.translation,
                active_language,
                generated.example,
                generated.explanation,
                comment,
            )
        except Exception:
            logger.exception("Failed to generate a card")
            await waiting.edit_text(
                "Не удалось создать карточку. Проверь OPENAI_API_KEY или попробуй позже."
            )
            return
        await state.clear()
        if not created:
            await waiting.edit_text("Такое слово уже есть в выбранном языке.")
            await message.answer("Выбери следующее действие:", reply_markup=main_menu())
            return
        card = await repo.find_by_word(
            message.from_user.id, generated.normalized_word, active_language
        )
        await waiting.edit_text(
            full_card(card), parse_mode="HTML", reply_markup=pronunciation_keyboard(card.id)
        )
        await message.answer("Карточка добавлена ✅", reply_markup=main_menu())

    @router.message(AddCard.comment, F.text)
    async def add_comment(message: Message, state: FSMContext) -> None:
        await generate_and_add(message, state)

    async def send_list(message: Message) -> None:
        active_language = await language(message.from_user.id)
        grouped = await repo.list_grouped(message.from_user.id, active_language)
        cards = [card for values in grouped.values() for card in values]
        if not cards:
            await message.answer(
                f"В разделе {LANGUAGE_NAMES[active_language]} пока нет слов."
            )
            return
        lines = [f"<b>{LANGUAGE_NAMES[active_language]}</b> · {len(cards)} слов"]
        for card in cards[:50]:
            lines.append(
                f"• {escape(card.word)} — {escape(card.meaning)} "
                f"<i>({card.learning_level}/5 · {LEVEL_NAMES[card.learning_level]})</i>"
            )
        if len(cards) > 50:
            lines.append(f"…ещё {len(cards) - 50}")
        await message.answer("\n".join(lines), parse_mode="HTML")

    @router.message(Command("list"))
    async def list_cards(message: Message) -> None:
        await send_list(message)

    @router.message(F.text == LIST_BUTTON)
    async def list_from_menu(message: Message, state: FSMContext) -> None:
        await state.clear()
        await send_list(message)

    async def begin_edit(message: Message, state: FSMContext, value: str = "") -> None:
        await state.clear()
        await state.set_state(EditCard.search)
        if value:
            await edit_search_value(message, state, value)
        else:
            await message.answer("Какое слово изменить?", reply_markup=cancel_menu())

    @router.message(Command("edit"))
    async def edit_start(message: Message, command: CommandObject, state: FSMContext) -> None:
        await begin_edit(message, state, command.args or "")

    @router.message(F.text == EDIT_BUTTON)
    async def edit_from_menu(message: Message, state: FSMContext) -> None:
        await begin_edit(message, state)

    async def edit_search_value(message: Message, state: FSMContext, value: str) -> None:
        active_language = await language(message.from_user.id)
        card = await repo.find_by_word(message.from_user.id, value, active_language)
        if not card:
            await message.answer("Слово не найдено в выбранном языке. Попробуй ещё раз.")
            return
        await state.update_data(card_id=card.id, old_word=card.word, old_comment=card.comment)
        await state.set_state(EditCard.word)
        await message.answer("Введи новое слово или «-», чтобы оставить прежнее:")

    @router.message(EditCard.search, F.text)
    async def edit_search(message: Message, state: FSMContext) -> None:
        await edit_search_value(message, state, message.text)

    @router.message(EditCard.word, F.text)
    async def edit_word(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        word = data["old_word"] if message.text.strip() == "-" else message.text.strip()
        await state.update_data(word=word)
        await state.set_state(EditCard.comment)
        await message.answer("Введи новый комментарий или «-», чтобы оставить прежний:")

    @router.message(EditCard.comment, F.text)
    async def edit_comment(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        comment = data["old_comment"] if message.text.strip() == "-" else message.text.strip()
        active_language = await language(message.from_user.id)
        waiting = await message.answer("Обновляю карточку с помощью ИИ… ✨")
        try:
            generated = await generator.generate(data["word"], active_language, comment)
            updated = await repo.update(
                data["card_id"], message.from_user.id, generated.normalized_word,
                generated.translation, generated.example, generated.explanation, comment,
            )
        except Exception:
            logger.exception("Failed to regenerate a card")
            await waiting.edit_text("Не удалось обновить карточку. Попробуй позже.")
            return
        await state.clear()
        await waiting.edit_text(
            "Карточка обновлена ✅" if updated else "Не удалось обновить: такое слово уже есть."
        )
        await message.answer("Выбери следующее действие:", reply_markup=main_menu())

    async def begin_delete(message: Message, state: FSMContext, value: str = "") -> None:
        await state.clear()
        await state.set_state(DeleteCard.search)
        if value:
            await delete_search_value(message, state, value)
        else:
            await message.answer("Какое слово удалить?", reply_markup=cancel_menu())

    @router.message(Command("delete"))
    async def delete_start(message: Message, command: CommandObject, state: FSMContext) -> None:
        await begin_delete(message, state, command.args or "")

    @router.message(F.text == DELETE_BUTTON)
    async def delete_from_menu(message: Message, state: FSMContext) -> None:
        await begin_delete(message, state)

    async def delete_search_value(message: Message, state: FSMContext, value: str) -> None:
        active_language = await language(message.from_user.id)
        card = await repo.find_by_word(message.from_user.id, value, active_language)
        if not card:
            await message.answer("Слово не найдено в выбранном языке. Попробуй ещё раз.")
            return
        await state.set_state(DeleteCard.confirm)
        await message.answer(
            f"Удалить «{card.word} — {card.meaning}»?", reply_markup=delete_keyboard(card.id)
        )

    @router.message(DeleteCard.search, F.text)
    async def delete_search(message: Message, state: FSMContext) -> None:
        await delete_search_value(message, state, message.text)

    @router.callback_query(F.data.startswith("delete_confirm:"))
    async def delete_confirm(callback: CallbackQuery, state: FSMContext) -> None:
        deleted = await repo.delete(int(callback.data.split(":")[1]), callback.from_user.id)
        await state.clear()
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer(
            "Карточка удалена." if deleted else "Карточка уже не существует.",
            reply_markup=main_menu(),
        )
        await callback.answer()

    @router.callback_query(F.data == "delete_cancel")
    async def delete_cancel(callback: CallbackQuery, state: FSMContext) -> None:
        await state.clear()
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.answer("Удаление отменено.", reply_markup=main_menu())
        await callback.answer()

    async def show_next(message: Message, user_id: int) -> None:
        active_language = await language(user_id)
        cards = await repo.due(user_id, active_language, limit=1)
        if not cards:
            streak = await streak_line(user_id)
            await message.answer(
                f"На сегодня в разделе {LANGUAGE_NAMES[active_language]} всё 🎉\n\n"
                f"{streak}"
            )
            return
        card = cards[0]
        await message.answer(
            f"Вспомни значение:\n\n<b>{escape(card.word)}</b>",
            parse_mode="HTML", reply_markup=reveal_keyboard(card.id),
        )

    @router.message(Command("study"))
    async def study(message: Message) -> None:
        await show_next(message, message.from_user.id)

    @router.message(F.text == STUDY_BUTTON)
    async def study_from_menu(message: Message, state: FSMContext) -> None:
        await state.clear()
        await show_next(message, message.from_user.id)

    @router.callback_query(F.data.startswith("reveal:"))
    async def reveal(callback: CallbackQuery) -> None:
        card = await repo.get(int(callback.data.split(":")[1]), callback.from_user.id)
        if not card:
            await callback.answer("Карточка не найдена", show_alert=True)
            return
        await callback.message.edit_text(
            full_card(card) + "\n\n<b>Как вспомнилось?</b>",
            parse_mode="HTML", reply_markup=grade_keyboard(card.id),
        )
        await callback.answer()

    @router.callback_query(F.data.startswith("pronounce:"))
    async def pronounce(callback: CallbackQuery) -> None:
        card = await repo.get(int(callback.data.split(":")[1]), callback.from_user.id)
        if not card:
            await callback.answer("Карточка не найдена", show_alert=True)
            return
        await callback.answer("Готовлю произношение…")
        try:
            audio = await synthesize_word(card.word, card.language)
            await callback.message.answer_audio(
                BufferedInputFile(audio, filename=f"{card.language}-pronunciation.mp3"),
                title=card.word,
            )
        except Exception:
            logger.exception("Failed to synthesize pronunciation")
            await callback.message.answer("Не удалось загрузить произношение. Попробуй позже.")

    @router.callback_query(F.data.startswith("grade:"))
    async def grade(callback: CallbackQuery) -> None:
        _, raw_id, raw_quality = callback.data.split(":")
        card = await repo.get(int(raw_id), callback.from_user.id)
        if not card:
            await callback.answer("Карточка не найдена", show_alert=True)
            return
        result = schedule(card, int(raw_quality), datetime.now(timezone.utc))
        await repo.save_review(
            card.id, callback.from_user.id, result.repetitions,
            result.interval_days, result.ease_factor, result.due_at,
            result.learning_level,
        )
        await repo.record_study_day(callback.from_user.id, local_today())
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.answer("Оценка сохранена")
        await show_next(callback.message, callback.from_user.id)

    return router
