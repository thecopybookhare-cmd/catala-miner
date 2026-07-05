"""AnkiConnect client with port auto-discovery.

AnkiConnect defaults to 8765, but another local service may squat that
port (it answers HTTP but not the AnkiConnect JSON shape). We probe the
candidate ports, remember the first real AnkiConnect, and expose a
diagnosis so the UI can tell the user exactly what is wrong.
"""
import base64

import requests

from . import config


class AnkiError(Exception):
    pass


_PORT: int | None = None  # discovered AnkiConnect port


def _url(port: int) -> str:
    return f"http://127.0.0.1:{port}"


def probe(port: int) -> str:
    """Return 'ok' (real AnkiConnect), 'squatted' (other service), 'down'."""
    try:
        r = requests.post(_url(port),
                          json={"action": "version", "version": 6},
                          timeout=3)
        data = r.json()
        if isinstance(data, dict) and "result" in data and "error" in data:
            return "ok"
        return "squatted"
    except Exception:
        return "down"


def find_port(preferred: int | None = None) -> tuple[int | None, dict]:
    """Locate AnkiConnect. Returns (port or None, {port: probe_result})."""
    global _PORT
    if _PORT is not None and probe(_PORT) == "ok":
        return _PORT, {str(_PORT): "ok"}
    ports = [preferred] if preferred else list(config.ANKI_PORTS)
    diag = {}
    for p in ports:
        st = probe(p)
        diag[str(p)] = st
        if st == "ok":
            _PORT = p
            return p, diag
    _PORT = None
    return None, diag


def invoke(action: str, **params):
    port = _PORT or config.ANKI_PORTS[0]
    r = requests.post(_url(port),
                      json={"action": action, "version": 6, "params": params},
                      timeout=10)
    data = r.json()
    if not (isinstance(data, dict) and "result" in data and "error" in data):
        raise AnkiError(f"port {port} is not AnkiConnect")
    if data.get("error"):
        raise AnkiError(data["error"])
    return data.get("result")


def is_up(preferred: int | None = None) -> bool:
    return find_port(preferred)[0] is not None


CARD_CSS = """.card { font-family: -apple-system, sans-serif; font-size: 22px;
text-align: center; color: #222; background: #fdfdfd; }
.front { font-size: 34px; font-weight: 700; }
.frase { margin-top: 12px; } .es { color: #666; font-size: 18px; }
.font { color: #999; font-size: 13px; margin-top: 10px; }
img { max-width: 90%; border-radius: 8px; margin-top: 10px; }"""

FRONT = '<div class="front">{{Paraula}}</div>'
BACK = """{{FrontSide}}<hr id=answer>
<div class="es">{{ParaulaES}}</div>
<div class="frase">{{Frase}}</div>
<div class="es">{{FraseES}}</div>
{{Imatge}}<br>{{Audio}}
<div class="font">{{Font}} · {{Freq}}</div>"""


def ensure_note_type():
    if config.NOTE_TYPE in invoke("modelNames"):
        return
    invoke("createModel", modelName=config.NOTE_TYPE,
           inOrderFields=config.NOTE_FIELDS, css=CARD_CSS,
           cardTemplates=[{"Name": "Card 1", "Front": FRONT, "Back": BACK}])


def build_note(card: dict, deck: str) -> dict:
    return {
        "deckName": deck,
        "modelName": config.NOTE_TYPE,
        "fields": {
            "Paraula": card["paraula"] or "",
            "ParaulaES": card["paraula_es"] or "",
            "Frase": card["frase"] or "",
            "FraseES": card["frase_es"] or "",
            "Audio": f"[sound:{card['audio_file']}]" if card.get("audio_file") else "",
            "Imatge": f'<img src="{card["image_file"]}">' if card.get("image_file") else "",
            "Font": card.get("font") or "",
            "Freq": card.get("freq_rank") or "",
        },
        "options": {"allowDuplicate": False},
        "tags": ["catala-miner"],
    }


def send_card(card: dict, deck: str) -> int:
    """Upload media + note. Raises AnkiError/requests errors if Anki is down."""
    ensure_note_type()
    if deck not in invoke("deckNames"):
        invoke("createDeck", deck=deck)
    for key in ("audio_file", "image_file"):
        name = card.get(key)
        if name:
            path = config.MEDIA_DIR / name
            if path.exists():
                invoke("storeMediaFile", filename=name,
                       data=base64.b64encode(path.read_bytes()).decode())
    return invoke("addNote", note=build_note(card, deck))
