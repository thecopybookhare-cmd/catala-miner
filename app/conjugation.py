"""Tabla de conjugación de un verbo, derivada del diccionario de formas de
Softcatalà/LanguageTool (offline, sin dependencias). Interpreta el tag
morfológico VM<mode><tiempo><persona><número>… del catalán.

Posiciones del tag (p.ej. VMIP3S00):
  [2] modo:    I indicatiu · S subjuntiu · M imperatiu · N infinitiu ·
               G gerundi · P participi
  [3] tiempo:  P present · I imperfet · F futur · S passat simple · C condicional
  [4] persona: 1 · 2 · 3
  [5] número:  S singular · P plural
  [-1] variante dialectal: 0 común a todos · C central (estándar) ·
       V valenciana · B balear · dígito = forma alternativa
"""
from . import forms

_MOOD = {"I": "Indicatiu", "S": "Subjuntiu", "M": "Imperatiu"}
_TENSE = {"P": "Present", "I": "Imperfet", "F": "Futur",
          "S": "Passat simple", "C": "Condicional"}
# orden de presentación
_MOOD_ORDER = ["Indicatiu", "Subjuntiu", "Imperatiu"]
_TENSE_ORDER = ["Present", "Imperfet", "Passat simple", "Futur", "Condicional"]
_PERSONS = ["1S", "2S", "3S", "1P", "2P", "3P"]
_PRONOUN = {"1S": "jo", "2S": "tu", "3S": "ell/ella",
            "1P": "nosaltres", "2P": "vosaltres", "3P": "ells/elles"}


def _variant_rank(tag: str) -> int:
    """Descarta las formas valencianas (V) y baleares (B) para quedarnos con la
    normativa central/común (0, C, Y…). Entre las restantes, gana la primera."""
    return 1 if tag and tag[-1] in ("V", "B") else 0


def table(lemma: str) -> dict:
    """{lemma, nonfinite:{...}, moods:[{mood, tenses:[{tense, forms:[6]}]}]}
    o {} si el lema no es un verbo con formas conocidas."""
    rows = forms.verb_forms(lemma)
    if not rows:
        return {}

    nonfinite: dict[str, str] = {}
    # cells[(modo, tiempo)][persona] = (form, variant_rank)
    cells: dict[tuple[str, str], dict[str, tuple[str, int]]] = {}

    for form, tag in rows:
        if len(tag) < 6:
            continue
        mood_c, tense_c, person_c, number_c = tag[2], tag[3], tag[4], tag[5]
        if mood_c == "N":
            nonfinite.setdefault("Infinitiu", form)
            continue
        if mood_c == "G":
            nonfinite.setdefault("Gerundi", form)
            continue
        if mood_c == "P":                       # participi (varios géneros/números)
            nonfinite.setdefault("Participi", form)
            continue
        mood = _MOOD.get(mood_c)
        if not mood:
            continue
        # imperativo no tiene distinción de tiempo; lo tratamos como "Present"
        tense = _TENSE.get(tense_c, "Present") if mood != "Imperatiu" else "Imperatiu"
        person = person_c + number_c
        if person not in _PERSONS:
            continue
        key = (mood, tense)
        rank = _variant_rank(tag)
        cur = cells.setdefault(key, {}).get(person)
        if cur is None or rank < cur[1]:        # preferir variante estándar
            cells[key][person] = (form, rank)

    moods = []
    for mood in _MOOD_ORDER:
        tenses = []
        order = ["Imperatiu"] if mood == "Imperatiu" else _TENSE_ORDER
        for tense in order:
            cell = cells.get((mood, tense))
            if not cell:
                continue
            forms6 = [cell.get(p, ("", 0))[0] for p in _PERSONS]
            if any(forms6):
                tenses.append({"tense": tense, "forms": forms6})
        if tenses:
            moods.append({"mood": mood, "tenses": tenses})

    if not moods and not nonfinite:
        return {}
    return {
        "lemma": lemma,
        "pronouns": [_PRONOUN[p] for p in _PERSONS],
        "nonfinite": nonfinite,
        "moods": moods,
    }
