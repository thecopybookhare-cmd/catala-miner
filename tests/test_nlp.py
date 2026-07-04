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
