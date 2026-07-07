import pytest


@pytest.fixture(autouse=True)
def no_forms_download(monkeypatch):
    """Neutraliza el diccionario de formas por defecto: sin acceso a disco ni
    descarga. Los tests que lo necesiten sobrescriben _CON/_TRIED o mockean
    forms.lookup/known_exact/knows_lower explícitamente."""
    from app import forms
    monkeypatch.setattr(forms, "_CON", None)
    monkeypatch.setattr(forms, "_TRIED", True)


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch, tmp_path):
    """Los tests nunca leen/escriben el settings.json real del usuario."""
    import app.main as main
    monkeypatch.setattr(main, "SETTINGS_PATH", tmp_path / "settings.json")
