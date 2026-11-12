"""Форматирование чисел в стиле русскоязычного Gretl (десятичная запятая)."""
import math
import re

MINUS = "−"  # Gretl в RTF/GUI использует типографский минус


def _ru(s, minus=True):
    s = s.replace(".", ",")
    if minus and s.startswith("-"):
        s = MINUS + s[1:]
    return s


def is_num(x):
    return isinstance(x, (int, float)) and not (isinstance(x, float) and (math.isnan(x) or math.isinf(x)))


def g(x, sig=6, minus=True):
    """Как Gretl печатает коэффициенты: %#.6g без лишней экспоненты."""
    if not is_num(x):
        return "NA"
    if x == 0:
        return "0"
    ax = abs(x)
    if ax >= 1e-4 and ax < 10 ** sig:
        digits = sig - 1 - int(math.floor(math.log10(ax)))
        digits = max(digits, 0)
        s = f"{x:.{digits}f}"
        # округление могло добавить разряд (9.999995 -> 10.00000)
        if len(s.replace("-", "").replace(".", "").lstrip("0")) > sig and digits > 0:
            s = f"{x:.{digits - 1}f}"
    else:
        s = f"{x:.{sig - 1}e}"
        m, e = s.split("e")
        s = f"{m}e{int(e):+03d}"
    return _ru(s, minus)


def stat(x, sig=7):
    """Сводные статистики модели (%.7g в Gretl)."""
    return g(x, sig)


def tstat(x):
    """t-статистика: 4 значащие цифры, как в таблице Gretl."""
    return g(x, 4)


def fixed(x, nd=6):
    if not is_num(x):
        return "NA"
    return _ru(f"{x:.{nd}f}")


def pval(p, table=True):
    """p-значение: в таблицах Gretl – «<0,0001»; в тексте – 4 знака или экспонента."""
    if not is_num(p):
        return "NA"
    if p < 0.0001:
        return "<0,0001" if table else _ru(f"{p:.2e}").replace("e-0", "e-")
    return _ru(f"{p:.4f}")


def pval_text(p):
    if not is_num(p):
        return "p = NA"
    if p < 0.0001:
        return "p < 0,0001"
    return "p = " + _ru(f"{p:.4f}")


def num(x, nd=None, sig=4):
    """Число для текста интерпретации: разумное округление."""
    if not is_num(x):
        return "NA"
    if nd is not None:
        s = f"{x:.{nd}f}"
    else:
        ax = abs(x)
        if ax == 0:
            s = "0"
        elif ax >= 1000:
            s = f"{x:.1f}" if ax < 1e6 else f"{x:.4g}"
        elif ax >= 1:
            s = f"{x:.{max(sig - 1 - int(math.floor(math.log10(ax))), 0)}f}"
        elif ax >= 1e-4:
            s = f"{x:.{sig - 1 - int(math.floor(math.log10(ax)))}f}"
        else:
            s = f"{x:.2e}"
    if "e" not in s and "." in s and nd is None:
        s = s.rstrip("0").rstrip(".") if ax < 1e6 else s
    return _ru(s)


def pct(x, nd=1):
    return _ru(f"{x:.{nd}f}") + "%"


def stars(p):
    if not is_num(p):
        return ""
    return "***" if p < 0.01 else "**" if p < 0.05 else "*" if p < 0.1 else ""


_SUP = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")
_SCI = re.compile(r"(?<=\d)e([+−-]?)0*(\d+)")
_RANGE = re.compile(r"(?<![\w.,:−-])(\d+(?::\d+)?)-(\d+(?::\d+)?)(?![\w.,:−-]?\d)")
_PCT = re.compile(r"(?<=\d)%(?!-)")


def typo(text):
    """Типографика научного текста.

    3,76e-17 → 3,76·10⁻¹⁷; диапазоны через тире: 1962–1994, 1949:01–1960:12;
    знак процента через неразрывный пробел (ГОСТ 8.417): 82,1 %, но «5%-ный».
    """
    text = _SCI.sub(lambda m: "·10" + ("⁻" if m.group(1) in "−-" else "") + m.group(2).translate(_SUP), text)
    text = _RANGE.sub(r"\1–\2", text)
    return _PCT.sub("\u00a0%", text)
