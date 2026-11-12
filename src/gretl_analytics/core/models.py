"""Модель Gretl: коэффициенты и статистики, таблица в стиле Gretl, трактовка коэффициентов."""
import math
import re

from . import fmt, stats
from .meta import MONTHS_CMP, MONTHS_GEN, VarMeta

METHOD_RU = [
    (r"^OLS", "МНК"), (r"^WLS", "Взвешенный МНК"), (r"Heteroskedasticity-corrected", "МНК с поправкой на гетероскедастичность"),
    (r"Cochrane-Orcutt", "Кохрейн–Оркатт"), (r"Prais-Winsten", "Прайс–Уинстен"), (r"Hildreth-Lu", "Хилдрет–Лу"),
    (r"^TSLS", "Двухшаговый МНК"), (r"^Logit", "Логит"), (r"^Probit", "Пробит"), (r"^Tobit", "Тобит"),
    (r"^ARIMA|^ARMA|^ARMAX", None), (r"^LAD", "Метод наименьших модулей (LAD)"),
    (r"Quantile", "Квантильная регрессия"), (r"^Poisson", "Пуассоновская регрессия"),
    (r"Negative Binomial", "Отрицательная биномиальная регрессия"), (r"GARCH", None),
    (r"Fixed-effects", "Модель с фиксированными эффектами"), (r"Random-effects", "Модель со случайными эффектами"),
    (r"Pooled OLS", "Сквозной МНК"),
]
INTERPRETED = {"ols", "wls", "hsk", "tsls", "ar1", "mpols", "omit", "add", "lad", "quantreg", "logit", "probit"}
ASYMPTOTIC_CMDS = {"logit", "probit", "tobit", "poisson", "negbin", "arima", "arma", "garch", "heckit",
                   "intreg", "biprobit", "duration", "mle", "gmm", "logistic"}


def method_ru(method):
    for pat, ru in METHOD_RU:
        if re.search(pat, method or ""):
            return ru or method
    return method or ""


class Coef:
    def __init__(self, name, b, se, df, asymptotic):
        self.name, self.b, self.se = name, b, se
        self.t = b / se if se and se > 0 else float("nan")
        if math.isnan(self.t):
            self.p = float("nan")
        elif asymptotic or not df:
            self.p = 2 * stats.norm_sf(abs(self.t))
        else:
            self.p = stats.t_pvalue2(self.t, df)
        self.meta = None


class Model:
    def __init__(self, idx, bundle, text_info, labels, overrides, dsinfo):
        self.idx = idx
        self.b = bundle
        self.info = text_info
        self.labels = labels
        self.dsinfo = dsinfo or {}
        self.number = text_info.get("number")
        self.method = text_info.get("method", bundle.get("command", ""))
        self.command = bundle.get("command", "")
        self.depvar = bundle.get("depvar") or text_info.get("depvar")
        self.T = int(bundle.get("T", 0) or 0)
        self.df = int(bundle.get("df", 0) or 0) if not math.isnan(bundle.get("df", float("nan")) or 0) else 0
        self.asymptotic = bool(bundle.get("asymptotic", 0)) or self.command in ASYMPTOTIC_CMDS
        names = bundle.get("parnames") or []
        coeff = bundle.get("coeff") or []
        se = bundle.get("stderr") or []
        self.coefs = [Coef(n, b, s, self.df, self.asymptotic) for n, b, s in zip(names, coeff, se)]
        self.stats = dict(text_info.get("stats", {}))
        self.limdep = self.command in ("logit", "probit")
        self.me = text_info.get("slopes", {})
        self.k = len(self.coefs)
        self.has_const = any(c.name == "const" for c in self.coefs)
        ov = overrides or {}
        self.y = VarMeta(self.depvar, labels.get(self.depvar, ""), ov.get(self.depvar))
        for c in self.coefs:
            c.meta = VarMeta(c.name, labels.get(c.name, ""), ov.get(c.name))
            c.basemeta = None
            if c.meta.kind == "log":
                bn = c.meta.base or _log_base(labels.get(c.name, ""))
                if bn and bn in labels:
                    c.basemeta = VarMeta(bn, labels.get(bn, ""), ov.get(bn))
        self.ybase = None
        if self.y.kind == "log" and not (self.y.base or _log_base(labels.get(self.depvar, ""))):
            rest = re.sub(r"^логарифм\s+", "", self.y.nom) if self.y.nom.startswith("логарифм") else ""
            self.ybase = VarMeta(self.depvar, "", {"name": ("уровень " + rest) if rest else "исходный показатель (до логарифмирования)"})
        if self.y.kind == "log" and self.ybase is None:
            base = self.y.base or _log_base(labels.get(self.depvar, ""))
            if base:
                self.ybase = VarMeta(base, labels.get(base, ""), ov.get(base))
                if not (ov.get(self.depvar) or {}).get("name") and self.ybase.nom != base:
                    self.y.nom = f"логарифм {self.ybase.gen}"
                    self.y.gen = f"логарифма {self.ybase.gen}"
        self.obs_from = text_info.get("obs_from")
        self.obs_to = text_info.get("obs_to")
        self.timeseries = self.dsinfo.get("datatype") == 2
        self.pd = self.dsinfo.get("pd", 1)

    @property
    def title_ru(self):
        num = self.number or "?"
        rng = f"{self.obs_from}-{self.obs_to}" if self.obs_from else ""
        tail = f" (T = {self.T})" if self.timeseries else ""
        return f"Модель {num}: {method_ru(self.method)}, использованы наблюдения {rng}{tail}"

    def slopes(self):
        return [c for c in self.coefs if c.name != "const"]


def _log_base(label):
    m = re.search(r"log(?:arithm)? of (\w+)", label or "")
    return m.group(1) if m else None


# ------------------------------------------------------------------ таблицы

def coef_table(m):
    zt = "z" if m.asymptotic else "t-статистика"
    header = ["", "Коэффициент", "Ст. ошибка", zt, "p-значение", ""]
    rows = []
    for c in m.coefs:
        rows.append([c.name, fmt.g(c.b), fmt.g(c.se), fmt.tstat(c.t), fmt.pval(c.p), fmt.stars(c.p)])
    return {"header": header, "rows": rows}


def stats_table(m):
    s = m.stats
    pairs = []

    def add(lab, key, f=fmt.stat):
        if key in s and fmt.is_num(s[key]):
            pairs.append((lab, f(s[key])))

    add("Среднее завис. перемен", "ybar")
    add("Ст. откл. завис. перем", "sdy")
    add("Сумма кв. остатков", "ess")
    add("Ст. ошибка модели", "sigma")
    add("R-квадрат", "rsq", lambda x: fmt.fixed(x, 6))
    add("Исправ. R-квадрат", "adjrsq", lambda x: fmt.fixed(x, 6))
    if "F" in s and "F_df" in s:
        pairs.append((f"F({s['F_df'][0]}, {s['F_df'][1]})", fmt.stat(s["F"])))
        if "pvalue_F" in s:
            pairs.append(("p-значение (F)", _pF(s["pvalue_F"])))
    if "chisq" in s and "chisq_df" in s:
        pairs.append((f"Хи-квадрат({s['chisq_df']})", fmt.stat(s["chisq"])))
    add("McFadden R-квадрат", "mcfadden", lambda x: fmt.fixed(x, 6))
    add("Лог. правдоподобие", "lnl")
    add("Крит. Акаике", "aic")
    add("Крит. Шварца", "bic")
    add("Крит. Хеннана–Куинна", "hqc")
    add("параметр rho", "rho", lambda x: fmt.fixed(x, 6))
    add("Стат. Дарбина–Уотсона", "dw", lambda x: fmt.fixed(x, 6))
    rows = []
    for i in range(0, len(pairs), 2):
        a = pairs[i]
        b = pairs[i + 1] if i + 1 < len(pairs) else ("", "")
        rows.append([a[0], a[1], "", b[0], b[1]])
    return {"header": None, "rows": rows}


def _pF(p):
    if p < 0.0001:
        return f"{p:.2e}".replace(".", ",")
    return fmt.fixed(p, 6)


def equation(m):
    """Уравнение как в Gretl «Просмотреть как уравнение» (3 знач. цифры, ст. ошибки в скобках)."""
    parts, ses = [], []
    for i, c in enumerate(m.coefs):
        val = fmt.g(abs(c.b), 3).replace("−", "")
        sign = fmt.MINUS if c.b < 0 else "+"
        term = val if c.name == "const" else f"{val}*{c.name}"
        if i == 0:
            parts.append((fmt.MINUS if c.b < 0 else "") + term)
        else:
            parts.append(f"{sign} {term}")
        ses.append("(" + fmt.g(c.se, 3) + ")")
    eq = f"^{m.depvar} = " + " ".join(parts)
    return {"text": eq, "se": " ".join(ses)}


# ------------------------------------------------------------------ интерпретация

def _period_word(pd):
    return {12: ("месяц", "месяца"), 4: ("квартал", "квартала"), 1: ("год", "года"), 7: ("день", "дня"),
            5: ("день", "дня"), 52: ("неделю", "недели")}.get(pd, ("период", "периода"))


def _season_name(p, pd):
    if pd == 12 and 1 <= p <= 12:
        return MONTHS_GEN[p - 1], MONTHS_CMP[p - 1]
    if pd == 4:
        return f"{p}-м квартале", f"{p}-м кварталом"
    return f"периоде {p}", f"периодом {p}"


def _change_word(b, up="увеличивается", down="уменьшается"):
    return up if b > 0 else down


def _limdep_effect(ctx, m, c):
    x = c.meta
    ev = f"события {m.depvar} = 1"
    if m.command == "logit":
        orr = math.exp(c.b)
        if x.kind == "dummy":
            k = orr if orr >= 1 else 1 / orr
            s = (f"Для наблюдений с {c.name} = 1 шансы {ev} в {ctx.n(k, sig=4)} раза "
                 f"{'выше' if orr > 1 else 'ниже'}, чем при {c.name} = 0 (отношение шансов OR = e^b = {ctx.n(orr, sig=4)}), при прочих равных.")
        else:
            s = f"При увеличении {x.gen} на {x.one_or()} шансы {ev} умножаются на e^b = {ctx.n(orr, sig=4)}"
            if orr >= 2:
                s += f", то есть возрастают в {ctx.n(orr, sig=4)} раза, при прочих равных."
            else:
                s += (f", то есть {'растут' if orr > 1 else 'снижаются'} на {ctx.abs_n(100 * (orr - 1), nd=1)}%, при прочих равных.")
    else:
        s = (f"Знак коэффициента пробит-модели показывает направление влияния: рост {x.gen} "
             f"{'повышает' if c.b > 0 else 'снижает'} вероятность {ev}; сама величина коэффициента – изменение латентного индекса, "
             f"а не вероятности.")
    me = m.me.get(c.name)
    if me is not None:
        s += (f" Предельный эффект в точке средних значений регрессоров (столбец slope в Gretl) равен {ctx.n(me, nd=4)}: "
              + (f"переход {c.name} от 0 к 1 {'повышает' if me > 0 else 'снижает'} вероятность события примерно на {ctx.abs_n(100 * me, nd=1)} п.п."
                 if x.kind == "dummy" else
                 f"малое изменение {x.gen} изменяет вероятность события со скоростью около {ctx.abs_n(100 * me, nd=1)} п.п. на единицу; "
                 f"это линейная аппроксимация, точная лишь для небольших изменений вблизи средних значений."))
    return s


def _effect_sentence(ctx, m, c, simple):
    """Содержательная интерпретация коэффициента с учётом функциональной формы."""
    if m.limdep:
        return _limdep_effect(ctx, m, c)
    if m.command not in INTERPRETED:
        return (f"Содержательная интерпретация коэффициентов модели «{method_ru(m.method)}» зависит от её спецификации "
                f"и помощником автоматически не формируется; ниже приведена только статистическая значимость.")
    x, y = c.meta, m.y
    b = c.b
    ceteris = "" if simple else " при прочих равных условиях"
    ylog = y.kind == "log"
    ynom = (m.ybase.nom if (ylog and m.ybase) else y.nom)
    yunit = y.unit_or()

    if x.kind == "season":
        cur, _ = _season_name(x.period, m.pd)
        base_periods = _base_periods(m)
        if base_periods and len(base_periods) == 1:
            ref = f"чем в {_base_loc(base_periods[0], m.pd)} (базовый период)"
        else:
            ref = "чем в базовом периоде"
        if ylog:
            pc = 100 * (math.exp(b) - 1)
            return (f"В {cur} {ynom} в среднем на {ctx.abs_n(pc, nd=1)}% {'выше' if b > 0 else 'ниже'}, {ref}, "
                    f"при одинаковом значении тренда (100·(e^b − 1), b = {ctx.g(b, 4)}).")
        return (f"В {cur} {ynom} в среднем на {ctx.abs_n(b)} {yunit} {'выше' if b > 0 else 'ниже'}, {ref}, "
                f"при одинаковом значении тренда.")

    if x.kind == "trend":
        per, _ = _period_word(m.pd if m.timeseries else 1)
        if ylog:
            g1 = 100 * (math.exp(b) - 1)
            s = (f"Коэффициент при тренде показывает, что за каждый {per} {ynom} в среднем "
                 f"{'растёт' if b > 0 else 'снижается'} примерно на {ctx.abs_n(g1, nd=2)}%{ceteris}")
            if m.pd in (4, 12) and m.timeseries:
                ga = 100 * (math.exp(b * m.pd) - 1)
                s += f", что соответствует {ctx.abs_n(ga, nd=1)}% за год"
            return s + "."
        return (f"Коэффициент при тренде показывает, что за каждый {per} {ynom} в среднем "
                f"{_change_word(b)} на {ctx.abs_n(b)} {yunit}{ceteris}.")

    if x.kind == "dummy":
        cond = f"{x.name} = 1"
        if ylog:
            pc = 100 * (math.exp(b) - 1)
            return (f"Для наблюдений с {cond} ({x.nom}) {ynom} в среднем на {ctx.abs_n(pc, nd=1)}% "
                    f"{'выше' if b > 0 else 'ниже'}, чем для наблюдений с {x.name} = 0{ceteris} (100·(e^b − 1)).")
        return (f"Для наблюдений с {cond} ({x.nom}) {ynom} в среднем на {ctx.abs_n(b)} {yunit} "
                f"{'выше' if b > 0 else 'ниже'}, чем для наблюдений с {x.name} = 0{ceteris}.")

    if x.kind == "square":
        return _square_sentence(ctx, m, c)

    xlog = x.kind == "log"
    xgen = c.basemeta.gen if (xlog and getattr(c, "basemeta", None)) else x.gen
    if ylog and xlog:
        return (f"Коэффициент является эластичностью: при росте {xgen} на 1% {ynom} в среднем "
                f"{_change_word(b)} примерно на {ctx.abs_n(b)}%{ceteris}.")
    if ylog and not xlog:
        pc = 100 * (math.exp(b) - 1)
        return (f"При увеличении {x.gen} на {x.one_or()} {ynom} в среднем {_change_word(b)} "
                f"примерно на {ctx.abs_n(pc, nd=2)}%{ceteris} (полуэластичность; 100·(e^b − 1)).")
    if xlog and not ylog:
        return (f"При росте {xgen} на 1% {y.nom} в среднем {_change_word(b)} примерно на "
                f"{ctx.abs_n(b / 100)} {yunit}{ceteris} (b/100).")
    sq = _find_square(m, c.name)
    if sq is not None:
        return _square_sentence(ctx, m, sq, base=c)
    lag = f" (значение с лагом {x.lag})" if x.kind == "lag" else ""
    return (f"При увеличении {x.gen}{lag} на {x.one_or()} {y.nom} в среднем {_change_word(b)} на "
            f"{ctx.abs_n(b)} {yunit}{ceteris}.")


def _base_loc(p, pd):
    if pd == 12 and 1 <= p <= 12:
        return MONTHS_GEN[p - 1]
    if pd == 4:
        return f"{p}-м квартале"
    return f"периоде {p}"


def _base_periods(m):
    present = {c.meta.period for c in m.coefs if c.meta.kind == "season"}
    if not present or not m.pd or m.pd < 2:
        return []
    return [p for p in range(1, m.pd + 1) if p not in present]


def _find_square(m, base):
    for c in m.coefs:
        if c.meta.kind == "square" and c.meta.base == base:
            return c
    return None


def _square_sentence(ctx, m, sq, base=None):
    if base is None:
        base = next((c for c in m.coefs if c.name == sq.meta.base), None)
    if base is None:
        return (f"Коэффициент при квадрате {sq.meta.base or sq.name} характеризует кривизну зависимости: "
                f"{'выпуклость' if sq.b > 0 else 'вогнутость'} (b = {ctx.g(sq.b, 4)}).")
    b1, b2 = base.b, sq.b
    s = (f"Переменная {base.name} входит в модель вместе с квадратом, поэтому её предельный эффект непостоянен: "
         f"∂{m.depvar}/∂{base.name} = {ctx.g(b1, 4)} + 2·({ctx.g(b2, 4)})·{base.name}.")
    if b2 != 0:
        xstar = -b1 / (2 * b2)
        s += (f" Зависимость {'U-образная (минимум)' if b2 > 0 else 'имеет форму перевёрнутой U (максимум)'} "
              f"в точке {base.name} = {ctx.n(xstar)}. Проверьте по описательной статистике, лежит ли эта точка "
              f"внутри наблюдаемого диапазона: если нет, в пределах выборки зависимость монотонна.")
    return s

