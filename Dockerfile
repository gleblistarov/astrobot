FROM python:3.11-slim

WORKDIR /app

# Системные зависимости
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Папка для SQLite базы данных (монтируется как volume на Railway/Fly.io)
RUN mkdir -p /data
ENV DATABASE_PATH=/data/astrobot.db

CMD ["python", "bot.py"]
