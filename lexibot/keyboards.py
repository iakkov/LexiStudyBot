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
SETTINGS_BUTTON = "⚙️ Настройки"
CANCEL_BUTTON = "❌ Отмена"
ENGLISH_BUTTON = "🇬🇧 English"
SPANISH_BUTTON = "🇪🇸 Español"


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=ADD_BUTTON), KeyboardButton(text=STUDY_BUTTON)],
            [KeyboardButton(text=LIST_BUTTON)],
            [KeyboardButton(text=EDIT_BUTTON), KeyboardButton(text=DELETE_BUTTON)],
            [KeyboardButton(text=SETTINGS_BUTTON)],
            [KeyboardButton(text=ENGLISH_BUTTON), KeyboardButton(text=SPANISH_BUTTON)],
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


def reveal_keyboard(card_id: int, study_mode: str = "word_to_translation") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Показать ответ", callback_data=f"reveal:{card_id}:{study_mode}")],
        [InlineKeyboardButton(text="🔊 Произнести", callback_data=f"pronounce:{card_id}")],
    ])


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
        [InlineKeyboardButton(text="🔊 Произнести", callback_data=f"pronounce:{card_id}")],
    ])


def pronunciation_keyboard(card_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🔊 Произнести", callback_data=f"pronounce:{card_id}")
    ]])


def delete_keyboard(card_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🗑 Удалить", callback_data=f"delete_confirm:{card_id}"),
        InlineKeyboardButton(text="Отмена", callback_data="delete_cancel"),
    ]])


def onboarding_language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇬🇧 English", callback_data="onboarding:language:en")],
        [InlineKeyboardButton(text="🇪🇸 Español", callback_data="onboarding:language:es")],
    ])


def onboarding_goal_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💼 Работа и бизнес", callback_data="onboarding:goal:work")],
        [InlineKeyboardButton(text="✈️ Путешествия", callback_data="onboarding:goal:travel")],
        [InlineKeyboardButton(text="🎬 Фильмы и сериалы", callback_data="onboarding:goal:media")],
        [InlineKeyboardButton(text="🌱 Просто учу для себя", callback_data="onboarding:goal:general")],
    ])


def onboarding_level_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="A1–A2 · Начинаю", callback_data="onboarding:level:beginner")],
        [InlineKeyboardButton(text="B1–B2 · Уже говорю", callback_data="onboarding:level:intermediate")],
        [InlineKeyboardButton(text="C1+ · Продвинутый", callback_data="onboarding:level:advanced")],
    ])


def onboarding_reminder_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🌅 09:00", callback_data="onboarding:reminder:09:00"),
            InlineKeyboardButton(text="☀️ 13:00", callback_data="onboarding:reminder:13:00"),
        ],
        [
            InlineKeyboardButton(text="🌙 20:00", callback_data="onboarding:reminder:20:00"),
            InlineKeyboardButton(text="Без напоминаний", callback_data="onboarding:reminder:off"),
        ],
    ])


def settings_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌍 Изменить язык", callback_data="settings:edit:language")],
        [InlineKeyboardButton(text="🎯 Изменить цель", callback_data="settings:edit:goal")],
        [InlineKeyboardButton(text="📈 Изменить уровень", callback_data="settings:edit:level")],
        [InlineKeyboardButton(text="⏰ Изменить напоминание", callback_data="settings:edit:reminder")],
        [InlineKeyboardButton(text="✅ Готово", callback_data="settings:close")],
    ])


def settings_language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇬🇧 English", callback_data="settings:language:en")],
        [InlineKeyboardButton(text="🇪🇸 Español", callback_data="settings:language:es")],
        [InlineKeyboardButton(text="← Назад", callback_data="settings:back")],
    ])


def settings_goal_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💼 Работа и бизнес", callback_data="settings:goal:work")],
        [InlineKeyboardButton(text="✈️ Путешествия", callback_data="settings:goal:travel")],
        [InlineKeyboardButton(text="🎬 Фильмы и сериалы", callback_data="settings:goal:media")],
        [InlineKeyboardButton(text="🌱 Просто учу для себя", callback_data="settings:goal:general")],
        [InlineKeyboardButton(text="← Назад", callback_data="settings:back")],
    ])


def settings_level_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="A1–A2 · Начинаю", callback_data="settings:level:beginner")],
        [InlineKeyboardButton(text="B1–B2 · Уже говорю", callback_data="settings:level:intermediate")],
        [InlineKeyboardButton(text="C1+ · Продвинутый", callback_data="settings:level:advanced")],
        [InlineKeyboardButton(text="← Назад", callback_data="settings:back")],
    ])


def settings_reminder_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🌅 09:00", callback_data="settings:reminder:09:00"),
            InlineKeyboardButton(text="☀️ 13:00", callback_data="settings:reminder:13:00"),
        ],
        [
            InlineKeyboardButton(text="🌙 20:00", callback_data="settings:reminder:20:00"),
            InlineKeyboardButton(text="Выключить", callback_data="settings:reminder:off"),
        ],
        [InlineKeyboardButton(text="← Назад", callback_data="settings:back")],
    ])
