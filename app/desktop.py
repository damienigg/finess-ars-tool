"""Lanceur desktop pour Finess-for-Laure (Windows / macOS / Linux).

Lance uvicorn dans un thread en fond et affiche l'interface dans une
fenêtre WebView. Aucun terminal ne s'affiche pour l'utilisateur final.
"""

from __future__ import annotations

import logging
import socket
import sys
import threading
import time
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
            # Important en mode gelé : pas de reload, pas de workers.
            reload=False,
            workers=1,
            lifespan="on",
        )
        self.server = uvicorn.Server(config)

    def run(self) -> None:
        self.server.run()

    def shutdown(self) -> None:
        self.server.should_exit = True


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

    try:
        import webview
    except ImportError:
        logger.error("pywebview n'est pas installé. `pip install pywebview`")
        server.shutdown()
        return 3

    url = f"http://127.0.0.1:{port}/"
    logger.info("Ouverture de la fenêtre sur %s", url)
    webview.create_window(
        APP_TITLE,
        url=url,
        width=WINDOW_SIZE[0],
        height=WINDOW_SIZE[1],
        resizable=True,
        min_size=(960, 640),
    )
    try:
        webview.start()
    finally:
        logger.info("Fermeture — arrêt du serveur")
        server.shutdown()
        server.join(timeout=5)
    return 0


if __name__ == "__main__":
    sys.exit(main())
