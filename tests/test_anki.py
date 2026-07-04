from unittest.mock import patch, MagicMock
from app import anki


def _resp(result=None, error=None):
    m = MagicMock()
    m.json.return_value = {"result": result, "error": error}
    return m


def test_note_payload():
    card = {"paraula": "gos", "paraula_es": "perro", "frase": "El gos",
            "frase_es": "El perro", "audio_file": "a.mp3",
            "image_file": "i.jpg", "font": "V @ 0:01", "freq_rank": "common"}
    note = anki.build_note(card, deck="Català")
    assert note["deckName"] == "Català"
    assert note["modelName"] == "CatalaMiner"
    assert note["fields"]["Audio"] == "[sound:a.mp3]"
    assert note["fields"]["Imatge"] == '<img src="i.jpg">'
    assert note["options"]["allowDuplicate"] is False


@patch("app.anki.requests.post")
def test_invoke_ok_and_error(post):
    post.return_value = _resp(result=["Default"])
    assert anki.invoke("deckNames") == ["Default"]
    post.return_value = _resp(error="boom")
    try:
        anki.invoke("deckNames")
        assert False
    except anki.AnkiError:
        pass


@patch("app.anki.requests.post")
def test_is_up_false_when_down(post):
    post.side_effect = ConnectionError()
    assert anki.is_up() is False


@patch("app.anki.requests.post")
def test_is_up_false_when_port_squatted(post):
    m = MagicMock()
    m.json.return_value = {"detail": "invalid bearer token"}
    post.return_value = m
    assert anki.is_up() is False
