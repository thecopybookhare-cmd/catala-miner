from app.translate import detok


def test_detok_joins_sentencepiece_pieces():
    assert detok(["▁Los", "▁per", "ros"]) == "Los perros"
    assert detok([]) == ""
    assert detok(["<unk>", "▁Te", "▁quiero"]) == "Te quiero"
