"""Rangos de frecuencia del corpus (wordfreq) lematizados, y marcado en
masa de vocabulario conocido (estilo Language Reactor)."""

_RANKS = None
_N = 5000


def ranks(n: int = _N) -> dict[str, int]:
    """{lema: rango} para las n palabras más frecuentes del catalán.
    Las formas se lematizan con el diccionario de formas; la primera
    aparición (rango más alto) gana."""
    global _RANKS
    if _RANKS is None:
        from wordfreq import top_n_list
        from . import forms
        out: dict[str, int] = {}
        for i, w in enumerate(top_n_list("ca", n), start=1):
            cands = forms.lookup(w)
            lemma = (cands[0][0] if cands else w).lower()
            out.setdefault(lemma, i)
        _RANKS = out
    return _RANKS


def bulk_known(con, top_n: int) -> int:
    """Marca como 'known' los lemas de rango <= top_n que aún no tienen
    estado (nunca pisa learning/ignored/tracking)."""
    from . import db
    current = db.word_statuses(con)
    marked = 0
    for lemma, rank in ranks().items():
        if rank <= top_n and lemma not in current:
            db.set_word_status(con, lemma, "known")
            marked += 1
    return marked
