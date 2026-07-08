from datetime import datetime, timezone
from html import escape

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from lexibot.db import CardRepository
from lexibot.keyboards import (
    ADD_BUTTON,
    CANCEL_BUTTON,
    DELETE_BUTTON,
    EDIT_BUTTON,
    LIST_BUTTON,
    STUDY_BUTTON,
    cancel_menu,
    delete_keyboard,
    grade_keyboard,
    main_menu,
    reveal_keyboard,
)
from lexibot.scheduler import schedule


class AddCard(StatesGroup):
    word = State()
    meaning = State()
    group = State()


class EditCard(StatesGroup):
    search = State()
    word = State()
    meaning = State()
    group = State()


class DeleteCard(StatesGroup):
    search = State()
    confirm = State()


LEVEL_NAMES = {
    1: "новое",
    2: "плохо выучено",
    3: "хорошо выучено",
    4: "отлично · осталось 1 повторение",
    5: "выучено",
}


def create_router(repo: CardRepository) -> Router:
    router = Router()

    @router.message(CommandStart())
    @router.message(Command("help"))
    async def help_command(message: Message) -> None:
        await message.answer(
            "Привет! Я храню английские слова и помогаю повторять их карточками.\n\n"
            "/addnew — добавить слово\n"
            "/addnew word | перевод — быстро добавить\n"
            "/list — показать словарь\n"
            "/study — начать повторение\n"
            "/edit — изменить карточку\n"
            "/delete — удалить карточку\n"
            "/cancel — отменить ввод",
            reply_markup=main_menu(),
        )

    @router.message(Command("cancel"))
    @router.message(F.text == CANCEL_BUTTON)
    async def cancel(message: Message, state: FSMContext) -> None:
        await state.clear()
        await message.answer("Действие отменено.", reply_markup=main_menu())

    @router.message(Command("addnew"))
    async def add_start(message: Message, command: CommandObject, state: FSMContext) -> None:
        if command.args and "|" in command.args:
            word, meaning = (part.strip() for part in command.args.split("|", 1))
            if word and meaning:
                created = await repo.add(message.from_user.id, word, meaning, "Без группы")
                await message.answer(
                    "Слово добавлено ✅" if created else "Такое слово уже есть.",
                    reply_markup=main_menu(),
                )
                return
        await state.set_state(AddCard.word)
        await message.answer("Напиши английское слово:", reply_markup=cancel_menu())

    @router.message(F.text == ADD_BUTTON)
    async def add_from_menu(message: Message, state: FSMContext) -> None:
        await state.clear()
        await state.set_state(AddCard.word)
        await message.answer("Напиши английское слово:", reply_markup=cancel_menu())

    @router.message(AddCard.word, F.text)
    async def add_word(message: Message, state: FSMContext) -> None:
        await state.update_data(word=message.text.strip())
        await state.set_state(AddCard.meaning)
        await message.answer("Теперь напиши перевод или значение:")

    @router.message(AddCard.meaning, F.text)
    async def add_meaning(message: Message, state: FSMContext) -> None:
        await state.update_data(meaning=message.text.strip())
        await state.set_state(AddCard.group)
        await message.answer("Укажи группу, например «Путешествия». Отправь «-», чтобы пропустить:")

    @router.message(AddCard.group, F.text)
    async def add_group(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        group = "Без группы" if message.text.strip() == "-" else message.text.strip()
        created = await repo.add(message.from_user.id, data["word"], data["meaning"], group)
        await state.clear()
        await message.answer(
            "Слово добавлено ✅" if created else "Такое слово уже есть.",
            reply_markup=main_menu(),
        )

    @router.message(Command("list"))
    async def list_cards(message: Message) -> None:
        grouped = await repo.list_grouped(message.from_user.id)
        if not grouped:
            await message.answer("Словарь пока пуст. Добавь первое слово через /addnew.")
            return
        chunks = []
        for group, cards in grouped.items():
            lines = [f"<b>{escape(group)}</b> · {len(cards)}"]
            for card in cards[:20]:
                status = LEVEL_NAMES[card.learning_level]
                lines.append(
                    f"• {escape(card.word)} — {escape(card.meaning)} "
                    f"<i>({card.learning_level}/5 · {status})</i>"
                )
            if len(cards) > 20:
                lines.append(f"…ещё {len(cards) - 20}")
            chunks.append("\n".join(lines))
        await message.answer("\n\n".join(chunks), parse_mode="HTML")

    @router.message(F.text == LIST_BUTTON)
    async def list_from_menu(message: Message, state: FSMContext) -> None:
        await state.clear()
        await list_cards(message)

    @router.message(Command("edit"))
    async def edit_start(message: Message, command: CommandObject, state: FSMContext) -> None:
        await state.clear()
        if command.args:
            await state.set_state(EditCard.search)
            await edit_search_value(message, state, command.args)
            return
        await state.set_state(EditCard.search)
        await message.answer("Какое английское слово изменить?", reply_markup=cancel_menu())

    @router.message(F.text == EDIT_BUTTON)
    async def edit_from_menu(message: Message, state: FSMContext) -> None:
        await state.clear()
        await state.set_state(EditCard.search)
        await message.answer("Какое английское слово изменить?", reply_markup=cancel_menu())

    async def edit_search_value(message: Message, state: FSMContext, value: str) -> None:
        card = await repo.find_by_word(message.from_user.id, value)
        if not card:
            await message.answer("Слово не найдено. Попробуй ещё раз или отправь /cancel.")
            return
        await state.update_data(card_id=card.id, old_word=card.word)
        await state.set_state(EditCard.word)
        await message.answer(
            f"Новое написание для «{card.word}»? Отправь «-», чтобы оставить прежнее."
        )

    @router.message(EditCard.search, F.text)
    async def edit_search(message: Message, state: FSMContext) -> None:
        await edit_search_value(message, state, message.text)

    @router.message(EditCard.word, F.text)
    async def edit_word(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        word = data["old_word"] if message.text.strip() == "-" else message.text.strip()
        await state.update_data(word=word)
        await state.set_state(EditCard.meaning)
        await message.answer("Новый перевод? «-» — оставить прежний.")

    @router.message(EditCard.meaning, F.text)
    async def edit_meaning(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        card = await repo.get(data["card_id"], message.from_user.id)
        if not card:
            await state.clear()
            await message.answer("Карточка уже не существует.")
            return
        meaning = card.meaning if message.text.strip() == "-" else message.text.strip()
        await state.update_data(meaning=meaning, old_group=card.group_name)
        await state.set_state(EditCard.group)
        await message.answer("Новая группа? «-» — оставить прежнюю.")

    @router.message(EditCard.group, F.text)
    async def edit_group(message: Message, state: FSMContext) -> None:
        data = await state.get_data()
        group = data["old_group"] if message.text.strip() == "-" else message.text.strip()
        updated = await repo.update(
            data["card_id"], message.from_user.id, data["word"], data["meaning"], group
        )
        await state.clear()
        await message.answer(
            "Карточка обновлена ✅" if updated else "Не удалось обновить: такое слово уже есть.",
            reply_markup=main_menu(),
        )

    @router.message(Command("delete"))
    async def delete_start(message: Message, command: CommandObject, state: FSMContext) -> None:
        await state.clear()
        await state.set_state(DeleteCard.search)
        if command.args:
            await delete_search_value(message, state, command.args)
        else:
            await message.answer("Какое английское слово удалить?", reply_markup=cancel_menu())

    @router.message(F.text == DELETE_BUTTON)
    async def delete_from_menu(message: Message, state: FSMContext) -> None:
        await state.clear()
        await state.set_state(DeleteCard.search)
        await message.answer("Какое английское слово удалить?", reply_markup=cancel_menu())

    async def delete_search_value(message: Message, state: FSMContext, value: str) -> None:
        card = await repo.find_by_word(message.from_user.id, value)
        if not card:
            await message.answer("Слово не найдено. Попробуй ещё раз или отправь /cancel.")
            return
        await state.update_data(card_id=card.id)
        await state.set_state(DeleteCard.confirm)
        await message.answer(
            f"Удалить «{card.word} — {card.meaning}»?",
            reply_markup=delete_keyboard(card.id),
        )

    @router.message(DeleteCard.search, F.text)
    async def delete_search(message: Message, state: FSMContext) -> None:
        await delete_search_value(message, state, message.text)

    @router.callback_query(F.data.startswith("delete_confirm:"))
    async def delete_confirm(callback: CallbackQuery, state: FSMContext) -> None:
        card_id = int(callback.data.split(":")[1])
        deleted = await repo.delete(card_id, callback.from_user.id)
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
        cards = await repo.due(user_id, limit=1)
        if not cards:
            await message.answer("На сегодня всё 🎉 Следующие карточки появятся позже.")
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
        card_id = int(callback.data.split(":")[1])
        card = await repo.get(card_id, callback.from_user.id)
        if not card:
            await callback.answer("Карточка не найдена", show_alert=True)
            return
        await callback.message.edit_text(
            f"<b>{escape(card.word)}</b>\n\n{escape(card.meaning)}\n\nКак вспомнилось?",
            parse_mode="HTML", reply_markup=grade_keyboard(card.id),
        )
        await callback.answer()

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
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.answer("Оценка сохранена")
        await show_next(callback.message, callback.from_user.id)

    return router
