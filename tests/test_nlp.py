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
