from app.dictionary import parse_bidix, Dictionary

BIDIX = """<?xml version="1.0"?>
<dictionary>
  <section id="main" type="standard">
    <e><p><l>perro<s n="n"/><s n="m"/></l><r>gos<s n="n"/><s n="m"/></r></p></e>
    <e><p><l>can<s n="n"/><s n="m"/></l><r>gos<s n="n"/><s n="m"/></r></p></e>
    <e><p><l>echar<b/>de<b/>menos<s n="vblex"/></l><r>trobar<b/>a<b/>faltar<s n="vblex"/></r></p></e>
    <e r="LR"><p><l>solo<s n="adj"/></l><r>sol<s n="adj"/></r></p></e>
  </section>
</dictionary>"""


def test_lookup_catalan_to_spanish():
    d = Dictionary(parse_bidix(BIDIX))
    assert d.lookup("gos") == [("perro", "n"), ("can", "n")]
    assert d.lookup("trobar a faltar") == [("echar de menos", "vblex")]
    assert d.lookup("GOS") == [("perro", "n"), ("can", "n")]  # case-insensitive
    assert d.lookup("inexistent") == []
