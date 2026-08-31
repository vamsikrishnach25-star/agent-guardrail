# Slim image is enough here - no compiled deps beyond psycopg2-binary,
# which ships its own wheel (no build toolchain needed at all).
#
# NOTE: built with the repo root as build context (see docker-compose.yml:
# `context: .`, `dockerfile: backend/Dockerfile`), not the backend/ folder
# itself - that's why requirements.txt is copied from the root and app/
# is copied from backend/app. Building this Dockerfile standalone with
# `docker build backend/` will NOT work; use docker-compose.
FROM python:3.11-slim

WORKDIR /app

# Install deps first so Docker can cache this layer across code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
