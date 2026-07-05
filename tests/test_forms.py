import sqlite3

from app import forms

SAMPLE = """ets ser VSIP2S00
gossos gos NCMP000
Barcelona Barcelona NPFSG00
casa casa NCFS000
casa casar VMIP3S0
"""


def _db(tmp_path):
    db = tmp_path / "forms.sqlite"
    forms.build(SAMPLE, db)
    return sqlite3.connect(str(db), check_same_thread=False)


def test_build_and_lookup(tmp_path, monkeypatch):
    con = _db(tmp_path)
    monkeypatch.setattr(forms, "_CON", con)
    monkeypatch.setattr(forms, "_TRIED", True)
    assert forms.lookup("ets") == [("ser", "VERB")]
    assert forms.lookup("Ets") == [("ser", "VERB")]        # cae a minúscula
    assert forms.lookup("gossos") == [("gos", "NOUN")]
    assert ("casa", "NOUN") in forms.lookup("casa")
    assert ("casar", "VERB") in forms.lookup("casa")
    assert forms.lookup("zzz") == []


def test_proper_noun_helpers(tmp_path, monkeypatch):
    con = _db(tmp_path)
    monkeypatch.setattr(forms, "_CON", con)
    monkeypatch.setattr(forms, "_TRIED", True)
    assert forms.known_exact("Barcelona") is True
    assert forms.known_exact("Ets") is False
    assert forms.knows_lower("Ets") is True
    assert forms.knows_lower("Barcelona") is False   # "barcelona" no existe
