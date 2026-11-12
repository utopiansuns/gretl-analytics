"""Общие разделы отчёта: каркас раздела, сравнение моделей, итоговые выводы."""
import re

from . import fmt
from .ctx import sig_level


def _section(kind, title, **kw):
    s = {"id": None, "kind": kind, "title": title, "command": None, "tables": [], "images": [], "equation": None,
         "brief": [], "full": [], "raw": None, "note": None}
    s.update(kw)
    return s


def _tidy(p):
    p = re.sub(r"(?<![.])\.\.(?![.])", ".", p)
    p = re.sub(r"\s+([,.;:])", r"\1", p)
    # абзац начинается с заглавной; русские названия внутри предложения остаются как в словаре
    if re.match(r"[а-яё]", p):
        p = p[0].upper() + p[1:]
    return p


def _compare_models(ctx, ms):
    if len(ms) < 2:
        return None
    sec = _section("compare", "Сравнение моделей")
    header = ["Модель", "Зависимая", "k", "n", "R²", "Испр. R²", "AIC", "BIC", "HQC"]
    rows = []
    for m in ms:
        s = m.stats
        rows.append([str(m.number), m.depvar, str(m.k), str(m.T), fmt.fixed(s.get("rsq", float("nan")), 4),
                     fmt.fixed(s.get("adjrsq", float("nan")), 4), fmt.stat(s.get("aic", float("nan"))),
                     fmt.stat(s.get("bic", float("nan"))), fmt.stat(s.get("hqc", float("nan")))])
    sec["tables"].append({"caption": "Сводка по моделям", "header": header, "rows": rows})
    P = []
    groups = {}
    for m in ms:
        groups.setdefault((m.depvar, m.T, m.obs_from, m.obs_to), []).append(m)
    refs = {m.depvar: m.y.ref() for m in ms}
    for (dep, _, _, _), g in groups.items():
        if len(g) < 2:
            continue
        names = ", ".join(str(m.number) for m in g)
        votes = {}
        for crit in ("aic", "bic", "hqc"):
            vals = [(m.stats.get(crit), m) for m in g if fmt.is_num(m.stats.get(crit))]
            if vals:
                best = min(vals, key=lambda x: x[0])[1]
                votes[crit] = best.number
        adj = [(m.stats.get("adjrsq"), m) for m in g if fmt.is_num(m.stats.get("adjrsq"))]
        txt = f"Модели {names} имеют одну зависимую переменную ({refs[dep]}) и одну выборку, поэтому их можно сравнивать. "
        for x in range(len(g)):
            for y in range(x + 1, len(g)):
                a, b2 = g[x], g[y]
                if a.k == b2.k and fmt.is_num(a.stats.get("ess")) and abs(a.stats["ess"] - b2.stats.get("ess", 0)) <= 1e-6 * max(1, a.stats["ess"]):
                    txt += (f"Модели {ctx.int(a.number)} и {ctx.int(b2.number)} эквивалентны: у них одинаковые сумма квадратов остатков, R² и "
                            f"информационные критерии – они различаются только параметризацией (например, выбором базовой категории). ")
        if votes:
            txt += ("Наименьшие значения информационных критериев: " +
                    ", ".join(f"{ {'aic': 'Акаике', 'bic': 'Шварца', 'hqc': 'Хеннана–Куинна'}[k]} – модель {ctx.int(v)}" for k, v in votes.items()) + ". ")
        if adj:
            ba = max(adj, key=lambda x: x[0])
            txt += f"Наибольший скорректированный R² ({ctx.n(ba[0], nd=4)}) – у модели {ctx.int(ba[1].number)}. "
        vs = list(votes.values())
        if vs and all(v == vs[0] for v in vs):
            txt += f"Все критерии согласованно указывают на модель {ctx.int(vs[0])}."
        elif vs:
            txt += "Критерии расходятся: BIC сильнее штрафует за число параметров и обычно предпочитает более компактную модель."
        P.append(txt)
    deps = {m.depvar for m in ms}
    if len(deps) > 1:
        P.append("Модели с разными зависимыми переменными (" + ", ".join(sorted(deps)) + ") напрямую по R² и информационным "
                 "критериям сравнивать нельзя: эти показатели относятся к разным величинам (например, к уровню и к логарифму).")
    if not P:
        return None
    sec["full"] = P
    sec["brief"] = P[:1]
    return sec


def _conclusions(ctx, sections, ms):
    if not ms:
        return None
    P = []
    for m in ms:
        sig = [(c.name if c.meta.kind == "season" else c.meta.ref()) for c in m.slopes() if sig_level(c.p) and sig_level(c.p) <= 5]
        nsig = [(c.name if c.meta.kind == "season" else c.meta.ref()) for c in m.slopes() if not (sig_level(c.p) and sig_level(c.p) <= 5)]
        s = f"Модель {m.number} (зависимая переменная: {m.y.nom if m.y.nom != m.depvar else m.depvar}): "
        s += (f"статистически значимы на 5%-ном уровне: {', '.join(sig)}" if sig else "ни один регрессор не значим на 5%-ном уровне")
        if nsig:
            s += f"; незначимы: {', '.join(nsig)}"
        if "rsq" in m.stats:
            s += f"; R² = {ctx.n(m.stats['rsq'], nd=3)}"
        P.append(s + ".")
    probs = {}
    short = {"normality": "ненормальность остатков", "white": "гетероскедастичность", "white_nocross": "гетероскедастичность",
             "bp": "гетероскедастичность", "koenker": "гетероскедастичность", "autocorr": "автокорреляция остатков",
             "reset": "ошибка функциональной формы (RESET)", "chow": "структурный сдвиг", "arch": "ARCH-эффект",
             "squares": "нелинейность", "logs": "нелинейность", "qlr": "структурный сдвиг"}
    num = {m.idx: m.number for m in ms}
    for s in sections:
        if s["kind"] == "test" and s.get("test_key") in short and s.get("reject"):
            lst = probs.setdefault(num.get(s.get("model_idx")), [])
            if short[s["test_key"]] not in lst:
                lst.append(short[s["test_key"]])
    if probs:
        P.append("По результатам диагностических тестов (5%-ный уровень) выявлены нарушения предпосылок, которые нужно учитывать при выводах: "
                 + "; ".join(f"модель {k} – {', '.join(v)}" if k is not None else ", ".join(v)
                            for k, v in probs.items()) + ".")
    P.append("Все выводы носят статистический характер: значимость коэффициентов показывает наличие устойчивой связи в выборке, "
             "но не доказывает причинно-следственного влияния факторов.")
    sec = _section("conclusions", "Выводы")
    sec["full"] = P
    sec["brief"] = P
    return sec
