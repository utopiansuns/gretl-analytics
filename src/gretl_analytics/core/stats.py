"""Функции распределений без внешних зависимостей (t, F, хи-квадрат, нормальное).

Используются только для критических значений; все оценки моделей и тестов
берутся из вывода Gretl. Значения сверяются с critical() Gretl в tests/test_engine.py.
"""
import math


def _betacf(a, b, x, itmax=500, eps=3e-16):
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > 1e-300 else 1e-300)
    h = d
    for m in range(1, itmax + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > 1e-300 else 1e-300)
        c = 1.0 + aa / c
        c = c if abs(c) > 1e-300 else 1e-300
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > 1e-300 else 1e-300)
        c = 1.0 + aa / c
        c = c if abs(c) > 1e-300 else 1e-300
        de = d * c
        h *= de
        if abs(de - 1.0) < eps:
            break
    return h


def betainc(a, b, x):
    """Регуляризованная неполная бета-функция I_x(a, b)."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbt = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b) + a * math.log(x) + b * math.log1p(-x)
    if x < (a + 1) / (a + b + 2):
        return math.exp(lbt) * _betacf(a, b, x) / a
    return 1.0 - math.exp(lbt) * _betacf(b, a, 1 - x) / b


def gammainc(a, x):
    """Регуляризованная нижняя неполная гамма-функция P(a, x)."""
    if x <= 0:
        return 0.0
    if x < a + 1:
        s, term, n = 1.0 / a, 1.0 / a, a
        for _ in range(1000):
            n += 1
            term *= x / n
            s += term
            if abs(term) < abs(s) * 1e-16:
                break
        return s * math.exp(-x + a * math.log(x) - math.lgamma(a))
    # непрерывная дробь для Q
    b, c, d = x + 1 - a, 1e300, 1.0 / (x + 1 - a)
    h = d
    for i in range(1, 1000):
        an = -i * (i - a)
        b += 2
        d = an * d + b
        d = 1.0 / (d if abs(d) > 1e-300 else 1e-300)
        c = b + an / c
        c = c if abs(c) > 1e-300 else 1e-300
        de = d * c
        h *= de
        if abs(de - 1) < 1e-16:
            break
    return 1.0 - math.exp(-x + a * math.log(x) - math.lgamma(a)) * h


def t_sf(t, df):
    """P(T > t)."""
    x = df / (df + t * t)
    p = 0.5 * betainc(df / 2.0, 0.5, x)
    return p if t >= 0 else 1 - p


def t_pvalue2(t, df):
    return min(1.0, 2 * t_sf(abs(t), df))


def f_sf(f, d1, d2):
    if f <= 0:
        return 1.0
    return betainc(d2 / 2.0, d1 / 2.0, d2 / (d2 + d1 * f))


def chi2_sf(x, k):
    return 1.0 - gammainc(k / 2.0, x / 2.0) if x > 0 else 1.0


def norm_sf(z):
    return 0.5 * math.erfc(z / math.sqrt(2))


def _invert(sf, target, lo, hi):
    # sf убывает по x; ищем x: sf(x) = target
    while sf(hi) > target:
        hi *= 2
        if hi > 1e12:
            break
    for _ in range(300):
        mid = 0.5 * (lo + hi)
        if sf(mid) > target:
            lo = mid
        else:
            hi = mid
        if hi - lo < 1e-13 * max(1.0, abs(mid)):
            break
    return 0.5 * (lo + hi)


def t_crit(alpha_right, df):
    """Критическое значение t: P(T > t) = alpha_right (как critical(t, df, a) в Gretl)."""
    return _invert(lambda x: t_sf(x, df), alpha_right, 0.0, 10.0)


def f_crit(alpha, d1, d2):
    return _invert(lambda x: f_sf(x, d1, d2), alpha, 0.0, 10.0)


def chi2_crit(alpha, k):
    return _invert(lambda x: chi2_sf(x, k), alpha, 0.0, max(10.0, 3.0 * k))
