# Multi-stage y runtime sin privilegios root (rubrica EVA 02).
FROM python:3.12-alpine AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt

FROM python:3.12-alpine
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY --from=builder /wheels /wheels
COPY requirements.txt .
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt \
    && rm -rf /wheels \
    && addgroup -S appgroup \
    && adduser -S appuser -G appgroup
COPY --chown=appuser:appgroup app ./app
COPY --chown=appuser:appgroup scripts ./scripts
COPY --chown=appuser:appgroup migrations ./migrations
COPY --chown=appuser:appgroup alembic.ini ./alembic.ini
USER appuser
EXPOSE 8000
CMD ["sh", "-c", "python -m scripts.migrate && exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"]
