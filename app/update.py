"""Actualización de la app: git fetch/pull sobre el propio checkout.

El bootstrap instala clonando el repo, así que actualizar = git pull. Si la
instalación no es un checkout (zip suelto), se informa y no se toca nada.
"""
import subprocess
import sys
from pathlib import Path

REPO_DIR = Path(__file__).resolve().parent.parent


def _git(*args: str, timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=REPO_DIR,
                          capture_output=True, text=True, timeout=timeout)


def is_git_checkout() -> bool:
    return (REPO_DIR / ".git").exists()


def check() -> dict:
    """Consulta el remoto y devuelve cuántos commits vamos por detrás."""
    if not is_git_checkout():
        return {"git": False}
    try:
        f = _git("fetch", "--quiet", "origin", "main", timeout=60)
    except (subprocess.TimeoutExpired, OSError) as e:
        return {"git": True, "error": str(e)[:200]}
    if f.returncode != 0:
        return {"git": True, "error": (f.stderr.strip() or "git fetch falló")[:200]}
    behind = _git("rev-list", "--count", "HEAD..origin/main").stdout.strip()
    return {
        "git": True,
        "current": _git("rev-parse", "--short", "HEAD").stdout.strip(),
        "behind": int(behind or 0),
        "latest": _git("log", "-1", "--format=%s", "origin/main").stdout.strip(),
    }


def apply() -> dict:
    """git pull --ff-only. Avisa si cambiaron las dependencias (reinstalar)."""
    if not is_git_checkout():
        return {"error": "la instalación no es un checkout de git"}
    diff = _git("diff", "--name-only", "HEAD..origin/main").stdout
    deps_changed = "pyproject.toml" in diff or "uv.lock" in diff
    try:
        p = _git("pull", "--ff-only", "origin", "main", timeout=120)
    except (subprocess.TimeoutExpired, OSError) as e:
        return {"error": str(e)[:300]}
    if p.returncode != 0:
        return {"error": (p.stderr or p.stdout).strip()[:300]}
    return {"ok": True, "deps_changed": deps_changed,
            "current": _git("rev-parse", "--short", "HEAD").stdout.strip()}


def installer_hint() -> str:
    return "install.ps1" if sys.platform.startswith("win") else "./install.sh"
