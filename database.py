import aiosqlite
from config import DATABASE_PATH


async def init_db():
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id            INTEGER PRIMARY KEY,
                username           TEXT,
                first_name         TEXT,
                credits            INTEGER DEFAULT 0,
                free_readings_used INTEGER DEFAULT 0,
                birth_date         TEXT,
                birth_time         TEXT,
                birth_place        TEXT,
                registered_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS readings (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      INTEGER,
                reading_type TEXT,
                question     TEXT,
                result       TEXT,
                credits_spent INTEGER DEFAULT 0,
                created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id                    INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id               INTEGER,
                telegram_payment_id   TEXT,
                stars_paid            INTEGER,
                credits_added         INTEGER,
                created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        """)
        await db.commit()


async def get_or_create_user(user_id: int, username: str = None, first_name: str = None) -> dict:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        if not row:
            await db.execute(
                "INSERT INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
                (user_id, username, first_name),
            )
            await db.commit()
            cur = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = await cur.fetchone()
        return dict(row)


async def get_user(user_id: int) -> dict | None:
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def use_free_reading(user_id: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE users SET free_readings_used = free_readings_used + 1 WHERE user_id = ?",
            (user_id,),
        )
        await db.commit()


async def deduct_credits(user_id: int, amount: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE users SET credits = credits - ? WHERE user_id = ?",
            (amount, user_id),
        )
        await db.commit()


async def add_credits(user_id: int, amount: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE users SET credits = credits + ? WHERE user_id = ?",
            (amount, user_id),
        )
        await db.commit()


async def update_birth_data(user_id: int, birth_date: str, birth_time: str, birth_place: str):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "UPDATE users SET birth_date=?, birth_time=?, birth_place=? WHERE user_id=?",
            (birth_date, birth_time, birth_place, user_id),
        )
        await db.commit()


async def save_reading(user_id: int, reading_type: str, question: str, result: str, cost: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "INSERT INTO readings (user_id, reading_type, question, result, credits_spent) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, reading_type, question, result, cost),
        )
        await db.commit()


async def save_payment(user_id: int, payment_id: str, stars: int, credits: int):
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute(
            "INSERT INTO payments (user_id, telegram_payment_id, stars_paid, credits_added) "
            "VALUES (?, ?, ?, ?)",
            (user_id, payment_id, stars, credits),
        )
        await db.commit()
