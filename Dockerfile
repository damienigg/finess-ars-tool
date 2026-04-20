FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Dépendances système pour pyproj (grilles EPSG).
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      libproj-dev proj-data proj-bin \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install -r requirements.txt

COPY app ./app
COPY migrations ./migrations
COPY alembic.ini gunicorn_conf.py pyproject.toml ./

# Runtime uid non-root.
RUN useradd --system --create-home --uid 1000 finess \
 && chown -R finess:finess /app
USER finess

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; \
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz',timeout=3).status==200 else 1)"

CMD ["gunicorn", "-c", "gunicorn_conf.py", "app.main:app"]
