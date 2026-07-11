def test_userdict_import_lookup_remove(tmp_path, monkeypatch):
    from app import config, userdict
    monkeypatch.setattr(config, "MODELS_DIR", tmp_path)

    from pyglossary.glossary_v2 import Glossary
    Glossary.init()
    g = Glossary()
    g.setInfo("name", "TestDic")
    for w, d in [("gos", "<b>perro</b> domèstic"), ("gat", "gato")]:
        g.addEntry(g.newEntry([w], d))
    src = tmp_path / "src"
    src.mkdir()
    g.write(str(src / "t.ifo"), formatName="Stardict")

    info = userdict.import_file(str(src / "t.ifo"))
    assert info["entries"] == 2 and info["name"] == "TestDic"
    assert userdict.lookup("gos") == [("perro domèstic", "TestDic")]   # HTML fuera
    assert userdict.lookup("nope") == []
    assert [d["name"] for d in userdict.list_dicts()] == ["TestDic"]
    userdict.remove(info["slug"])
    assert userdict.list_dicts() == []
