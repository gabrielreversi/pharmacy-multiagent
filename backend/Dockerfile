FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_NO_INTERACTION=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    HF_HOME=/app/.cache/huggingface

WORKDIR /app

RUN pip install --no-cache-dir poetry==2.2.1 && python -m venv /opt/venv

COPY pyproject.toml poetry.lock ./
RUN poetry install --only main --no-root && rm -rf /root/.cache/pypoetry

RUN python -c "import laya; laya.load('convaiinnovations/laya')"

COPY alembic.ini ./
COPY migrations/ ./migrations/
COPY src/ ./src/

WORKDIR /app/src
EXPOSE 8000
CMD ["uvicorn", "aplication.api:app", "--host", "0.0.0.0", "--port", "8000"]
