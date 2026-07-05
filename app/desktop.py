"""CatalàMiner como app de escritorio: uvicorn en un hilo + WKWebView."""
import socket
import threading
import time

from . import config


def _serve():
    import uvicorn
    from .main import app
    uvicorn.run(app, host="127.0.0.1", port=config.PORT, log_level="warning")


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
    import webview
    threading.Thread(target=_serve, daemon=True).start()
    _wait_port(config.PORT)
    webview.create_window("CatalàMiner", f"http://127.0.0.1:{config.PORT}",
                          width=1280, height=860, min_size=(980, 640))
    webview.start()


if __name__ == "__main__":
    main()
