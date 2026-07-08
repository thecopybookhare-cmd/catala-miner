"""Optional IPA via espeak-ng (brew). Empty string when unavailable."""
import shutil
import subprocess
from functools import lru_cache


@lru_cache(maxsize=4096)
def _run_ipa(text: str, voice: str) -> str:
    exe = shutil.which("espeak-ng") or shutil.which("espeak")
    if not exe or not text:
        return ""
    try:
        out = subprocess.run([exe, "-q", "--ipa", "-v", voice, text],
                             capture_output=True, text=True, timeout=5)
        s = " ".join(out.stdout.split())
        return f"/{s}/" if s else ""
    except Exception:
        return ""


def ipa(text: str) -> str:
    from . import languages
    return _run_ipa(text, languages.profile()["espeak"])
