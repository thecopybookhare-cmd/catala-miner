"""CatalàMiner como app de escritorio: uvicorn en un hilo + WKWebView."""
import logging
import os
import socket
import threading
import time

from . import config

LOG_PATH = config.APP_DIR / "desktop.log"

# Lanzada por LaunchServices (doble clic), la app NO hereda el PATH de la
# terminal: ffmpeg/ffprobe/espeak-ng de Homebrew quedan invisibles y todo
# subprocess.run(["ffprobe", ...]) revienta con FileNotFoundError.
for _hb in ("/opt/homebrew/bin", "/usr/local/bin"):
    if _hb not in os.environ.get("PATH", "").split(os.pathsep):
        os.environ["PATH"] = _hb + os.pathsep + os.environ.get("PATH", "")


def _setup_logging():
    """La app empaquetada no tiene terminal — stdout/stderr van a /dev/null.
    Sin esto, cualquier excepción del servidor es indiagnosticable."""
    handler = logging.FileHandler(str(LOG_PATH))
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)


def _serve():
    import uvicorn
    from .main import app
    uvicorn.run(app, host="127.0.0.1", port=config.PORT, log_level="info",
                log_config=None)


def _wait_port(port: int, secs: float = 20.0) -> bool:
    t0 = time.time()
    while time.time() - t0 < secs:
        with socket.socket() as s:
            s.settimeout(0.3)
            if s.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.2)
    return False


def main():
    _setup_logging()
    log = logging.getLogger("desktop")
    log.info("arrancando CatalàMiner desktop, log en %s", LOG_PATH)
    try:
        import webview
        threading.Thread(target=_serve, daemon=True).start()
        _wait_port(config.PORT)
        webview.create_window("CatalàMiner", f"http://127.0.0.1:{config.PORT}",
                              width=1280, height=860, min_size=(980, 640))
        webview.start()
    except Exception:
        log.exception("fallo no capturado en main()")
        raise
    log.info("cerrado normalmente")


if __name__ == "__main__":
    main()
