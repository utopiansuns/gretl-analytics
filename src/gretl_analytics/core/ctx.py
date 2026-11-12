"""Контекст генерации текста: форматирование чисел с регистрацией в реестре фактов."""
import math

from . import fmt
from .meta import Facts


class Ctx:
    def __init__(self, alpha=0.05):
        self.facts = Facts()
        self.alpha = alpha

    def _r(self, s):
        self.facts.add(s)
        return s

    # числа для текста
    def n(self, x, nd=None, sig=4):
        return self._r(fmt.num(x, nd=nd, sig=sig))

    def g(self, x, sig=6):
        return self._r(fmt.g(x, sig))

    def stat(self, x):
        return self._r(fmt.stat(x))

    def t(self, x):
        return self._r(fmt.tstat(x))

    def p(self, p):
        s = fmt.pval_text(p)
        self._r(s.replace("p = ", "").replace("p < ", ""))
        return s

    def pv(self, p):
        s = fmt.pval(p, table=False)
        return self._r(s)

    def pct(self, x, nd=1):
        s = fmt.pct(x, nd)
        self._r(s[:-1])
        return s

    def abs_n(self, x, nd=None, sig=4):
        return self.n(abs(x), nd=nd, sig=sig)

    def raw(self, s):
        """Регистрирует строку, взятую дословно из вывода Gretl (метка наблюдения, df)."""
        import re
        for m in re.finditer(r"[−-]?\d+(?:,\d+)?(?:e[−-]?\d+)?", str(s)):
            self._r(m.group(0))
            self._r(m.group(0).lstrip("−-"))
        return str(s)

    def int(self, k):
        return self._r(str(int(k)))


def sig_level(p):
    if p is None or (isinstance(p, float) and math.isnan(p)):
        return None
    if p < 0.01:
        return 1
    if p < 0.05:
        return 5
    if p < 0.10:
        return 10
    return None


def strength(r):
    a = abs(r)
    if a < 0.1:
        return "практически отсутствует"
    if a < 0.3:
        return "слабая"
    if a < 0.5:
        return "умеренная"
    if a < 0.7:
        return "заметная"
    if a < 0.9:
        return "высокая"
    return "весьма высокая"
