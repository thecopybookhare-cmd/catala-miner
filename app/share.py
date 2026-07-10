"""Modo compartir: sirve la app a la red local / tailnet bajo demanda.

Por defecto la app solo escucha en 127.0.0.1 (privada). Al activar el modo
compartir se arranca un *segundo* servidor en 0.0.0.0:SHARE_PORT dentro de un
hilo, accesible desde otros dispositivos de tu red local o de tu tailnet
(Tailscale). Se apaga con stop(). Nada queda expuesto hasta activarlo.

Ojo: quien acceda tiene la app completa (no hay modo invitado), así que
pensado para amigos de confianza en tu red privada / tailnet.
"""
import io
import ipaddress
import shutil
import socket
import subprocess
import threading
import time
from pathlib import Path

from . import config

SHARE_PORT = config.PORT + 1          # 8978

_server = None                        # uvicorn.Server
_thread: threading.Thread | None = None


def _lan_ips() -> list[str]:
    """IPv4 privadas por las que otros dispositivos de tu red pueden entrar."""
    ips: set[str] = set()
    try:                              # IP de la interfaz de salida por defecto
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ips.add(s.getsockname()[0])
        s.close()
    except Exception:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ip = info[4][0]
            if ip and not ip.startswith("127.") and ipaddress.ip_address(ip).is_private:
                ips.add(ip)
    except Exception:
        pass
    return sorted(ips)


def _tailscale_exe() -> str | None:
    exe = shutil.which("tailscale")
    if exe:
        return exe
    mac = "/Applications/Tailscale.app/Contents/MacOS/Tailscale"
    return mac if Path(mac).exists() else None


def _tailscale_ip() -> str | None:
    """IP 100.x del tailnet (CGNAT), o None si Tailscale no está activo."""
    exe = _tailscale_exe()
    if not exe:
        return None
    try:
        out = subprocess.run([exe, "ip", "-4"], capture_output=True,
                             text=True, timeout=4)
        lines = [ln.strip() for ln in out.stdout.splitlines() if ln.strip()]
        return lines[0] if lines else None
    except Exception:
        return None


def is_running() -> bool:
    return _server is not None and getattr(_server, "started", False)


def start() -> dict:
    global _server, _thread
    if is_running():
        return status()
    import uvicorn

    from .main import app
    cfg = uvicorn.Config(app, host="0.0.0.0", port=SHARE_PORT,
                         log_level="warning", log_config=None)
    _server = uvicorn.Server(cfg)
    _server.install_signal_handlers = lambda: None      # no en hilo principal
    _thread = threading.Thread(target=_server.run, daemon=True)
    _thread.start()
    for _ in range(60):                                 # esperar a que levante
        if getattr(_server, "started", False):
            break
        time.sleep(0.1)
    return status()


def stop() -> dict:
    global _server, _thread
    if _server is not None:
        _server.should_exit = True
        if _thread is not None:
            _thread.join(timeout=6)
    _server, _thread = None, None
    return status()


def status() -> dict:
    running = is_running()
    ts_ip = _tailscale_ip()
    urls: list[dict] = []
    if running:
        for ip in _lan_ips():
            urls.append({"label": "Red local", "url": f"http://{ip}:{SHARE_PORT}"})
        if ts_ip:
            urls.append({"label": "Tailscale", "url": f"http://{ts_ip}:{SHARE_PORT}"})
    return {
        "running": running,
        "port": SHARE_PORT,
        "urls": urls,
        "tailscale": _tailscale_exe() is not None,
        "tailscale_up": ts_ip is not None,
        "tailscale_ip": ts_ip,
    }


def qr_svg(url: str) -> str:
    """QR en SVG (sin PIL) para escanear la URL desde el móvil de un amigo."""
    import qrcode
    import qrcode.image.svg
    img = qrcode.make(url, image_factory=qrcode.image.svg.SvgPathImage,
                      box_size=10, border=2)
    buf = io.BytesIO()
    img.save(buf)
    return buf.getvalue().decode("utf-8")
