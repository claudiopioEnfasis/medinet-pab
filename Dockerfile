# Multi-stage y runtime sin privilegios root (rubrica EVA 02).
FROM python:3.12-alpine@sha256:e6dae589c1c05976188fd3bd019afd091445fc533ed2ea29001beddc7368a9c8 AS builder
RUN apk upgrade --no-cache \
    && python -m pip install --no-cache-dir --upgrade pip==26.2.2
WORKDIR /build
COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt
# Descarga por HTTPS y comprueba que el archivo contiene certificados utilizables.
RUN python -c "import ssl; from urllib.request import urlopen; response = urlopen('https://truststore.pki.rds.amazonaws.com/us-east-1/us-east-1-bundle.pem', timeout=30); pem = response.read().decode('ascii'); response.close(); ssl.create_default_context(cadata=pem); open('/build/rds-us-east-1.pem', 'w', encoding='ascii').write(pem)"

FROM python:3.12-alpine@sha256:e6dae589c1c05976188fd3bd019afd091445fc533ed2ea29001beddc7368a9c8
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN apk upgrade --no-cache
COPY --from=builder /wheels /wheels
COPY --from=builder /build/rds-us-east-1.pem /usr/local/share/rds/us-east-1-bundle.pem
COPY requirements.txt .
RUN pip install --no-cache-dir --no-index --find-links=/wheels -r requirements.txt \
    && python -m pip uninstall --yes pip \
    && rm -rf /wheels \
    && addgroup -S appgroup \
    && adduser -S appuser -G appgroup
COPY --chown=appuser:appgroup app ./app
COPY --chown=appuser:appgroup scripts ./scripts
COPY --chown=appuser:appgroup migrations ./migrations
COPY --chown=appuser:appgroup alembic.ini ./alembic.ini
USER appuser
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
