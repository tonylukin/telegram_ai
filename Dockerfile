FROM python:3.12-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем зависимости и устанавливаем их
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Копируем всё остальное
COPY . .

# Устанавливаем переменную окружения PYTHONPATH
ENV PYTHONPATH=/app

# Команда по умолчанию для запуска бота
CMD ["python3", "app/bots/human_scanner_ai/main.py"]
