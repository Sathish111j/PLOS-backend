FROM python:3.11-slim

WORKDIR /app

# Install deps first so layer is cached unless requirements change
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot/ ./bot/

# Persistence directory (mounted as volume in compose)
RUN mkdir -p data

CMD ["python", "-m", "bot.main"]
