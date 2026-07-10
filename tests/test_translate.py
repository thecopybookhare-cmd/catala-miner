from app.translate import _find_sp, detok


def test_detok_joins_sentencepiece_pieces():
    assert detok(["▁Los", "▁per", "ros"]) == "Los perros"
    assert detok([]) == ""
    assert detok(["<unk>", "▁Te", "▁quiero"]) == "Te quiero"


def test_find_sp_prefers_source_spm(tmp_path):
    # OPUS-MT trae source.spm + target.spm: se codifica con el de origen
    (tmp_path / "source.spm").write_bytes(b"")
    (tmp_path / "target.spm").write_bytes(b"")
    assert _find_sp(tmp_path).name == "source.spm"


def test_find_sp_falls_back_to_shared_model(tmp_path):
    # Softcatalà trae un único sp_m.model compartido
    (tmp_path / "sp_m.model").write_bytes(b"")
    assert _find_sp(tmp_path).name == "sp_m.model"


FAKE = {"Ets molt intel·ligent, tu.": "Ets muy inteligente, tú.",
        "ets molt intel·ligent, tu.": "eres muy inteligente, tú.",
        "Barcelona és gran.": "Barcelona es grande.",
        "barcelona és gran.": "barcelona es grande."}


def _fake_translate(text):
    return FAKE.get(text, "X:" + text)


def test_sentence_decapitalizes_untranslated_leading_verb(monkeypatch):
    from app import forms, translate
    monkeypatch.setattr(translate, "translate", _fake_translate)
    monkeypatch.setattr(forms, "known_exact", lambda w: w == "Barcelona")
    monkeypatch.setattr(forms, "knows_lower", lambda w: w.lower() == "ets")
    assert translate.sentence("Ets molt intel·ligent, tu.") == \
        "Eres muy inteligente, tú."


def test_sentence_keeps_proper_nouns(monkeypatch):
    from app import forms, translate
    monkeypatch.setattr(translate, "translate", _fake_translate)
    monkeypatch.setattr(forms, "known_exact", lambda w: w == "Barcelona")
    monkeypatch.setattr(forms, "knows_lower", lambda w: False)
    assert translate.sentence("Barcelona és gran.") == "Barcelona es grande."
