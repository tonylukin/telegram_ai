FROM python:3.12-slim

WORKDIR /app

# Copy and install dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Install Playwright + browser binaries
#RUN pip install playwright && playwright install --with-deps && pip install playwright-stealth

COPY . .

# set env PYTHONPATH
ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["bash", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
