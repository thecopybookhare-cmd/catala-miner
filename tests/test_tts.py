from app import piper_tts, tts


def test_piper_available_by_profile():
    assert piper_tts.available("ca") is True
    assert piper_tts.available("fr") is True
    assert piper_tts.available("zz") is False      # idioma sin voz configurada


def test_tts_speak_empty_text():
    assert tts.speak("") == ""


def test_tts_prefers_piper_over_espeak(monkeypatch):
    monkeypatch.setattr(piper_tts, "speak", lambda t: "piper-x.wav")
    assert tts.speak("hola") == "piper-x.wav"       # gana la voz neural


def test_tts_falls_back_when_no_piper(monkeypatch):
    monkeypatch.setattr(piper_tts, "speak", lambda t: "")
    monkeypatch.setattr(tts.shutil, "which", lambda _e: None)   # sin espeak
    assert tts.speak("hola") == ""
