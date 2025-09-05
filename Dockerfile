FROM python:3.12-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем зависимости и устанавливаем их
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Install Playwright + browser binaries
#RUN pip install playwright && playwright install --with-deps && pip install playwright-stealth

# Копируем всё остальное
COPY . .

# Устанавливаем переменную окружения PYTHONPATH
ENV PYTHONPATH=/app

# Открываем порт (если используешь 8000)
EXPOSE 8000

CMD ["bash", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
