from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from config import CATEGORIES, STATUSES

BTN_NEW = "Оставить заявку"
BTN_MINE = "Мои заявки"
BTN_CANCEL = "Отмена"
BTN_CONTACT = "Отправить мой номер"


def main_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_NEW), KeyboardButton(text=BTN_MINE)],
        ],
        resize_keyboard=True,
    )


def cancel_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=BTN_CANCEL)]],
        resize_keyboard=True,
    )


def phone_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_CONTACT, request_contact=True)],
            [KeyboardButton(text=BTN_CANCEL)],
        ],
        resize_keyboard=True,
    )


def categories_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=title, callback_data=f"cat:{key}")]
        for key, title in CATEGORIES.items()
    ]
    rows.append([InlineKeyboardButton(text=BTN_CANCEL, callback_data="form:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Отправить", callback_data="form:send")],
            [
                InlineKeyboardButton(text="Заполнить заново", callback_data="form:restart"),
                InlineKeyboardButton(text=BTN_CANCEL, callback_data="form:cancel"),
            ],
        ]
    )


def user_apps_kb(apps: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for app in apps:
        status = STATUSES.get(app["status"], app["status"])
        category = CATEGORIES.get(app["category"], app["category"])
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"№{app['id']} · {category} · {status}",
                    callback_data=f"my:{app['id']}",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def admin_apps_kb(apps: list[dict]) -> InlineKeyboardMarkup:
    rows = []
    for app in apps:
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"№{app['id']} · {app['name']}",
                    callback_data=f"open:{app['id']}",
                )
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def status_kb(app_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="В работу", callback_data=f"st:{app_id}:in_progress"),
                InlineKeyboardButton(text="Выполнена", callback_data=f"st:{app_id}:done"),
            ],
            [InlineKeyboardButton(text="Отклонить", callback_data=f"st:{app_id}:rejected")],
        ]
    )
