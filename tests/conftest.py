import pytest


@pytest.fixture(autouse=True)
def no_forms_download(monkeypatch):
    """Los tests nunca descargan el diccionario de formas real."""
    from app import forms
    if not forms._DB_PATH.exists():
        monkeypatch.setattr(forms, "_TRIED", True)
