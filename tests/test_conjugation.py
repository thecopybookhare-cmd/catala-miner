from app import conjugation, forms

# (forma, tag LanguageTool) simuladas para no depender del diccionario real
_ROWS = [
    ("menjo", "VMIP1S0C"), ("menges", "VMIP2S00"), ("menja", "VMIP3S00"),
    ("mengem", "VMIP1P00"), ("mengeu", "VMIP2P00"), ("mengen", "VMIP3P00"),
    ("menge", "VMIP1S0V"),                 # valenciana: pierde frente a 'menjo'
    ("mengi", "VMSP1S0Y"), ("mengis", "VMSP2S0Y"), ("mengi2", "VMSP3S0Y"),
    ("menjar", "VMN00000"), ("menjant", "VMG00000"), ("menjada", "VMP00SF0"),
]


def test_conjugation_parses_and_prefers_central(monkeypatch):
    monkeypatch.setattr(forms, "verb_forms", lambda lemma: _ROWS)
    t = conjugation.table("menjar")
    assert t["nonfinite"]["Infinitiu"] == "menjar"
    assert t["nonfinite"]["Gerundi"] == "menjant"
    assert "Participi" in t["nonfinite"]
    ind = next(m for m in t["moods"] if m["mood"] == "Indicatiu")
    present = next(te for te in ind["tenses"] if te["tense"] == "Present")
    # gana la forma central 'menjo', no la valenciana 'menge'
    assert present["forms"] == ["menjo", "menges", "menja",
                                "mengem", "mengeu", "mengen"]
    assert t["pronouns"][0] == "jo" and t["pronouns"][2] == "ell/ella"


def test_conjugation_empty_without_forms(monkeypatch):
    monkeypatch.setattr(forms, "verb_forms", lambda lemma: [])
    assert conjugation.table("inexistent") == {}
