FROM python:3.14-slim

WORKDIR /srv/app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY scripts ./scripts
COPY site ./site

RUN useradd --create-home appuser && chown -R appuser:appuser /srv/app
USER appuser

EXPOSE 8000

# Migrations run before the server starts; exec hands PID 1 to uvicorn so
# signals (docker stop) reach it directly.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
