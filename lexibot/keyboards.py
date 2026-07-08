from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)


ADD_BUTTON = "➕ Добавить"
LIST_BUTTON = "📚 Словарь"
STUDY_BUTTON = "🎓 Учить"
EDIT_BUTTON = "✏️ Изменить"
DELETE_BUTTON = "🗑 Удалить"
CANCEL_BUTTON = "❌ Отмена"


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=ADD_BUTTON), KeyboardButton(text=STUDY_BUTTON)],
            [KeyboardButton(text=LIST_BUTTON)],
            [KeyboardButton(text=EDIT_BUTTON), KeyboardButton(text=DELETE_BUTTON)],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Выбери действие",
    )


def cancel_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=CANCEL_BUTTON)]],
        resize_keyboard=True,
        input_field_placeholder="Введи значение или отмени действие",
    )


def reveal_keyboard(card_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Показать ответ", callback_data=f"reveal:{card_id}")
    ]])


def grade_keyboard(card_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="😵 Не помню", callback_data=f"grade:{card_id}:0"),
            InlineKeyboardButton(text="😓 Трудно", callback_data=f"grade:{card_id}:3"),
        ],
        [
            InlineKeyboardButton(text="🙂 Помню", callback_data=f"grade:{card_id}:4"),
            InlineKeyboardButton(text="😎 Легко", callback_data=f"grade:{card_id}:5"),
        ],
    ])


def delete_keyboard(card_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete_confirm:{card_id}"),
        InlineKeyboardButton(text="Отмена", callback_data="delete_cancel"),
    ]])
