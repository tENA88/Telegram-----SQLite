import asyncio
import html
import logging
import re

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramForbiddenError
from aiogram.filters import Command, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, Message

import db
from config import ADMIN_IDS, BOT_TOKEN, CATEGORIES, STATUSES
from keyboards import (
    BTN_CANCEL,
    BTN_MINE,
    BTN_NEW,
    admin_apps_kb,
    cancel_menu,
    categories_kb,
    confirm_kb,
    main_menu,
    phone_menu,
    status_kb,
    user_apps_kb,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("bot")

router = Router()
PHONE_RE = re.compile(r"^[+\d][\d\s\-()]{5,20}$")


class Form(StatesGroup):
    name = State()
    phone = State()
    category = State()
    description = State()
    confirm = State()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def esc(value: object) -> str:
    return html.escape(str(value))


def application_text(app: dict, *, for_admin: bool = False) -> str:
    category = CATEGORIES.get(app["category"], app["category"])
    status = STATUSES.get(app["status"], app["status"])
    lines = [
        f"<b>Заявка №{app['id']}</b>",
        f"Статус: {esc(status)}",
        f"Имя: {esc(app['name'])}",
        f"Телефон: {esc(app['phone'])}",
        f"Тема: {esc(category)}",
    ]
    if for_admin:
        username = app.get("username")
        who = f"@{esc(username)}" if username else "без username"
        lines.insert(1, f"Клиент: {esc(app.get('tg_name') or app['name'])} ({who}), id <code>{app['user_id']}</code>")
    lines.append(f"Создана: {esc(db.format_dt(app['created_at']))}")
    lines.append("")
    lines.append(esc(app["description"]))
    return "\n".join(lines)


def preview_text(data: dict) -> str:
    category = CATEGORIES.get(data["category"], data["category"])
    return (
        "<b>Проверьте заявку</b>\n\n"
        f"Имя: {esc(data['name'])}\n"
        f"Телефон: {esc(data['phone'])}\n"
        f"Тема: {esc(category)}\n\n"
        f"{esc(data['description'])}"
    )


def normalize_phone(raw: str) -> str | None:
    compact = re.sub(r"[^\d+]", "", raw.strip())
    digits = re.sub(r"\D", "", compact)
    if len(digits) < 10 or len(digits) > 15:
        return None
    if not PHONE_RE.match(raw.strip()):
        return None
    return compact


async def show_main(message: Message, text: str) -> None:
    await message.answer(text, reply_markup=main_menu())


async def ask_name(message: Message, state: FSMContext) -> None:
    await state.set_state(Form.name)
    await message.answer(
        "Как к вам обращаться? Напишите имя.",
        reply_markup=cancel_menu(),
    )


async def notify_admins(bot: Bot, app: dict) -> None:
    text = "<b>Новая заявка</b>\n\n" + application_text(app, for_admin=True)
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text, reply_markup=status_kb(app["id"]))
        except TelegramForbiddenError:
            log.warning("Админ %s недоступен", admin_id)
        except Exception:
            log.exception("Не удалось отправить заявку админу %s", admin_id)


async def notify_user(bot: Bot, app: dict) -> None:
    status = STATUSES.get(app["status"], app["status"])
    text = (
        f"Статус заявки №{app['id']} изменён: <b>{esc(status)}</b>."
    )
    try:
        await bot.send_message(app["user_id"], text)
    except TelegramForbiddenError:
        log.info("Пользователь %s заблокировал бота", app["user_id"])


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    user = message.from_user
    await db.upsert_user(user.id, user.username, user.full_name)
    await show_main(
        message,
        "Здравствуйте. Здесь можно оставить заявку и следить за её статусом.\n"
        "Выберите действие на клавиатуре.",
    )


@router.message(Command("cancel"), StateFilter("*"))
@router.message(F.text == BTN_CANCEL, StateFilter("*"))
async def cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await show_main(message, "Заполнение отменено.")


@router.message(Command("admin"))
@router.message(F.text == "Новые заявки")
async def cmd_admin(message: Message) -> None:
    if not is_admin(message.from_user.id):
        await message.answer("Команда доступна только администратору.")
        return
    apps = await db.list_by_status("new")
    if not apps:
        await message.answer("Новых заявок нет.")
        return
    await message.answer("Новые заявки:", reply_markup=admin_apps_kb(apps))


@router.message(F.text == BTN_NEW)
async def start_form(message: Message, state: FSMContext) -> None:
    user = message.from_user
    await db.upsert_user(user.id, user.username, user.full_name)
    await state.clear()
    await ask_name(message, state)


@router.message(F.text == BTN_MINE)
async def my_apps(message: Message, state: FSMContext) -> None:
    await state.clear()
    apps = await db.list_user_applications(message.from_user.id)
    if not apps:
        await show_main(message, "У вас пока нет заявок.")
        return
    await message.answer("Ваши последние заявки:", reply_markup=user_apps_kb(apps))


@router.message(Form.name, F.text)
async def got_name(message: Message, state: FSMContext) -> None:
    name = message.text.strip()
    if len(name) < 2 or len(name) > 80:
        await message.answer("Имя должно быть от 2 до 80 символов.")
        return
    await state.update_data(name=name)
    await state.set_state(Form.phone)
    await message.answer(
        "Укажите телефон: отправьте контакт кнопкой или напишите номер.",
        reply_markup=phone_menu(),
    )


@router.message(Form.phone, F.contact)
async def got_contact(message: Message, state: FSMContext) -> None:
    contact = message.contact
    if contact.user_id and contact.user_id != message.from_user.id:
        await message.answer("Нужен ваш собственный контакт, не чужой.")
        return
    phone = normalize_phone(contact.phone_number) or contact.phone_number
    await state.update_data(phone=phone)
    await state.set_state(Form.category)
    await message.answer("Выберите тему заявки.", reply_markup=cancel_menu())
    await message.answer("Тема:", reply_markup=categories_kb())


@router.message(Form.phone, F.text)
async def got_phone(message: Message, state: FSMContext) -> None:
    phone = normalize_phone(message.text)
    if phone is None:
        await message.answer("Не похоже на номер. Пример: +79991234567")
        return
    await state.update_data(phone=phone)
    await state.set_state(Form.category)
    await message.answer("Выберите тему заявки.", reply_markup=cancel_menu())
    await message.answer("Тема:", reply_markup=categories_kb())


@router.callback_query(Form.category, F.data.startswith("cat:"))
async def got_category(query: CallbackQuery, state: FSMContext) -> None:
    key = query.data.split(":", 1)[1]
    if key not in CATEGORIES:
        await query.answer("Неизвестная тема")
        return
    await state.update_data(category=key)
    await state.set_state(Form.description)
    await query.answer()
    await query.message.edit_text(f"Тема: {CATEGORIES[key]}")
    await query.message.answer(
        "Опишите задачу одним сообщением.",
        reply_markup=cancel_menu(),
    )


@router.message(Form.category)
async def category_need_button(message: Message) -> None:
    await message.answer("Выберите тему кнопкой под сообщением.", reply_markup=categories_kb())


@router.message(Form.confirm)
async def confirm_need_button(message: Message) -> None:
    await message.answer("Отправьте заявку кнопкой под сообщением или отмените заполнение.")


@router.message(Form.description, F.text)
async def got_description(message: Message, state: FSMContext) -> None:
    text = message.text.strip()
    if len(text) < 5 or len(text) > 2000:
        await message.answer("Описание должно быть от 5 до 2000 символов.")
        return
    await state.update_data(description=text)
    await state.set_state(Form.confirm)
    data = await state.get_data()
    await message.answer(preview_text(data), reply_markup=confirm_kb())


@router.callback_query(F.data == "form:cancel")
async def form_cancel(query: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await query.answer()
    await query.message.answer("Заполнение отменено.", reply_markup=main_menu())


@router.callback_query(F.data == "form:restart")
async def form_restart(query: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await query.answer()
    await ask_name(query.message, state)


@router.callback_query(Form.confirm, F.data == "form:send")
async def form_send(query: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()
    required = ("name", "phone", "category", "description")
    if any(key not in data for key in required):
        await state.clear()
        await query.answer("Данные устарели, начните заново", show_alert=True)
        return
    user = query.from_user
    await db.upsert_user(user.id, user.username, user.full_name)
    app_id = await db.create_application(
        user.id,
        data["name"],
        data["phone"],
        data["category"],
        data["description"],
    )
    await state.clear()
    app = await db.get_application(app_id)
    await query.answer("Заявка отправлена")
    await query.message.edit_reply_markup(reply_markup=None)
    await query.message.answer(
        f"Заявка №{app_id} принята. Статус: {STATUSES['new']}.",
        reply_markup=main_menu(),
    )
    if app:
        await notify_admins(bot, app)


@router.callback_query(F.data.startswith("my:"))
async def open_mine(query: CallbackQuery) -> None:
    app_id = int(query.data.split(":", 1)[1])
    app = await db.get_application(app_id)
    if app is None or app["user_id"] != query.from_user.id:
        await query.answer("Заявка не найдена", show_alert=True)
        return
    await query.answer()
    await query.message.answer(application_text(app))


@router.callback_query(F.data.startswith("open:"))
async def open_admin(query: CallbackQuery) -> None:
    if not is_admin(query.from_user.id):
        await query.answer("Недостаточно прав", show_alert=True)
        return
    app_id = int(query.data.split(":", 1)[1])
    app = await db.get_application(app_id)
    if app is None:
        await query.answer("Заявка не найдена", show_alert=True)
        return
    await query.answer()
    markup = status_kb(app_id) if app["status"] == "new" or app["status"] == "in_progress" else None
    await query.message.answer(application_text(app, for_admin=True), reply_markup=markup)


@router.callback_query(F.data.startswith("st:"))
async def change_status(query: CallbackQuery, bot: Bot) -> None:
    if not is_admin(query.from_user.id):
        await query.answer("Недостаточно прав", show_alert=True)
        return
    _, app_id_raw, status = query.data.split(":", 2)
    if status not in STATUSES:
        await query.answer("Неизвестный статус")
        return
    app_id = int(app_id_raw)
    current = await db.get_application(app_id)
    if current is None:
        await query.answer("Заявка не найдена", show_alert=True)
        return
    if current["status"] == status:
        await query.answer("Этот статус уже стоит")
        return
    if current["status"] in {"done", "rejected"}:
        await query.answer("Заявка уже закрыта", show_alert=True)
        return
    app = await db.set_status(app_id, status)
    await query.answer("Статус обновлён")
    closed = status in {"done", "rejected"}
    await query.message.edit_text(
        application_text(app, for_admin=True),
        reply_markup=None if closed else status_kb(app_id),
    )
    await notify_user(bot, app)


async def main() -> None:
    if not BOT_TOKEN:
        raise SystemExit("Укажите BOT_TOKEN в файле .env (см. .env.example)")
    if not ADMIN_IDS:
        log.warning("ADMIN_IDS пуст: новые заявки некому присылать, /admin недоступен")
    await db.init()
    bot = Bot(BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    log.info("Бот запущен")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
