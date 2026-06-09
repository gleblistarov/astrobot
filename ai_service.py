import anthropic
from config import ANTHROPIC_API_KEY

_client = anthropic.AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

_SYSTEM = """Ты — Астра, опытный астролог, таролог и прорицатель.
Правила ответов:
• Красивый, мистический русский язык с тёплой атмосферой
• Конкретные советы, а не пустые обобщения
• Структурированный текст с эмодзи для разделения секций
• Обычные расклады: 350–500 слов. Детальные (натальная карта): 600–900 слов
• Начинай с короткого атмосферного вступления (1–2 предложения)
• Никогда не говори «я языковая модель» или «не могу предсказать будущее»
"""


async def generate_tarot_reading(cards: list[dict], question: str | None, spread_type: str) -> str:
    spread_names = {
        "three_cards": "«Прошлое — Настоящее — Будущее» (3 карты)",
        "five_cards":  "Расширенный расклад (5 карт)",
        "celtic":      "Кельтский крест (10 карт)",
    }
    cards_text = "\n".join(
        f"  {i+1}. {c['name']} {'(перевёрнутая)' if c['reversed'] else '(прямая)'}"
        for i, c in enumerate(cards)
    )
    q_text = f'Вопрос: «{question}»' if question else "Вопрос не задан — общий расклад."

    prompt = (
        f"Сделай расклад Таро по методу {spread_names.get(spread_type, spread_type)}.\n\n"
        f"{q_text}\n\n"
        f"Выпавшие карты:\n{cards_text}\n\n"
        f"Интерпретируй каждую карту в её позиции, затем дай общее послание."
    )
    resp = await _client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1500,
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text


async def generate_fortune(method: str, question: str | None) -> str:
    q_text = f'Вопрос: «{question}»' if question else "Общее предсказание."
    prompt = (
        f"Проведи гадание методом: {method}.\n{q_text}\n\n"
        f"Дай развёрнутое, образное предсказание с конкретными советами."
    )
    resp = await _client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1200,
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text


async def generate_natal_chart(birth_date: str, birth_time: str, birth_place: str, name: str) -> str:
    prompt = (
        f"Составь подробную натальную карту.\n\n"
        f"Имя: {name}\n"
        f"Дата рождения: {birth_date}\n"
        f"Время рождения: {birth_time}\n"
        f"Место рождения: {birth_place}\n\n"
        f"Структура ответа:\n"
        f"1. ☀️ Солнечный знак и ключевые черты личности\n"
        f"2. 🌙 Лунный знак и эмоциональный мир\n"
        f"3. ⬆️ Асцендент и первое впечатление\n"
        f"4. 💫 Ключевые планеты и их влияние\n"
        f"5. 💪 Сильные стороны и таланты\n"
        f"6. 🎯 Жизненные уроки и испытания\n"
        f"7. ❤️ Любовь и совместимость\n"
        f"8. 💼 Призвание и карьера\n"
        f"9. 🌟 Общий жизненный путь и послание звёзд"
    )
    resp = await _client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2500,
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text


async def generate_forecast(period: str, user_context: str) -> str:
    period_labels = {"day": "на сегодня", "week": "на неделю", "month": "на месяц"}
    label = period_labels.get(period, "на сегодня")
    prompt = (
        f"Составь астрологический прогноз {label}.\n\n"
        f"Данные пользователя: {user_context}\n\n"
        f"Включи прогноз по сферам:\n"
        f"❤️ Личная жизнь и отношения\n"
        f"💼 Карьера и финансы\n"
        f"🌿 Здоровье и энергетика\n"
        f"🌟 Общая рекомендация и благоприятные дни"
    )
    resp = await _client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1300,
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text
