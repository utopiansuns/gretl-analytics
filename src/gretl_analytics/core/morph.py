"""Склонение русских названий переменных («цена» → «цены», «цену», «ценой»).

Использует морфологический словарь pymorphy3. Если пакет не установлен, названия
остаются в той форме, в которой их ввёл пользователь (именительный падеж).

Склоняется именная группа до первого существительного: согласованные с ним
прилагательные и само существительное. Остальное (зависимые слова в родительном
падеже, предлоги, латиница, скобки) не меняется: «цена продажи» → «цены продажи»,
«жилая площадь дома» → «жилой площади дома».
"""
import functools
import re

CASES = {"nom": "nomn", "gen": "gent", "dat": "datv", "acc": "accs", "ins": "ablt", "loc": "loct"}
_WORD = re.compile(r"[А-Яа-яЁё]+(?:-[А-Яа-яЁё]+)*")
_STOP = {"в", "во", "на", "по", "с", "со", "из", "от", "до", "для", "при", "о", "об", "за", "к", "у", "и", "или", "без"}


@functools.lru_cache(maxsize=1)
def _analyzer():
    try:
        import pymorphy3
        try:
            import pymorphy3_dicts_ru       # явный путь к словарю: нужен в собранном приложении
            return pymorphy3.MorphAnalyzer(path=pymorphy3_dicts_ru.get_path())
        except Exception:  # noqa: BLE001
            return pymorphy3.MorphAnalyzer()
    except Exception:  # noqa: BLE001 – нет пакета или словаря
        return None


def available():
    return _analyzer() is not None


def _nom_parse(word, pos):
    """Разбор слова в именительном падеже с нужной частью речи (или None)."""
    for p in _analyzer().parse(word):
        if p.tag.POS in pos and "nomn" in p.tag:
            return p
    return None


def _match_case(src, dst):
    if src.isupper() and len(src) > 1:
        return dst.upper()
    if src[:1].isupper():
        return dst[:1].upper() + dst[1:]
    return dst


@functools.lru_cache(maxsize=2048)
def _plan(phrase):
    """Слова, которые нужно склонять: [(start, end, parse)], и разбор главного слова."""
    if not available():
        return (), None
    plan = []
    for m in _WORD.finditer(phrase):
        w = m.group(0)
        if w.lower() in _STOP:
            break
        noun = _nom_parse(w.lower(), {"NOUN"})
        adj = _nom_parse(w.lower(), {"ADJF", "PRTF"})
        if adj and not noun:
            plan.append((m.start(), m.end(), adj))
            continue
        if noun:
            plan.append((m.start(), m.end(), noun))
            return tuple(plan), noun
        break
    return (), None


def inflect(phrase, case):
    """Название в нужном падеже: case – nom, gen, dat, acc, ins или loc."""
    if not phrase or case == "nom":
        return phrase
    plan, head = _plan(phrase)
    if not head:
        return phrase
    gram = {CASES[case]}
    number = "plur" if "plur" in head.tag else "sing"
    out, pos = [], 0
    for a, b, p in plan:
        tags = set(gram)
        if p is not head:
            tags.add(number)
            if number == "sing" and head.tag.gender:
                tags.add(head.tag.gender)
            if case == "acc" and head.tag.animacy:
                tags.add(head.tag.animacy)
        f = p.inflect(tags)
        out.append(phrase[pos:a])
        out.append(_match_case(phrase[a:b], f.word) if f else phrase[a:b])
        pos = b
    out.append(phrase[pos:])
    return "".join(out)


def forms(phrase):
    return {c: inflect(phrase, c) for c in CASES}


def gender(phrase):
    """masc / femn / neut / plur – для согласования («связан», «связана», «связаны»)."""
    _, head = _plan(phrase)
    if not head:
        return None
    if "plur" in head.tag:
        return "plur"
    return head.tag.gender


def agree(phrase, masc, femn, neut, plur):
    """Слово, согласованное по роду с названием: agree("цена", "связан", "связана", "связано", "связаны")."""
    return {"masc": masc, "femn": femn, "neut": neut, "plur": plur}.get(gender(phrase), masc)
