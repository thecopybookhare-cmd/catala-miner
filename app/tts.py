"""Pronunciación de palabra con espeak-ng (offline, opcional).
Genera wav cacheado por hash en MEDIA_DIR; '' si espeak no está."""
import hashlib
import shutil
import subprocess

from . import config


def speak(text: str) -> str:
    text = (text or "").strip()
    exe = shutil.which("espeak-ng") or shutil.which("espeak")
    if not exe or not text:
        return ""
    name = "tts-" + hashlib.md5(text.encode()).hexdigest()[:12] + ".wav"
    out = config.MEDIA_DIR / name
    if out.exists():
        return name
    try:
        subprocess.run([exe, "-v", "ca", "-s", "150", "-w", str(out), text],
                       check=True, capture_output=True, timeout=10)
        return name if out.exists() else ""
    except Exception:
        return ""
