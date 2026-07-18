from app import nlp


def test_freq_badge_thresholds():
    assert nlp.freq_badge(5.6) == "common"
    assert nlp.freq_badge(4.0) == "medium"
    assert nlp.freq_badge(2.0) == "rare"
    assert nlp.freq_badge(0.0) == "rare"


def test_naive_tokenize_keeps_catalan_clitics():
    toks = nlp.naive_tokenize("N'hi ha molts, oi?")
    words = [t["t"] for t in toks if t["is_word"]]
    assert "N'hi" in words and "ha" in words and "molts" in words
    # punctuation preserved as non-word tokens
    assert any(t["t"] == "," and not t["is_word"] for t in toks)


def test_wordlike_excludes_numbers_and_sub_artifacts():
    # engendros reales de subs automáticos de YouTube que salían en el panel
    for junk in ("què?-no", "tant.-i", "no?-m'", "3", "18", "gai?-home"):
        assert not nlp.is_wordlike(junk), junk
    # palabras legítimas con apóstrofo/guion/punt volat/elisión
    for ok in ("n'hi", "anem-hi", "l·l", "peut-être", "l'", "'s", "casa"):
        assert nlp.is_wordlike(ok), ok
    toks = nlp.naive_tokenize("Té 18 anys, oi?")
    by_text = {t["t"]: t["is_word"] for t in toks}
    assert by_text["18"] is False and by_text["anys"] is True


def test_naive_tokenize_ws_reconstructs_text():
    # «ws» permite al frontend reconstruir el espaciado original exacto
    text = "Aquesta campanya, oi? No."
    toks = nlp.naive_tokenize(text)
    assert all("ws" in t for t in toks)
    rebuilt = "".join(t["t"] + t["ws"] for t in toks).strip()
    assert rebuilt == text
    # sin espacio antes de la coma; con espacio después
    coma = next(t for t in toks if t["t"] == ",")
    assert coma["ws"] == " "
    campanya = next(t for t in toks if t["t"] == "campanya")
    assert campanya["ws"] == ""


def test_correct_lemma_overrides_spacy(monkeypatch):
    from app import forms
    monkeypatch.setattr(forms, "lookup",
                        lambda f: [("ser", "VERB")] if f.lower() == "ets" else [])
    # spaCy se equivocó ("et" NOUN) y el dicc. de formas no lo avala -> corrige
    assert nlp._correct("Ets", "et", "NOUN") == ("ser", "VERB")
    # spaCy coincide con un candidato -> se respeta su desambiguación
    monkeypatch.setattr(forms, "lookup",
                        lambda f: [("casa", "NOUN"), ("casar", "VERB")])
    assert nlp._correct("casa", "casar", "VERB") == ("casar", "VERB")
    # sin entrada en el diccionario -> spaCy tal cual
    monkeypatch.setattr(forms, "lookup", lambda f: [])
    assert nlp._correct("blau", "blau", "ADJ") == ("blau", "ADJ")


def test_correct_pos_match_wins(monkeypatch):
    from app import forms
    monkeypatch.setattr(forms, "lookup",
                        lambda f: [("casa", "NOUN"), ("casar", "VERB")])
    # spaCy dice VERB con lema desconocido -> gana el candidato VERB
    assert nlp._correct("casa", "cassar", "VERB") == ("casar", "VERB")
    # AUX cuenta como VERB
    monkeypatch.setattr(forms, "lookup", lambda f: [("ser", "VERB")])
    assert nlp._correct("ets", "et", "AUX") == ("ser", "AUX")
