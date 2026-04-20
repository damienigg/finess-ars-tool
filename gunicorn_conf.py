"""Configuration gunicorn pour l'exécution en production.

Lancer : `gunicorn -c gunicorn_conf.py app.main:app`
"""

from __future__ import annotations

import multiprocessing
import os

bind = os.getenv("GUNICORN_BIND", "0.0.0.0:8000")
workers = int(os.getenv("GUNICORN_WORKERS", max(2, multiprocessing.cpu_count())))
worker_class = "uvicorn.workers.UvicornWorker"
timeout = int(os.getenv("GUNICORN_TIMEOUT", 60))
graceful_timeout = 30
keepalive = 5

accesslog = os.getenv("GUNICORN_ACCESS_LOG", "-")
errorlog = os.getenv("GUNICORN_ERROR_LOG", "-")
loglevel = os.getenv("GUNICORN_LOG_LEVEL", "info")

# Recycle workers to keep memory bounded.
max_requests = int(os.getenv("GUNICORN_MAX_REQUESTS", 1000))
max_requests_jitter = 100

proc_name = "finess-ars"
forwarded_allow_ips = os.getenv("FORWARDED_ALLOW_IPS", "127.0.0.1")
