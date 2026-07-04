"""Apertium bidix (spa-cat) as a ca->es sense dictionary.

The bidix is downloaded once from GitHub (config.BIDIX_URL) and parsed as
plain XML — Apertium itself is never installed. <l> = Spanish, <r> = Catalan.
"""
import xml.etree.ElementTree as ET

import requests

from . import config

_BIDIX_PATH = config.MODELS_DIR / "apertium-spa-cat.dix"


def _side_text(el) -> str:
    """Text of <l>/<r>: <b/> is a space; <s n=..> are grammar symbols."""
    parts = [el.text or ""]
    for child in el:
        if child.tag == "b":
            parts.append(" ")
        parts.append(child.tail or "")
    return "".join(parts).strip()


def _first_symbol(el) -> str:
    s = el.find("s")
    return s.get("n", "") if s is not None else ""


def parse_bidix(xml_text: str) -> dict[str, list[tuple[str, str]]]:
    """Return {catalan_lemma_lower: [(spanish, pos), ...]} preserving order."""
    root = ET.fromstring(xml_text)
    index: dict[str, list[tuple[str, str]]] = {}
    for e in root.iter("e"):
        p = e.find("p")
        if p is None:
            continue
        l, r = p.find("l"), p.find("r")
        if l is None or r is None:
            continue
        ca, es = _side_text(r), _side_text(l)
        if not ca or not es:
            continue
        entry = (es, _first_symbol(l))
        bucket = index.setdefault(ca.lower(), [])
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
    if not _BIDIX_PATH.exists():
        resp = requests.get(config.BIDIX_URL, timeout=60)
        resp.raise_for_status()
        _BIDIX_PATH.write_text(resp.text, encoding="utf-8")
    return Dictionary(parse_bidix(_BIDIX_PATH.read_text(encoding="utf-8")))
