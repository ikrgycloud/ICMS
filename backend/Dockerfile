FROM python:3.12-slim

WORKDIR /app

# System dependencies for PostgreSQL / psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Application source
COPY . .

EXPOSE 8000

# Run the complete application bootstrap first,
# then start FastAPI.
CMD ["sh", "-c", "python bootstrap.py && exec uvicorn main:app --host 0.0.0.0 --port 8000"]
