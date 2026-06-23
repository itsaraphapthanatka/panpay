FROM python:3.14-slim-bookworm

# Runtime libs: opencv-python-headless needs libGL/glib/gomp; psycopg[binary] bundles libpq;
# fonts-thai-tlwg lets PDF receipts render Thai text.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
        fonts-thai-tlwg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

# Apply migrations, then serve. (Override DATABASE_URL etc. via env.)
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
