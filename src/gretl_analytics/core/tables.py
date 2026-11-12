"""Таблицы описательной статистики и прогноза, разбор окна прогноза Gretl."""
import math
import re

from . import fmt, stats


# ------------------------------------------------------------------ значимость корреляции

def corr_p(r, n):
    if n < 3 or abs(r) >= 1:
        return 0.0
    t = r * math.sqrt((n - 2) / (1 - r * r))
    return stats.t_pvalue2(t, n - 2)


def _fix_date(s):
    m = re.match(r"^(\d{4})M(\d{2})$", s)
    if m:
        return f"{m.group(1)}:{m.group(2)}"
    m = re.match(r"^(\d{4})Q(\d)$", s)
    if m:
        return f"{m.group(1)}:{m.group(2)}"
    return s


# ------------------------------------------------------------------ описательная статистика

def summary_table(rows):
    """Как в Gretl, но транспонировано (статистики – строки), чтобы таблица помещалась на страницу."""
    stats_rows = [
        ("Среднее", lambda r: fmt.g(r["mean"], 5)), ("Медиана", lambda r: fmt.g(r["median"], 5)),
        ("Минимум", lambda r: fmt.g(r["min"], 5)), ("Максимум", lambda r: fmt.g(r["max"], 5)),
        ("Ст. откл.", lambda r: fmt.g(r["sd"], 5)),
        ("Вариация", lambda r: fmt.g(r["sd"] / abs(r["mean"]), 5) if r["mean"] else "NA"),
        ("Асимметрия", lambda r: fmt.g(r["skew"], 5)), ("Эксцесс", lambda r: fmt.g(r["exkurt"], 5)),
        ("5% перц.", lambda r: fmt.g(r["p05"], 5)), ("95% перц.", lambda r: fmt.g(r["p95"], 5)),
        ("Межкварт. размах", lambda r: fmt.g(r["q3"] - r["q1"], 5)),
        ("Пропущ. набл.", lambda r: str(int(r["missing"]))),
    ]
    header = [""] + [r["var"] for r in rows]
    out = []
    for lab, f in stats_rows:
        vals = [f(r) for r in rows]
        if all(v == "NA" for v in vals):
            continue
        out.append([lab] + vals)
    return {"header": header, "rows": out}


# ------------------------------------------------------------------ прогноз

def parse_fcast(text):
    res = {"rows": [], "eval": {}}
    m = re.search(r"For (\d+)% confidence intervals, (t|z)\((?:(\d+), )?([\d.]+)\) = ([\d.]+)", text)
    if m:
        res["level"] = int(m.group(1))
        res["crit"] = float(m.group(5))
        res["crit_df"] = int(m.group(3)) if m.group(3) else None
    m = re.search(r"^\s*(\S+)\s+prediction\s+std\. error", text, re.M)
    if m:
        res["depvar"] = m.group(1)
    for line in text.split("\n"):
        mm = re.match(r"^\s*(\S+)\s+(-?[\d.]+(?:e[-+]?\d+)?)?\s+(-?[\d.]+(?:e[-+]?\d+)?)\s+([\d.]+(?:e[-+]?\d+)?)\s+(-?[\d.]+(?:e[-+]?\d+)?)\s+-\s+(-?[\d.]+(?:e[-+]?\d+)?)\s*$", line)
        if mm:
            res["rows"].append({"obs": _fix_date(mm.group(1)), "actual": float(mm.group(2)) if mm.group(2) else None,
                                "pred": float(mm.group(3)), "se": float(mm.group(4)),
                                "lo": float(mm.group(5)), "hi": float(mm.group(6)),
                                "s": [_rs(mm.group(k)) if mm.group(k) else "" for k in range(2, 7)]})
            continue
        mm = re.match(r"^\s*(\S+)\s{8,}(-?[\d.]+(?:e[-+]?\d+)?)\s+([\d.]+(?:e[-+]?\d+)?)\s+(-?[\d.]+(?:e[-+]?\d+)?)\s+-\s+(-?[\d.]+(?:e[-+]?\d+)?)\s*$", line)
        if mm:
            res["rows"].append({"obs": _fix_date(mm.group(1)), "actual": None, "pred": float(mm.group(2)),
                                "se": float(mm.group(3)), "lo": float(mm.group(4)), "hi": float(mm.group(5)),
                                "s": [""] + [_rs(mm.group(k)) for k in range(2, 6)]})
    keys = [("Mean Error", "ME"), ("Root Mean Squared Error", "RMSE"), ("Mean Absolute Error", "MAE"),
            ("Mean Percentage Error", "MPE"), ("Mean Absolute Percentage Error", "MAPE"),
            ("Theil's U2", "U2"), ("Theil's U", "U"), ("Bias proportion, UM", "UM"),
            ("Regression proportion, UR", "UR"), ("Disturbance proportion, UD", "UD")]
    for lab, k in keys:
        mm = re.search(re.escape(lab) + r"\s+(-?[\d.]+(?:e[-+]?\d+)?)", text)
        if mm and k not in res["eval"]:
            res["eval"][k] = float(mm.group(1))
            res.setdefault("eval_s", {})[k] = _rs(mm.group(1))
    mm = re.search(r"using (\d+) observations", text)
    if mm:
        res["eval_n"] = int(mm.group(1))
    return res


def _rs(tok):
    """Число в том виде, как его напечатал Gretl, с десятичной запятой."""
    return fmt._ru(tok)


def fcast_table(fc):
    header = ["Наблюдение", fc.get("depvar", "y"), "Прогноз", "Ст. ошибка", f"{fc.get('level', 95)}% доверительный интервал"]
    rows = []
    for r in fc["rows"]:
        a, pr, se, lo, hi = r["s"]
        rows.append([r["obs"], a, pr, se, f"{lo} – {hi}"])
    return {"header": header, "rows": rows}

