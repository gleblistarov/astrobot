import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
DATABASE_PATH = os.getenv("DATABASE_PATH", "astrobot.db")

# Бесплатных раскладов при регистрации
FREE_READINGS = 2

# Пакеты кредитов (Stars — внутренняя валюта Telegram)
CREDIT_PACKS = {
    "pack_10":  {"stars": 50,  "credits": 10,  "title": "10 раскладов"},
    "pack_30":  {"stars": 130, "credits": 30,  "title": "30 раскладов"},
    "pack_100": {"stars": 380, "credits": 100, "title": "100 раскладов"},
}

# Стоимость каждого типа расклада в кредитах
READING_COSTS = {
    "tarot_three_cards": 1,
    "tarot_five_cards":  2,
    "tarot_celtic":      3,
    "fortune":           1,
    "natal":             2,
    "forecast_day":      1,
    "forecast_week":     2,
    "forecast_month":    3,
}
