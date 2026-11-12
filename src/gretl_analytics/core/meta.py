"""Метаданные переменных: русские названия, единицы измерения, тип переменной.

Названия и единицы берутся из описаний переменных (строки «price = Sale price in thousands
of dollars») или из словаря, который пользователь заполняет в приложении. Если единица неизвестна, помощник пишет
«ед. изм. переменной X», а не придумывает её.
"""
import functools
import os
import re
from collections import Counter

from . import morph

# (шаблон описания, именительный, родительный)
NAME_DICT = [
    (r"sale ?price|selling price", "цена продажи", "цены продажи"),
    (r"\bprice", "цена", "цены"),
    (r"living are(a)?|square feet of living|living space", "жилая площадь", "жилой площади"),
    (r"bed ?rooms", "число спален", "числа спален"),
    (r"bath(room)?s", "число ванных комнат", "числа ванных комнат"),
    (r"swimming pool|\bpool\b", "наличие бассейна", "наличия бассейна"),
    (r"family room", "наличие семейной комнаты", "наличия семейной комнаты"),
    (r"fireplace", "наличие камина", "наличия камина"),
    (r"car spaces|garage", "число машиномест в гараже", "числа машиномест в гараже"),
    (r"age of (the )?house", "возраст дома", "возраста дома"),
    (r"income tax|\btax", "налог", "налога"),
    (r"gross income|\bincome", "доход", "дохода"),
    (r"population", "численность населения", "численности населения"),
    (r"airline passengers|passengers", "число авиапассажиров", "числа авиапассажиров"),
    (r"natural logarithm|\blog\b", "логарифм", "логарифма"),
    (r"time trend", "временной тренд", "временного тренда"),
    (r"unemployment rate", "уровень безработицы", "уровня безработицы"),
    (r"inflation", "инфляция", "инфляции"),
    (r"consumption", "потребление", "потребления"),
    (r"wage|earnings", "заработная плата", "заработной платы"),
    (r"interest rate", "процентная ставка", "процентной ставки"),
    (r"\bgdp\b|gross domestic product", "ВВП", "ВВП"),
    (r"\bsales\b", "объём продаж", "объёма продаж"),
    (r"\byear\b", "год", "года"),
]

# (шаблон, сокращение единицы, форма «на 1 …»)
UNIT_DICT = [
    (r"\(\$000s|\$000|thousands? of (current |constant )?dollars|\$ ?thousands|in \$1,?000", "тыс. долл.", "1 тыс. долл."),
    (r"billions? of (current |constant )?dollars|\$ ?billions?", "млрд долл.", "1 млрд долл."),
    (r"millions? of (current |constant )?dollars|\$ ?millions?", "млн долл.", "1 млн долл."),
    (r"square feet|sq\.? ?ft", "кв. футов", "1 кв. фут"),
    (r"square met(er|re)s|sq\.? ?m\b", "кв. м", "1 кв. м"),
    (r"\bin percent|percentage|\(%\)|\bpercent\b", "п.п.", "1 п.п."),
    (r"in years|age .* in years|\byears\b", "лет", "1 год"),
    (r"in millions", "млн", "1 млн"),
    (r"in thousands", "тыс.", "1 тыс."),
    (r"in dollars|\bdollars\b", "долл.", "1 долл."),
    (r"number of", "ед.", "1 ед."),
]

# Подсказки по самому имени переменной, когда описания данных нет: (шаблон имени, название, единица).
# Единица указывается, только если она следует из смысла (число, годы, 0/1, площадь в sqft);
# денежные единицы не угадываются: валюта и масштаб зависят от данных.
VAR_NAMES = [
    (r"sale_?pric?e?|saleprice", "цена продажи", ""),
    (r"price|pr|cena|tsena", "цена", ""),
    (r"sqft|sq_?feet", "жилая площадь", "кв. футов"),
    (r"area|livarea|square", "площадь", ""),
    (r"bedrms|bedrooms?|beds", "число спален", "ед."),
    (r"baths|bathrooms?|bathrms", "число ванных комнат", "ед."),
    (r"garage", "число машиномест в гараже", "ед."),
    (r"rooms?", "число комнат", "ед."),
    (r"age", "возраст", "лет"),
    (r"pool", "наличие бассейна", "0/1"),
    (r"famroom", "наличие семейной комнаты", "0/1"),
    (r"firepl(ace)?", "наличие камина", "0/1"),
    (r"female|fem", "женский пол", "0/1"),
    (r"male", "мужской пол", "0/1"),
    (r"married", "состояние в браке", "0/1"),
    (r"urban", "проживание в городе", "0/1"),
    (r"tax(es)?", "налог", ""),
    (r"income|inc|dohod", "доход", ""),
    (r"wages?|salary|zp", "заработная плата", ""),
    (r"educ|edu|school", "число лет обучения", "лет"),
    (r"exper|experience", "опыт работы", "лет"),
    (r"tenure", "стаж на текущем месте работы", "лет"),
    (r"hours|hrs", "число часов работы", "ч"),
    (r"pop|population", "численность населения", ""),
    (r"gdp|vvp", "ВВП", ""),
    (r"cons|consumption", "потребление", ""),
    (r"inv|invest(ment)?s?", "инвестиции", ""),
    (r"exports?", "экспорт", ""),
    (r"imports?", "импорт", ""),
    (r"unemp|unrate|unemployment", "уровень безработицы", "%"),
    (r"infl?|inflation|cpi_?infl", "инфляция", "%"),
    (r"cpi", "индекс потребительских цен", ""),
    (r"rate|interest|irate", "процентная ставка", "%"),
    (r"m[12]|money", "денежная масса", ""),
    (r"sales", "объём продаж", ""),
    (r"costs?", "издержки", ""),
    (r"profits?", "прибыль", ""),
    (r"q|qty|quantity", "количество", ""),
    (r"emp|employment|employees", "численность занятых", ""),
    (r"gpa", "средний балл", ""),
    (r"grade", "оценка", ""),
    (r"year|god", "год", ""),
    (r"passengers|pass", "число авиапассажиров", ""),
]


SAFE_UNITS = {"0/1", "%", "лет", "ед.", "чел.", "кв. футов", "мес.", "ч", "дней"}   # не зависят от данных
_PREFIXES = (("ld_", "темп прироста", False), ("l_", "логарифм", False), ("ln_", "логарифм", False),
             ("log_", "логарифм", False), ("d_", "изменение", True), ("sq_", "квадрат", False))


@functools.lru_cache(maxsize=1)
def gretl_vars():
    """Словарь переменных учебных наборов Gretl (gretl_vars.tsv): имя → [(название, единица, наборы)]."""
    table = {}
    with open(os.path.join(os.path.dirname(__file__), "gretl_vars.tsv"), encoding="utf-8") as f:
        for line in f:
            if line.strip() and not line.startswith("#"):
                name, ru, unit, ds = line.rstrip("\n").split("\t")
                table.setdefault(name, []).append((ru, unit, frozenset(ds.split(","))))
    return table


def base_name(name):
    """Исходная переменная для производных имён Gretl: l_price → price, sqft_1 → sqft."""
    for prefix, _, _ in _PREFIXES:
        if name.lower().startswith(prefix) and len(name) > len(prefix):
            return base_name(name[len(prefix):])
    m = re.match(r"^(.+?)_\d+$", name)
    return base_name(m.group(1)) if m else name


def guess_known(names):
    """{имя: (название, единица)} по словарю наборов Gretl.

    Одно имя в разных наборах значит разное (C – потребление или издержки), поэтому выбирается
    набор, в котором есть больше всего переменных из текста. Если такого набора нет (своё исследование),
    название берётся, только когда оно однозначно, а единица – только если она не зависит от данных."""
    table = gretl_vars()
    rows_of = {n: table.get(n) or table.get(next((k for k in table if k.lower() == n.lower()), ""), []) for n in names}
    score = Counter(d for rows in rows_of.values() for d in set().union(*(r[2] for r in rows)) if rows)
    out = {}
    for n, rows in rows_of.items():
        if not rows:
            continue
        best = max(rows, key=lambda r: (max(score[d] for d in r[2]), len(r[2])))
        if max(score[d] for d in best[2]) >= 2:
            out[n] = best[:2]
        elif len({r[0] for r in rows}) == 1:
            units = {r[1] for r in rows}
            out[n] = (best[0], best[1] if len(units) == 1 and best[1] in SAFE_UNITS else "")
    return out


def guess_by_name(name, known=None):
    """(название, единица) по имени переменной Gretl или None.

    known – подсказки guess_known() для текущего текста. Понимает производные имена Gretl:
    l_x (логарифм), d_x (изменение), ld_x (темп прироста), sq_x (квадрат), x_1 (лаг)."""
    known = known if known is not None else guess_known([base_name(name)])
    if name in known:
        return known[name]
    n = name.lower()
    for prefix, word, keep_unit in _PREFIXES:
        if n.startswith(prefix) and len(n) > len(prefix):
            base = guess_by_name(name[len(prefix):], known)
            if not base or base[1] == "0/1":
                return None
            unit = ("п.п." if base[1] == "%" else base[1]) if keep_unit else ""   # изменение доли: в п.п.
            return f"{word} {morph.inflect(base[0], 'gen')}", unit
    m = re.match(r"^(.+?)_(\d+)$", n)
    if m:
        base = guess_by_name(name[:len(m.group(1))], known)
        return (f"{base[0]} с лагом {m.group(2)}", base[1]) if base else None
    for pat, nom, unit in VAR_NAMES:
        if re.fullmatch(pat, n):
            return nom, unit
    return None


MONTHS_GEN = ["январе", "феврале", "марте", "апреле", "мае", "июне", "июле", "августе", "сентябре",
              "октябре", "ноябре", "декабре"]
MONTHS_NOM = ["январь", "февраль", "март", "апрель", "май", "июнь", "июль", "август", "сентябрь",
              "октябрь", "ноябрь", "декабрь"]
MONTHS_CMP = ["январём", "февралём", "мартом", "апрелем", "маем", "июнем", "июлем", "августом",
              "сентябрём", "октябрём", "ноябрём", "декабрём"]


def _single_noun(phrase):
    words = phrase.split()
    return len(words) == 1 and not phrase.lower().startswith("налич")


class VarMeta:
    def __init__(self, name, label="", override=None):
        self.name = name
        self.label = label or ""
        o = override or {}
        self.kind = "level"
        self.base = None        # исходная переменная (для log/sq/lag)
        self.period = None      # номер периода для сезонной фиктивной
        self.lag = None
        self._detect()
        if o.get("kind"):
            self.kind = o["kind"]
        nom, gen = self._names()
        name = (o.get("name") or "").strip()
        if name and self.kind == "dummy" and _single_noun(name):
            name = "наличие " + morph.inflect(name, "gen")      # «бассейн» → «наличие бассейна»
        self.nom = name or nom
        self.gen = o.get("name_gen") or (morph.inflect(name, "gen") if name else gen)
        self.unit, self.one = self._unit()
        if o.get("unit"):
            self.unit = o["unit"]
            known = {u: one for _, u, one in UNIT_DICT}
            known.update({"кв. фута": "1 кв. фут", "кв. футы": "1 кв. фут", "кв. м.": "1 кв. м", "года": "1 год",
                          "чел.": "1 чел.", "тыс. чел.": "1 тыс. чел.", "руб.": "1 руб.", "тыс. руб.": "1 тыс. руб.",
                          "млн руб.": "1 млн руб.", "%": "1 п.п.", "шт.": "1 шт."})
            self.one = o.get("unit_one") or known.get(o["unit"].strip(), "1 " + o["unit"])

    # --- определение типа
    def _detect(self):
        n, lab = self.name, self.label.lower()
        if n == "const":
            self.kind = "const"
            return
        m = re.match(r"^d([mq])(\d+)$", n)
        m2 = re.search(r"= ?1 if (?:period|month|quarter) is (\d+)", lab)
        if m or m2:
            self.kind = "season"
            self.period = int(m.group(2) if m else m2.group(1))
            return
        if n in ("time", "t", "trend", "year", "god", "tt") or "time trend" in lab:
            self.kind = "trend"
            return
        m = re.match(r"^sq_(\w+)$", n) or re.search(r"= ?(\w+) squared", lab)
        if m:
            self.kind, self.base = "square", m.group(1)
            return
        m = re.match(r"^(\w+)_(\d+)$", n)
        m3 = re.search(r"= ?(\w+)\(-(\d+)\)", lab)
        if m3 or (m and not n.startswith(("l_", "ld_", "d_", "sd_"))):
            mm = m3 or m
            self.kind, self.base, self.lag = "lag", mm.group(1), int(mm.group(2))
            return
        if re.match(r"^(l_|ln_?|log_?|lg_?)\w*", n) and n not in ("l", "ln", "log") or re.search(r"natural log|= ?log of|^log of|logarithm", lab):
            self.kind = "log"
            mm = re.match(r"^(?:l_|ln_?|log_?)(\w+)", n)
            self.base = mm.group(1) if mm else None
            return
        if re.match(r"^(d_|ld_)\w+", n) or "first difference" in lab:
            self.kind = "diff"
            return
        if re.search(r"\b1 (if|for)\b.*\b0\b|\(1\).*\(0\)|indicator|dummy", lab):
            self.kind = "dummy"

    def _names(self):
        lab = self.label.lower()
        if self.kind == "season" and self.period:
            return f"фиктивная переменная периода {self.period}", f"фиктивной переменной периода {self.period}"
        if self.kind == "trend":
            return "временной тренд", "временного тренда"
        if self.kind == "dummy":
            m = re.match(r"1 if (?:the )?(.*?)(?:,| and)? 0 (?:otherwise|if.*)", lab)
            if m:
                for pat, nom, gen in NAME_DICT:
                    if re.search(pat, m.group(1)):
                        return nom, gen
        for pat, nom, gen in NAME_DICT:
            if re.search(pat, lab):
                if self.kind == "log" and "логарифм" not in nom:
                    return f"логарифм показателя «{nom}»", f"логарифма показателя «{nom}»"
                return nom, gen
        return self.name, self.name

    def _unit(self):
        if self.kind in ("dummy", "season", "const"):
            return None, None
        if self.kind == "trend":
            return "периодов", "1 период"
        if self.kind == "log":
            return None, None
        lab = self.label.lower()
        for pat, unit, one in UNIT_DICT:
            if re.search(pat, lab):
                return unit, one
        return None, None

    # подписи для текста
    def case(self, c):
        """Название в падеже c (nom, gen, dat, acc, ins, loc)."""
        if self.nom == self.name:
            return self.name
        if c == "gen":
            return self.gen
        return morph.inflect(self.nom, c)

    def agree(self, masc, femn, neut, plur):
        return morph.agree(self.nom, masc, femn, neut, plur) if self.nom != self.name else masc

    def ref(self):
        """«жилая площадь (sqft)» – для первого упоминания."""
        return f"{self.nom} ({self.name})" if self.nom != self.name else self.name

    def unit_or(self):
        return self.unit if self.unit else f"ед. изм. {self.name}"

    def one_or(self):
        return self.one if self.one else "единицу"



class Facts:
    """Реестр всех чисел, попавших в текст. Нужен для самопроверки «нет выдуманных чисел»."""

    def __init__(self):
        self.strings = set()

    def add(self, s):
        self.strings.add(s)
        return s


def verify_numbers(text, facts):
    """Возвращает числа из текста, которых нет в реестре фактов."""
    allowed = {"0", "1", "2", "3", "5", "10", "95", "90", "99", "100", "0,05", "0,01", "0,1", "0,10", "0,025",
               "2,5", "1,5", "0,5", "0,7", "0,3"}
    bad = []
    for m in re.finditer(r"(?<![\w,])[−-]?\d+(?:,\d+)?(?:e[−-]?\d+)?", text):
        s = m.group(0).replace("−", "").replace("-", "", 1) if m.group(0)[0] in "−-" else m.group(0)
        if s in allowed or m.group(0) in facts.strings or s in facts.strings or ("−" + s) in facts.strings:
            continue
        bad.append(m.group(0))
    return bad
