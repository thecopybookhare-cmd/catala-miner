"""Apertium bidix (spa-cat) as a ca->es sense dictionary.

The bidix is downloaded once from GitHub (config.BIDIX_URL) and parsed as
plain XML — Apertium itself is never installed. <l> = Spanish, <r> = Catalan.
"""
import xml.etree.ElementTree as ET

import requests

from . import config

_BIDIX_PATH = config.MODELS_DIR / "apertium-spa-cat.dix"


def _collect(el, parts: list[str]):
    parts.append(el.text or "")
    for child in el:
        if child.tag in ("b", "j"):
            parts.append(" ")
        elif child.tag in ("s", "v", "par"):
            pass
        else:
            _collect(child, parts)
        parts.append(child.tail or "")


def _side_text(el) -> str:
    """Text of <l>/<r>: <b/>/<j/> are spaces; <s>/<v> are grammar symbols
    (no surface text); <g> groups nest and are recursed into."""
    parts: list[str] = []
    _collect(el, parts)
    return " ".join("".join(parts).split())


def _first_symbol(el) -> str:
    s = el.find("s")
    return s.get("n", "") if s is not None else ""


def parse_bidix(xml_text: str, src: str = "r") -> dict[str, list[tuple[str, str]]]:
    """Return {source_lemma_lower: [(spanish, pos), ...]} preserving order.

    ``src`` dice en qué lado del par vive la lengua de origen (la que se
    busca): "r" para apertium-spa-cat (<l>=spa, <r>=cat → cat→spa) y "l"
    para apertium-fra-spa (<l>=fra, <r>=spa → fra→spa). El español (destino)
    es siempre el otro lado.
    """
    root = ET.fromstring(xml_text)
    index: dict[str, list[tuple[str, str]]] = {}
    for e in root.iter("e"):
        p = e.find("p")
        if p is None:
            continue
        left, right = p.find("l"), p.find("r")
        if left is None or right is None:
            continue
        key_el, val_el = (left, right) if src == "l" else (right, left)
        key, es = _side_text(key_el), _side_text(val_el)
        if not key or not es:
            continue
        entry = (es, _first_symbol(val_el))
        bucket = index.setdefault(key.lower(), [])
        if entry not in bucket:
            bucket.append(entry)
    return index


class Dictionary:
    def __init__(self, index: dict[str, list[tuple[str, str]]]):
        self._index = index

    def lookup(self, term: str) -> list[tuple[str, str]]:
        return self._index.get(term.strip().lower(), [])


def load() -> Dictionary:
    """Load from disk cache, downloading the bidix on first use."""
    from . import languages
    prof = languages.profile()
    path = config.MODELS_DIR / prof["bidix_file"]
    if not path.exists():
        if not prof.get("bidix_url"):
            return Dictionary({})
        resp = requests.get(prof["bidix_url"], timeout=60)
        resp.raise_for_status()
        path.write_text(resp.text, encoding="utf-8")
    src = prof.get("bidix_src", "r")
    return Dictionary(parse_bidix(path.read_text(encoding="utf-8"), src=src))
