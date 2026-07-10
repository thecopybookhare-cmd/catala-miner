"""Pronunciación de palabra: voz neural Piper si está disponible, si no
espeak-ng (offline, opcional). Genera wav cacheado por hash en MEDIA_DIR;
'' si no hay ninguna voz."""
import hashlib
import shutil
import subprocess

from . import config


def speak(text: str) -> str:
    from . import languages, piper_tts
    text = (text or "").strip()
    if not text:
        return ""
    natural = piper_tts.speak(text)        # voz neural Piper (preferida)
    if natural:
        return natural
    exe = shutil.which("espeak-ng") or shutil.which("espeak")
    if not exe:
        return ""
    voice = languages.profile()["espeak"]
    name = ("tts-" + voice + "-"
            + hashlib.md5(text.encode()).hexdigest()[:12] + ".wav")
    out = config.MEDIA_DIR / name
    if out.exists():
        return name
    try:
        subprocess.run([exe, "-v", voice, "-s", "150", "-w", str(out), text],
                       check=True, capture_output=True, timeout=10)
        return name if out.exists() else ""
    except Exception:
        return ""
