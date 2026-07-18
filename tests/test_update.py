"""Actualizador: check/apply sobre el checkout (git mockeado)."""
import subprocess
from unittest.mock import patch

from fastapi.testclient import TestClient

import app.main as main
from app import update


def client(tmp_path):
    main.CON = main.db.connect(tmp_path / "t.db")
    return TestClient(main.app)


def _cp(stdout="", returncode=0, stderr=""):
    return subprocess.CompletedProcess([], returncode, stdout=stdout, stderr=stderr)


def test_check_reports_behind(tmp_path):
    c = client(tmp_path)
    outs = {"fetch": _cp(), "rev-list": _cp("3\n"), "rev-parse": _cp("abc1234\n"),
            "log": _cp("fix: algo\n")}
    with patch.object(update, "_git", side_effect=lambda *a, **k: outs[a[0]]):
        r = c.get("/api/update/check").json()
    assert r == {"git": True, "current": "abc1234", "behind": 3, "latest": "fix: algo"}


def test_check_without_git_checkout(tmp_path):
    c = client(tmp_path)
    with patch.object(update, "is_git_checkout", return_value=False):
        assert c.get("/api/update/check").json() == {"git": False}


def test_apply_pull_and_deps_hint(tmp_path):
    c = client(tmp_path)
    outs = {"diff": _cp("pyproject.toml\napp/main.py\n"), "pull": _cp("ok"),
            "rev-parse": _cp("def5678\n")}
    with patch.object(update, "_git", side_effect=lambda *a, **k: outs[a[0]]):
        r = c.post("/api/update/apply").json()
    assert r["ok"] and r["deps_changed"] and r["current"] == "def5678"
    assert r["installer"] in ("./install.sh", "install.ps1")


def test_apply_surfaces_pull_error(tmp_path):
    c = client(tmp_path)
    outs = {"diff": _cp(""),
            "pull": _cp("", returncode=1, stderr="error: local changes")}
    with patch.object(update, "_git", side_effect=lambda *a, **k: outs[a[0]]):
        r = c.post("/api/update/apply").json()
    assert "error" in r and "local changes" in r["error"]
