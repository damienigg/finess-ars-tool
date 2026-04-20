"""Lanceur desktop pour Finess-for-Laure (Windows / macOS / Linux).

Lance uvicorn dans un thread en fond et affiche l'interface dans une
fenêtre WebView. Si pywebview n'est pas disponible (ex. Linux sans
WebKit2), ouvre l'URL dans le navigateur par défaut.
"""

from __future__ import annotations

import logging
import os
import socket
import sys
import threading
import time
import webbrowser
from contextlib import closing
from urllib.request import urlopen

import uvicorn

from app.logging_conf import configure_logging
from app.main import app

APP_TITLE = "Finess-for-Laure"
READY_TIMEOUT_SECONDS = 15
WINDOW_SIZE = (1280, 860)


def _find_free_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _wait_until_ready(port: int, timeout: float = READY_TIMEOUT_SECONDS) -> bool:
    """Attend que /healthz réponde 200 avant d'ouvrir la fenêtre."""
    deadline = time.monotonic() + timeout
    url = f"http://127.0.0.1:{port}/healthz"
    while time.monotonic() < deadline:
        try:
            with urlopen(url, timeout=1) as resp:
                if resp.status == 200:
                    return True
        except Exception:  # noqa: BLE001 - polling, any error = not ready yet
            time.sleep(0.2)
    return False


class _ServerThread(threading.Thread):
    """Wrapper qui porte une référence au Server uvicorn pour l'arrêt propre."""

    def __init__(self, port: int):
        super().__init__(daemon=True, name="finess-server")
        config = uvicorn.Config(
            app=app,
            host="127.0.0.1",
            port=port,
            log_level="warning",
            access_log=False,
            reload=False,
            workers=1,
            lifespan="on",
        )
        self.server = uvicorn.Server(config)

    def run(self) -> None:
        self.server.run()

    def shutdown(self) -> None:
        self.server.should_exit = True


def _open_webview(url: str, logger: logging.Logger) -> bool:
    """Essaye d'ouvrir la fenêtre pywebview. Retourne True si OK."""
    try:
        import webview
    except ImportError:
        logger.info("pywebview indisponible, fallback navigateur.")
        return False

    try:
        webview.create_window(
            APP_TITLE,
            url=url,
            width=WINDOW_SIZE[0],
            height=WINDOW_SIZE[1],
            resizable=True,
            min_size=(960, 640),
        )
        webview.start()
        return True
    except Exception as exc:  # noqa: BLE001
        # Linux sans WebKit2 lève ValueError au démarrage.
        logger.warning("pywebview a échoué (%s), fallback navigateur.", exc)
        return False


def _open_browser_and_wait(url: str, logger: logging.Logger) -> None:
    """Fallback : ouvre le navigateur par défaut et laisse le serveur tourner."""
    webbrowser.open(url)
    logger.info("Application disponible sur %s", url)
    print(
        f"\n  Finess-for-Laure est ouvert dans votre navigateur : {url}\n"
        "  Fermez cette fenêtre (Ctrl+C) pour arrêter l'application.\n",
        flush=True,
    )
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        logger.info("Arrêt demandé (Ctrl+C)")


def main() -> int:
    configure_logging()
    logger = logging.getLogger("finess-for-laure")

    port = _find_free_port()
    logger.info("Démarrage du serveur local sur 127.0.0.1:%d", port)
    server = _ServerThread(port)
    server.start()

    if not _wait_until_ready(port):
        logger.error("Le serveur ne répond pas sous %ds — abandon.", READY_TIMEOUT_SECONDS)
        server.shutdown()
        return 2

    url = f"http://127.0.0.1:{port}/"

    # FINESS_NO_WEBVIEW=1 force le fallback navigateur (utile pour tests CI / headless).
    force_browser = os.getenv("FINESS_NO_WEBVIEW") == "1"

    try:
        if force_browser or not _open_webview(url, logger):
            _open_browser_and_wait(url, logger)
    finally:
        logger.info("Fermeture — arrêt du serveur")
        server.shutdown()
        server.join(timeout=5)
    return 0


if __name__ == "__main__":
    sys.exit(main())
