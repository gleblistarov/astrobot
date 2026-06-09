import asyncio
import logging
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, PreCheckoutQueryHandler, filters, ContextTypes,
)

from config import BOT_TOKEN, FREE_READINGS, CREDIT_PACKS, READING_COSTS
from database import (
    init_db, get_or_create_user, get_user,
    use_free_reading, deduct_credits, add_credits,
    update_birth_data, save_reading, save_payment,
)
from ai_service import (
    generate_tarot_reading, generate_fortune,
    generate_natal_chart, generate_forecast,
)
from tarot_data import get_random_cards, format_cards

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Keyboards ────────────────────────────────────────────────────────────────

def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🃏 Расклад Таро",      callback_data="tarot"),
            InlineKeyboardButton("🔮 Гадание",           callback_data="fortune"),
        ],
        [
            InlineKeyboardButton("⭐ Натальная карта",   callback_data="natal"),
            InlineKeyboardButton("🌙 Прогноз",           callback_data="forecast"),
        ],
        [
            InlineKeyboardButton("💰 Мой баланс",        callback_data="balance"),
            InlineKeyboardButton("💳 Пополнить",         callback_data="buy"),
        ],
    ])

def back_to_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("◀️ В меню", callback_data="menu")]])

# ── Helpers ──────────────────────────────────────────────────────────────────

async def charge(user_id: int, cost_key: str) -> tuple[bool, str]:
    """
    Попытка списать кредит (бесплатный или платный).
    Возвращает (успех, сообщение_для_пользователя).
    """
    user = await get_user(user_id)
    cost = READING_COSTS.get(cost_key, 1)
    free_used = user["free_readings_used"]

    if free_used < FREE_READINGS:
        await use_free_reading(user_id)
        left = FREE_READINGS - free_used - 1
        suffix = f"{'Ещё' if left else 'Бесплатных раскладов'} {left} шт." if left else "Бесплатные расклады исчерпаны."
        return True, f"🎁 _Бесплатный расклад. {suffix}_"

    if user["credits"] >= cost:
        await deduct_credits(user_id, cost)
        return True, f"💎 _Списано {cost} кр. Остаток: {user['credits'] - cost}_"

    return False, "no_credits"


async def send_or_edit(update: Update, text: str, keyboard=None, parse_mode="Markdown"):
    """Редактировать существующее сообщение или отправить новое."""
    kwargs = {"text": text, "parse_mode": parse_mode}
    if keyboard:
        kwargs["reply_markup"] = keyboard
    if update.callback_query:
        try:
            await update.callback_query.edit_message_text(**kwargs)
            return update.callback_query.message
        except Exception:
            pass
    msg = await update.effective_chat.send_message(**kwargs)
    return msg


async def no_credits_prompt(update: Update):
    text = (
        "💎 *Кредиты закончились*\n\n"
        "Пополните баланс, чтобы продолжить получать предсказания."
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💳 Пополнить баланс", callback_data="buy")],
        [InlineKeyboardButton("◀️ В меню",           callback_data="menu")],
    ])
    await send_or_edit(update, text, kb)


async def split_and_send(update: Update, text: str, keyboard=None):
    """Отправить длинный текст, разбив на части по 4000 символов."""
    chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
    msg = None
    for i, chunk in enumerate(chunks):
        kb = keyboard if i == len(chunks) - 1 else None
        if i == 0:
            msg = await send_or_edit(update, chunk, kb)
        else:
            msg = await update.effective_chat.send_message(
                chunk, parse_mode="Markdown", reply_markup=kb
            )
    return msg

# ── /start ───────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    await get_or_create_user(u.id, u.username, u.first_name)
    await update.message.reply_text(
        f"✨ *Добро пожаловать, {u.first_name}!*\n\n"
        f"Я — *Астра*, ваш личный астролог и таролог 🌟\n\n"
        f"Карты, звёзды и мистические практики помогут заглянуть за горизонт.\n"
        f"Вас ждут *{FREE_READINGS} бесплатных расклада* для знакомства.\n\n"
        f"Что хотите узнать?",
        parse_mode="Markdown",
        reply_markup=main_menu(),
    )

# ── Menu ─────────────────────────────────────────────────────────────────────

async def show_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()  # сброс незавершённых диалогов
    text = "✨ *Главное меню*\n\nЧто вас интересует сегодня?"
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(
            text, parse_mode="Markdown", reply_markup=main_menu()
        )
    else:
        await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_menu())

# ── Balance ──────────────────────────────────────────────────────────────────

async def balance_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    u = await get_user(update.effective_user.id)
    free_left = max(0, FREE_READINGS - u["free_readings_used"])
    await update.callback_query.edit_message_text(
        f"💰 *Ваш баланс*\n\n"
        f"🎁 Бесплатных раскладов: *{free_left}*\n"
        f"💎 Платных кредитов: *{u['credits']}*\n\n"
        f"_1 кредит — расклад Таро / гадание / прогноз на день_\n"
        f"_Натальная карта — 2 кредита_",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💳 Пополнить",  callback_data="buy")],
            [InlineKeyboardButton("◀️ В меню",     callback_data="menu")],
        ]),
    )

# ── Buy ──────────────────────────────────────────────────────────────────────

async def buy_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    rows = [
        [InlineKeyboardButton(
            f"💎 {p['credits']} кредитов — {p['stars']} ⭐ Stars",
            callback_data=f"pay_{pid}",
        )]
        for pid, p in CREDIT_PACKS.items()
    ]
    rows.append([InlineKeyboardButton("◀️ В меню", callback_data="menu")])
    await update.callback_query.edit_message_text(
        "💳 *Пополнение баланса*\n\n"
        "Оплата через встроенные *Telegram Stars* — мгновенно и безопасно.\n\n"
        "Выберите пакет:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(rows),
    )


async def pay_pack_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    pid = update.callback_query.data.replace("pay_", "")
    pack = CREDIT_PACKS.get(pid)
    if not pack:
        return

    await context.bot.send_invoice(
        chat_id=update.effective_user.id,
        title=f"💎 {pack['credits']} кредитов — Астробот",
        description=(
            f"Получите {pack['credits']} кредитов для раскладов Таро, "
            f"гаданий, прогнозов и натальных карт."
        ),
        payload=f"{pid}:{update.effective_user.id}",
        currency="XTR",
        prices=[LabeledPrice(label=f"{pack['credits']} кредитов", amount=pack["stars"])],
        provider_token="",
    )


async def precheckout_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.pre_checkout_query.answer(ok=True)


async def payment_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    payment = update.message.successful_payment
    pid = payment.invoice_payload.split(":")[0]
    pack = CREDIT_PACKS.get(pid)
    if pack:
        await add_credits(update.effective_user.id, pack["credits"])
        await save_payment(
            update.effective_user.id,
            payment.telegram_payment_charge_id,
            pack["stars"],
            pack["credits"],
        )
    await update.message.reply_text(
        f"✅ *Оплата прошла!*\n\n"
        f"💎 Зачислено *{pack['credits']} кредитов*.\n"
        f"Звёзды ждут вас! ✨",
        parse_mode="Markdown",
        reply_markup=main_menu(),
    )

# ── ТАРО ─────────────────────────────────────────────────────────────────────

async def tarot_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "🃏 *Расклад Таро*\n\nВыберите тип расклада:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("3 карты — Прошлое/Настоящее/Будущее (1 кр.)", callback_data="spread_three_cards")],
            [InlineKeyboardButton("5 карт — Развёрнутый анализ (2 кр.)",         callback_data="spread_five_cards")],
            [InlineKeyboardButton("Кельтский крест — 10 карт (3 кр.)",           callback_data="spread_celtic")],
            [InlineKeyboardButton("◀️ В меню",                                    callback_data="menu")],
        ]),
    )


async def spread_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    spread = update.callback_query.data.replace("spread_", "")
    context.user_data["tarot_spread"] = spread
    context.user_data["waiting_for"] = "tarot_question"

    spread_labels = {
        "three_cards": "3 карты",
        "five_cards":  "5 карт",
        "celtic":      "Кельтский крест",
    }
    await update.callback_query.edit_message_text(
        f"✨ *{spread_labels.get(spread, 'Расклад')}*\n\n"
        f"Сосредоточьтесь на своём вопросе...\n"
        f"Напишите его или нажмите «Пропустить» для общего расклада.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⏭ Пропустить вопрос", callback_data="tarot_skip")],
            [InlineKeyboardButton("◀️ В меню",            callback_data="menu")],
        ]),
    )


async def _do_tarot(update: Update, context: ContextTypes.DEFAULT_TYPE, question: str | None):
    user_id = update.effective_user.id
    spread = context.user_data.pop("tarot_spread", "three_cards")
    context.user_data.pop("waiting_for", None)
    cost_key = f"tarot_{spread}"

    ok, note = await charge(user_id, cost_key)
    if not ok:
        return await no_credits_prompt(update)

    sizes = {"three_cards": 3, "five_cards": 5, "celtic": 10}
    cards = get_random_cards(sizes.get(spread, 3))

    await send_or_edit(update, "🔮 _Карты открываются... подождите._", parse_mode="Markdown")

    reading = await generate_tarot_reading(cards, question, spread)
    await save_reading(user_id, f"tarot_{spread}", question or "", reading, READING_COSTS.get(cost_key, 1))

    spread_names = {"three_cards": "3 карты", "five_cards": "5 карт", "celtic": "Кельтский крест"}
    header = (
        f"🃏 *Расклад «{spread_names.get(spread, '')}»*\n\n"
        f"{format_cards(cards)}\n\n"
        f"{'—' * 20}\n\n"
        f"{reading}\n\n{note}"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🃏 Новый расклад", callback_data="tarot"),
         InlineKeyboardButton("◀️ В меню",        callback_data="menu")],
    ])
    await split_and_send(update, header, kb)


async def tarot_skip_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await _do_tarot(update, context, None)

# ── ГАДАНИЕ ──────────────────────────────────────────────────────────────────

FORTUNE_METHODS = {
    "runes":       "🎴 Рунное гадание",
    "coffee":      "☕ На кофейной гуще",
    "crystal":     "🔮 Хрустальный шар",
    "numerology":  "🔢 Нумерология",
    "clairvoyance":"🌟 Ясновидение",
}


async def fortune_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    rows = [[InlineKeyboardButton(label, callback_data=f"fmethod_{key}")]
            for key, label in FORTUNE_METHODS.items()]
    rows.append([InlineKeyboardButton("◀️ В меню", callback_data="menu")])
    await update.callback_query.edit_message_text(
        "🔮 *Гадание*\n\nВыберите метод:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(rows),
    )


async def fmethod_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    method_key = update.callback_query.data.replace("fmethod_", "")
    method_name = FORTUNE_METHODS.get(method_key, "Гадание")
    context.user_data["fortune_method"] = method_name
    context.user_data["waiting_for"] = "fortune_question"
    await update.callback_query.edit_message_text(
        f"✨ *{method_name}*\n\n"
        f"Задайте вопрос или нажмите «Пропустить» для общего предсказания.",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⏭ Пропустить", callback_data="fortune_skip")],
            [InlineKeyboardButton("◀️ В меню",     callback_data="menu")],
        ]),
    )


async def _do_fortune(update: Update, context: ContextTypes.DEFAULT_TYPE, question: str | None):
    user_id = update.effective_user.id
    method = context.user_data.pop("fortune_method", "Ясновидение")
    context.user_data.pop("waiting_for", None)

    ok, note = await charge(user_id, "fortune")
    if not ok:
        return await no_credits_prompt(update)

    await send_or_edit(update, "🔮 _Мистические силы открывают завесу..._", parse_mode="Markdown")

    reading = await generate_fortune(method, question)
    await save_reading(user_id, "fortune", question or "", reading, READING_COSTS["fortune"])

    text = f"🔮 *{method}*\n\n{reading}\n\n{note}"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔮 Новое гадание", callback_data="fortune"),
         InlineKeyboardButton("◀️ В меню",        callback_data="menu")],
    ])
    await split_and_send(update, text, kb)


async def fortune_skip_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await _do_fortune(update, context, None)

# ── НАТАЛЬНАЯ КАРТА ──────────────────────────────────────────────────────────

async def natal_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    u = await get_user(update.effective_user.id)

    if u.get("birth_date") and u.get("birth_time") and u.get("birth_place"):
        await update.callback_query.edit_message_text(
            f"⭐ *Натальная карта*\n\n"
            f"Сохранённые данные:\n"
            f"📅 {u['birth_date']}  🕐 {u['birth_time']}  📍 {u['birth_place']}\n\n"
            f"Использовать их?",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Да, использовать",  callback_data="natal_saved")],
                [InlineKeyboardButton("✏️ Ввести новые",      callback_data="natal_new")],
                [InlineKeyboardButton("◀️ В меню",            callback_data="menu")],
            ]),
        )
    else:
        await _ask_birth_date(update, context)


async def natal_saved_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    u = await get_user(update.effective_user.id)
    context.user_data["birth_date"]  = u["birth_date"]
    context.user_data["birth_time"]  = u["birth_time"]
    context.user_data["birth_place"] = u["birth_place"]
    await _do_natal(update, context)


async def natal_new_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await _ask_birth_date(update, context)


async def _ask_birth_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["waiting_for"] = "natal_date"
    await send_or_edit(
        update,
        "⭐ *Натальная карта*\n\n📅 Введите дату рождения в формате *ДД.ММ.ГГГГ*\n_Пример: 15.03.1990_",
        back_to_menu(),
    )


async def _do_natal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    bd = context.user_data.get("birth_date")
    bt = context.user_data.get("birth_time")
    bp = context.user_data.get("birth_place")

    ok, note = await charge(user_id, "natal")
    if not ok:
        return await no_credits_prompt(update)

    await update_birth_data(user_id, bd, bt, bp)

    await send_or_edit(update, "⭐ _Звёзды выстраиваются... составляю вашу карту._", parse_mode="Markdown")

    name = update.effective_user.first_name or "Клиент"
    reading = await generate_natal_chart(bd, bt, bp, name)
    await save_reading(user_id, "natal", f"{bd} {bt} {bp}", reading, READING_COSTS["natal"])

    text = f"⭐ *Натальная карта*\n\n{reading}\n\n{note}"
    await split_and_send(update, text, main_menu())

# ── ПРОГНОЗ ──────────────────────────────────────────────────────────────────

async def forecast_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "🌙 *Астрологический прогноз*\n\nВыберите период:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("☀️ На сегодня (1 кр.)", callback_data="fperiod_day")],
            [InlineKeyboardButton("🌙 На неделю  (2 кр.)", callback_data="fperiod_week")],
            [InlineKeyboardButton("✨ На месяц   (3 кр.)", callback_data="fperiod_month")],
            [InlineKeyboardButton("◀️ В меню",             callback_data="menu")],
        ]),
    )


async def fperiod_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    period = update.callback_query.data.replace("fperiod_", "")
    context.user_data["forecast_period"] = period

    u = await get_user(update.effective_user.id)
    if u.get("birth_date"):
        return await _do_forecast(update, context)

    # Нет данных о рождении — спросим знак
    signs = [
        "♈ Овен", "♉ Телец", "♊ Близнецы", "♋ Рак",
        "♌ Лев",  "♍ Дева",  "♎ Весы",      "♏ Скорпион",
        "♐ Стрелец", "♑ Козерог", "♒ Водолей", "♓ Рыбы",
    ]
    rows = [
        [InlineKeyboardButton(signs[i], callback_data=f"sign_{signs[i]}"),
         InlineKeyboardButton(signs[i+1], callback_data=f"sign_{signs[i+1]}")]
        for i in range(0, len(signs), 2)
    ]
    rows.append([InlineKeyboardButton("◀️ В меню", callback_data="menu")])
    await update.callback_query.edit_message_text(
        "🌟 Выберите ваш знак зодиака:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(rows),
    )


async def sign_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    context.user_data["zodiac_sign"] = update.callback_query.data.replace("sign_", "")
    await _do_forecast(update, context)


async def _do_forecast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    period = context.user_data.pop("forecast_period", "day")
    cost_key = f"forecast_{period}"

    ok, note = await charge(user_id, cost_key)
    if not ok:
        return await no_credits_prompt(update)

    u = await get_user(user_id)
    user_ctx = (
        f"Дата рождения: {u['birth_date']}, место: {u.get('birth_place', '')}"
        if u.get("birth_date")
        else f"Знак зодиака: {context.user_data.pop('zodiac_sign', '')}"
    )

    period_labels = {"day": "на сегодня", "week": "на неделю", "month": "на месяц"}
    label = period_labels.get(period, "")

    await send_or_edit(update, f"🌙 _Составляю прогноз {label}..._", parse_mode="Markdown")

    reading = await generate_forecast(period, user_ctx)
    await save_reading(user_id, f"forecast_{period}", "", reading, READING_COSTS.get(cost_key, 1))

    text = f"🌙 *Прогноз {label}*\n\n{reading}\n\n{note}"
    await split_and_send(update, text, main_menu())

# ── Текстовый роутер ─────────────────────────────────────────────────────────

async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    waiting = context.user_data.get("waiting_for")
    text = update.message.text.strip()

    if waiting == "tarot_question":
        await _do_tarot(update, context, text)

    elif waiting == "fortune_question":
        await _do_fortune(update, context, text)

    elif waiting == "natal_date":
        try:
            datetime.strptime(text, "%d.%m.%Y")
        except ValueError:
            await update.message.reply_text(
                "❌ Неверный формат. Введите дату как *ДД.ММ.ГГГГ*\n_Пример: 15.03.1990_",
                parse_mode="Markdown",
            )
            return
        context.user_data["birth_date"] = text
        context.user_data["waiting_for"] = "natal_time"
        await update.message.reply_text(
            "🕐 Введите время рождения *ЧЧ:ММ*\n_Пример: 14:30. Если не знаете — введите 12:00_",
            parse_mode="Markdown",
        )

    elif waiting == "natal_time":
        try:
            datetime.strptime(text, "%H:%M")
        except ValueError:
            await update.message.reply_text(
                "❌ Неверный формат. Введите время как *ЧЧ:ММ*\n_Пример: 14:30_",
                parse_mode="Markdown",
            )
            return
        context.user_data["birth_time"] = text
        context.user_data["waiting_for"] = "natal_place"
        await update.message.reply_text(
            "📍 Введите город и страну рождения\n_Пример: Москва, Россия_",
            parse_mode="Markdown",
        )

    elif waiting == "natal_place":
        context.user_data["birth_place"] = text
        context.user_data.pop("waiting_for", None)
        await _do_natal(update, context)

    else:
        await update.message.reply_text(
            "Выберите действие из меню:",
            reply_markup=main_menu(),
        )

# ── Error handler ────────────────────────────────────────────────────────────

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error("Unhandled exception", exc_info=context.error)
    if isinstance(update, Update) and update.effective_chat:
        await context.bot.send_message(
            update.effective_chat.id,
            "⚠️ Что-то пошло не так. Попробуйте ещё раз или вернитесь в меню /menu",
        )

# ── Entry point ──────────────────────────────────────────────────────────────

async def _post_init(app: Application) -> None:
    await init_db()
    logger.info("✅ База данных инициализирована")


def main():
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(_post_init)
        .build()
    )

    # Commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("menu",  show_menu))

    # Callback handlers (order matters — more specific first)
    app.add_handler(CallbackQueryHandler(show_menu,       pattern="^menu$"))
    app.add_handler(CallbackQueryHandler(balance_cb,      pattern="^balance$"))
    app.add_handler(CallbackQueryHandler(buy_cb,          pattern="^buy$"))
    app.add_handler(CallbackQueryHandler(pay_pack_cb,     pattern="^pay_pack_"))
    # Tarot
    app.add_handler(CallbackQueryHandler(tarot_cb,        pattern="^tarot$"))
    app.add_handler(CallbackQueryHandler(spread_cb,       pattern="^spread_"))
    app.add_handler(CallbackQueryHandler(tarot_skip_cb,   pattern="^tarot_skip$"))
    # Fortune
    app.add_handler(CallbackQueryHandler(fortune_cb,      pattern="^fortune$"))
    app.add_handler(CallbackQueryHandler(fmethod_cb,      pattern="^fmethod_"))
    app.add_handler(CallbackQueryHandler(fortune_skip_cb, pattern="^fortune_skip$"))
    # Natal
    app.add_handler(CallbackQueryHandler(natal_cb,        pattern="^natal$"))
    app.add_handler(CallbackQueryHandler(natal_saved_cb,  pattern="^natal_saved$"))
    app.add_handler(CallbackQueryHandler(natal_new_cb,    pattern="^natal_new$"))
    # Forecast
    app.add_handler(CallbackQueryHandler(forecast_cb,     pattern="^forecast$"))
    app.add_handler(CallbackQueryHandler(fperiod_cb,      pattern="^fperiod_"))
    app.add_handler(CallbackQueryHandler(sign_cb,         pattern="^sign_"))

    # Payments
    app.add_handler(PreCheckoutQueryHandler(precheckout_cb))
    app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, payment_done))

    # Text router (must be last)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))

    app.add_error_handler(error_handler)

    logger.info("🌟 АстроБот запущен")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
