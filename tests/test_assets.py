"""Invariante de release: el cache-bust de los assets debe subir con la versión.

Si `static/index.html` referencia `app.js?v=X` con una X vieja, los navegadores
(y el WKWebView del escritorio) sirven el JS/CSS cacheado y los usuarios que ya
usaron una versión previa nunca reciben los arreglos. Este test ata el `?v=` a
la versión de `pyproject.toml` para que no vuelva a quedar rezagado.
"""
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _project_version() -> str:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text())
    return data["project"]["version"]


def test_index_cache_bust_matches_version():
    html = (ROOT / "static" / "index.html").read_text()
    versions = set(re.findall(r"\?v=([0-9]+\.[0-9]+\.[0-9]+)", html))
    assert versions, "index.html debería usar cache-bust ?v=… en sus assets"
    assert versions == {_project_version()}, (
        f"cache-bust {versions} no coincide con la versión "
        f"{_project_version()} de pyproject.toml"
    )
