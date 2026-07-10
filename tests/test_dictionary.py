from app.dictionary import Dictionary, parse_bidix

BIDIX = """<?xml version="1.0"?>
<dictionary>
  <section id="main" type="standard">
    <e><p><l>perro<s n="n"/><s n="m"/></l><r>gos<s n="n"/><s n="m"/></r></p></e>
    <e><p><l>can<s n="n"/><s n="m"/></l><r>gos<s n="n"/><s n="m"/></r></p></e>
    <e><p><l>echar<b/>de<b/>menos<s n="vblex"/></l><r>trobar<b/>a<b/>faltar<s n="vblex"/></r></p></e>
    <e r="LR"><p><l>solo<s n="adj"/></l><r>sol<s n="adj"/></r></p></e>
    <e><p><l>gato<g><b/>montés</g><s n="n"/></l><r>gat<g><b/>salvatge</g><s n="n"/></r></p></e>
    <e><p><l>agua<v n="gen"/><s n="n"/></l><r>aigua<v n="gen"/><s n="n"/></r></p></e>
  </section>
</dictionary>"""


def test_lookup_catalan_to_spanish():
    d = Dictionary(parse_bidix(BIDIX))
    assert d.lookup("gos") == [("perro", "n"), ("can", "n")]
    assert d.lookup("trobar a faltar") == [("echar de menos", "vblex")]
    assert d.lookup("GOS") == [("perro", "n"), ("can", "n")]  # case-insensitive
    assert d.lookup("inexistent") == []


def test_metadix_tags_g_and_v():
    d = Dictionary(parse_bidix(BIDIX))
    assert d.lookup("gat salvatge") == [("gato montés", "n")]
    assert d.lookup("aigua") == [("agua", "n")]
