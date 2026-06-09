import random

# ── 22 Старших аркана ────────────────────────────────────────────────────────

MAJOR_ARCANA = [
    "Шут (0)", "Маг (I)", "Верховная Жрица (II)", "Императрица (III)",
    "Император (IV)", "Иерофант (V)", "Влюблённые (VI)", "Колесница (VII)",
    "Сила (VIII)", "Отшельник (IX)", "Колесо Фортуны (X)", "Справедливость (XI)",
    "Повешенный (XII)", "Смерть (XIII)", "Умеренность (XIV)", "Дьявол (XV)",
    "Башня (XVI)", "Звезда (XVII)", "Луна (XVIII)", "Солнце (XIX)",
    "Суд (XX)", "Мир (XXI)",
]

# ── 56 Младших аркана ────────────────────────────────────────────────────────

def _suit(name: str, symbol: str) -> list[str]:
    cards = [f"Туз {name}", f"Двойка {name}", f"Тройка {name}",
             f"Четвёрка {name}", f"Пятёрка {name}", f"Шестёрка {name}",
             f"Семёрка {name}", f"Восьмёрка {name}", f"Девятка {name}",
             f"Десятка {name}", f"Паж {name}", f"Рыцарь {name}",
             f"Королева {name}", f"Король {name}"]
    return [f"{symbol} {c}" for c in cards]

MINOR_ARCANA = (
    _suit("Жезлов", "🔥") +
    _suit("Кубков", "💧") +
    _suit("Мечей", "💨") +
    _suit("Пентаклей", "🌍")
)

FULL_DECK = MAJOR_ARCANA + MINOR_ARCANA  # 78 карт


def get_random_cards(n: int) -> list[dict]:
    """Вернуть n уникальных карт, каждая может быть перевёрнутой (30 %)."""
    chosen = random.sample(FULL_DECK, min(n, len(FULL_DECK)))
    return [
        {"name": card, "reversed": random.random() < 0.30}
        for card in chosen
    ]


def format_cards(cards: list[dict]) -> str:
    parts = []
    for i, c in enumerate(cards, 1):
        rev = " ↕" if c["reversed"] else ""
        parts.append(f"{i}. *{c['name']}*{rev}")
    return "\n".join(parts)
