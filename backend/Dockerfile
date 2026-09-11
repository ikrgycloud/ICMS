FROM python:3.12-slim

WORKDIR /app

# System deps for psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Development mode may seed demo data on startup. Production mode performs
# only additive schema checks and never seeds tenant operational data.
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
