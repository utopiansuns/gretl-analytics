"""Сборка отчёта: каждая часть вставки разбирается и превращается в раздел с таблицами и текстом.

Все числа берутся из вставленного текста; verify_numbers() проверяет, что в отчёте нет чисел,
которых нет во вставке и которые не получены из неё по явной формуле.
"""
import datetime
import json
import math
import os
import re

from . import fmt, models, morph, style, tables, tests_kb
from .ctx import Ctx, sig_level, strength
from .meta import VarMeta, base_name, guess_by_name, guess_known, verify_numbers
from .parsing import (NUM, detect_kind, normalize, parse_corr, parse_data_desc, parse_model, parse_summary,
                      parse_test, split_text, to_en)
from .sections import _compare_models, _conclusions, _section, _tidy


def interpret_corr_matrix(ctx, names, mat, n):
    header = [""] + names
    rows = [[a] + [fmt.g(mat.get((a, b), float("nan")), 4) for b in names] for a in names]
    P = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            r = mat.get((a, b))
            if r is None or math.isnan(r):
                continue
            txt = f"{a} и {b}: r = {ctx.n(r, nd=4)} – {strength(r)} {'положительная' if r > 0 else 'отрицательная'} линейная связь (шкала Чеддока)"
            if n and n > 2:
                pv = tables.corr_p(r, n)
                lvl = sig_level(pv)
                txt += f", {'значимая' if lvl and lvl <= 5 else 'статистически незначимая'} на 5%-ном уровне ({ctx.p(pv)}, n = {ctx.int(n)})"
            P.append(txt + ".")
    P.append("Коэффициент корреляции измеряет только линейную связь и не говорит о направлении причинности; "
             "высокая корреляция может быть вызвана общим третьим фактором (например, общим трендом).")
    return {"header": header, "rows": rows}, P


def glossary_overrides(glossary):
    """Словарь из приложения: [{"var": "price", "ru": "цена", "unit": "тыс. долл."}] → overrides для VarMeta.
    В поле единиц «0/1» или «фиктивная» отмечает фиктивную переменную."""
    ov = {}
    for g in glossary or []:
        var = (g.get("var") or "").strip()
        if not re.match(r"^[A-Za-z_]\w*$", var):
            continue
        d = {}
        if (g.get("ru") or "").strip():
            d["name"] = g["ru"].strip()
        unit = (g.get("unit") or "").strip()
        if re.match(r"^(0/1|0-1|фиктивн|dummy)", unit, re.I):
            d["kind"] = "dummy"
        elif unit:
            d["unit"] = unit
        if d:
            ov[var] = d
    return ov


def find_variables(text, glossary=None):
    """Имена переменных во вставленном тексте (для словаря в приложении) и формы русских названий."""
    names, labels = [], {}

    def add(n):
        if n and n != "const" and n not in names:
            names.append(n)

    for kind, t in split_text(text or ""):
        kind = kind or detect_kind(t)
        if kind == "data":
            for n, lab in parse_data_desc(t).items():
                labels[n] = lab
                add(n)
        elif kind == "model":
            pm = parse_model(t)
            if pm:
                add(pm["bundle"].get("depvar"))
                for n in pm["bundle"].get("parnames", []):
                    add(n)
        elif kind == "summary":
            for r in parse_summary(t):
                add(r["var"])
        elif kind == "corr":
            for n in parse_corr(t)[0]:
                add(n)
    ov = glossary_overrides(glossary)
    known = guess_known({base_name(n) for n in names} | set(names))
    out = []
    for n in names:
        auto = VarMeta(n, labels.get(n, ""))
        if auto.kind in ("season", "trend", "const"):
            continue
        # 1) словарь наборов Gretl, 2) описание из вставки, 3) подсказка по имени
        by_name = guess_by_name(n, known)
        suggest, unit = (auto.nom if auto.nom != n else ""), auto.unit or ""
        if n in known:
            suggest, unit = known[n]
        elif by_name:
            suggest, unit = suggest or by_name[0], unit or by_name[1]
        if auto.kind == "dummy":
            unit = "0/1"
        out.append({"name": n, "label": labels.get(n, ""), "kind": auto.kind, "suggest": suggest, "unit": unit})
    forms = {}
    for n, d in ov.items():
        vm = VarMeta(n, labels.get(n, ""), d)
        if vm.nom != n:
            forms[n] = {c: vm.case(c) for c in ("nom", "gen", "dat", "acc", "ins")}
    return {"variables": out, "forms": forms, "morphology": morph.available()}


def analyze_blocks(blocks, outdir, title=None, glossary=None):
    os.makedirs(outdir, exist_ok=True)
    ctx = Ctx()
    overrides = glossary_overrides(glossary)
    sections, ms, warnings = [], [], []
    last_model = None
    labels = {}
    expanded = []
    for blk in blocks:
        if blk.get("kind", "auto") == "auto" and blk.get("text", "").strip():
            for k, t in split_text(blk["text"]):
                expanded.append({"kind": k or "auto", "text": t, "split": True})
        else:
            expanded.append(blk)
    blocks = expanded
    for blk in blocks:
        k = blk.get("kind", "auto")
        if k == "data" or (k == "auto" and detect_kind(blk.get("text", "")) == "data"):
            labels.update(parse_data_desc(blk.get("text", "")))
    for bi, blk in enumerate(blocks, 1):
        text = blk.get("text", "")
        if not text.strip():
            continue
        kind = blk.get("kind", "auto")
        if kind == "auto":
            kind = detect_kind(text)
        quiet = blk.get("split") and blk.get("kind") == "auto"   # заголовки и прочий текст вокруг вывода Gretl
        where = f"Фрагмент «{text.strip().splitlines()[0][:60]}»"
        if kind == "data":
            rows = []
            for n, lab in parse_data_desc(text).items():
                vm = VarMeta(n, lab, overrides.get(n))
                rows.append([n, lab, vm.nom if vm.nom != n else "-", vm.unit or "-"])
            sec = _section("data", "Описание данных")
            sec["tables"].append({"caption": "Переменные", "header": ["Переменная", "Описание", "Название", "Единицы"], "rows": rows})
            sections.append(sec)
            continue
        if kind == "model":
            pm = parse_model(text)
            if not pm:
                warnings.append(f"{where}: не найдена таблица коэффициентов (строки «имя  коэффициент  ст. ошибка  t  p»).")
                continue
            m = models.Model(bi, pm["bundle"], pm["info"], labels, overrides, pm["dsinfo"])
            for c in m.coefs:
                if c.name in pm["pvalues"]:
                    c.p = pm["pvalues"][c.name]
            aux = re.match(r"\s*(Расширенная регрессия[^\n]*|Augmented regression[^\n]*)", normalize(text))
            if aux:
                # вспомогательная регрессия теста (например, Чоу): только таблица, выводы – в разделе теста
                title_ = aux.group(1).strip()
                if title_.startswith("Augmented regression for Chow"):
                    title_ = "Расширенная регрессия для теста Чоу"
                sec = _section("model", title_)
                sec["tables"].append(dict(models.coef_table(m), caption=f"{sec['title']}\nЗависимая переменная: {m.depvar}"))
                sec["note"] = "Вспомогательная регрессия теста; выводы приведены в разделе теста ниже."
                sections.append(sec)
                last_model = None
                continue
            if m.number is None:
                m.number = len(ms) + 1
            sec = _section("model", m.title_ru if pm["info"].get("obs_from") else f"Модель {m.number}: {models.method_ru(m.method)}")
            sec["tables"].append(dict(models.coef_table(m), caption=f"{sec['title']}\nЗависимая переменная: {m.depvar}"))
            st = models.stats_table(m)
            if st["rows"]:
                sec["tables"].append(dict(st, caption=None))
            sec["equation"] = models.equation(m)
            sec["full"] = style.model_text(ctx, m, full=True)
            sec["brief"] = style.model_brief(ctx, m)
            if not m.T:
                sec["note"] = "Число наблюдений не найдено во вставленном тексте – вставьте вывод модели целиком (с заголовком и F-статистикой)."
            sections.append(sec)
            ms.append(m)
            last_model = m
        elif kind == "test":
            pt = parse_test(text)
            if blk.get("split") and pt["stat"] is None and pt["key"] != "vif":
                if not re.search(r"p-значение|p-value", pt["text"]):
                    continue   # только заголовок, без результатов теста
            if pt["key"] == "vif":
                title_, table, full = tests_kb.interpret_test(ctx, "vif", None, None, {}, pt["text"], last_model, True)
                brief = full[1:]
            elif pt["key"] in tests_kb.KB and pt["stat"] is not None and pt["key"] not in ("adf", "kpss"):
                kb = tests_kb.KB[pt["key"]]
                title_ = kb[0]
                extra = tests_kb.parse_extra(pt["key"], pt["text"])
                extra["_dist"] = pt["dist"]
                dl = ctx.raw(tests_kb._dist_label(pt["dist"]))
                full = style.test_text(ctx, pt["key"], kb, pt["stat"], pt["p"], dl, extra, True)
                brief = [x for x in style.test_text(ctx, pt["key"], kb, pt["stat"], pt["p"], dl, extra, False) if x.startswith("Вывод")]
                table = {"header": ["Показатель", "Значение"],
                         "rows": [["Статистика" + (f" {dl}" if dl else ""), fmt.g(pt["stat"])],
                                  ["p-значение", fmt.pval(pt["p"], table=False) if pt["p"] is not None else "-"]]}
            else:
                title_, table, full = tests_kb.interpret_test(ctx, pt["key"], pt["stat"], pt["p"], pt["dist"], pt["text"], last_model, True)
                brief = full[-1:]
            sec = _section("test", title_ + (f" – модель {last_model.number}" if last_model and pt["key"] not in ("adf", "kpss", "coint") else ""))
            sec["test_key"] = pt["key"]
            sec["reject"] = pt["p"] is not None and pt["p"] < 0.05
            sec["model_idx"] = last_model.idx if last_model else None
            if table:
                sec["tables"].append(dict(table, caption=None))
            sec["full"], sec["brief"] = full, brief
            sections.append(sec)
        elif kind == "summary":
            rows = parse_summary(text)
            if not rows:
                warnings.append(f"{where}: не удалось разобрать описательную статистику.")
                continue
            metas = {r["var"]: VarMeta(r["var"], labels.get(r["var"], ""), overrides.get(r["var"])) for r in rows}
            sec = _section("summary", "Описательная статистика")
            sec["tables"].append(dict(tables.summary_table(rows), caption="Описательная статистика (Gretl)"))
            sec["full"] = style.summary_text(ctx, rows, metas, True)
            sec["brief"] = style.summary_text(ctx, rows, metas, False)
            sections.append(sec)
        elif kind == "forecast":
            t = to_en(normalize(text))
            t = re.sub(r"(\w+?)\s*прогнозирование", r"\1    prediction", t).replace("Ст. ошибка", "std. error").replace("ст. ошибка", "std. error")
            t = re.sub(r"^\s*(Набл\.|Obs)\s+", "  ", t, flags=re.M)
            t = re.sub(r"\(\s*(" + NUM + r"),\s*(" + NUM + r")\s*\)", r"\1 - \2", t)
            t = re.sub(r"(?<=\S)[ \t]+(?:не определено|NA)[ \t]+", " " * 10, t)   # прогноз вне выборки
            t = re.sub(r"использовано наблюдений\s*-\s*(\d+)", r"using \1 observations", t)
            fc = tables.parse_fcast(t)
            if not fc["rows"]:
                warnings.append(f"{where}: не найдены строки прогноза.")
                continue
            if not fc.get("depvar") and last_model:
                fc["depvar"] = last_model.depvar
            sec = _section("forecast", "Прогноз" + (f" по модели {last_model.number}" if last_model else ""))
            sec["tables"].append(dict(tables.fcast_table(fc), caption="Прогнозные значения (Gretl)"))
            sec["full"] = style.forecast_text(ctx, fc, last_model, True)
            sec["brief"] = [p for p in style.forecast_text(ctx, fc, last_model, False) if p.startswith("Вывод")][:6]
            sections.append(sec)
        elif kind == "corr":
            names, mat, n = parse_corr(text)
            if not names or not mat:
                warnings.append(f"{where}: не удалось разобрать корреляционную матрицу.")
                continue
            tbl, _ = interpret_corr_matrix(ctx, names, mat, n)
            metas = {v: VarMeta(v, labels.get(v, ""), overrides.get(v)) for v in names}
            P = style.corr_text(ctx, names, mat, n, metas)
            sec = _section("corr", "Корреляционная матрица")
            sec["tables"].append(dict(tbl, caption="Коэффициенты корреляции"))
            sec["full"], sec["brief"] = P, P
            sections.append(sec)
        else:
            if not quiet:
                warnings.append(f"{where}: не удалось определить, что это за вывод Gretl.")

    comp = _compare_models(ctx, ms)
    if comp:
        sections.append(comp)
    concl = _conclusions(ctx, sections, ms)
    if concl:
        sections.append(concl)
    unverified = []
    for k, s in enumerate(sections, 1):
        s["id"] = f"s{k}"
        for mode in ("brief", "full"):
            s[mode] = [_tidy(p) for p in s[mode]]
            for p in s[mode]:
                bad = verify_numbers(p, ctx.facts)
                if bad:
                    unverified.append({"section": s["id"], "numbers": bad})
            s[mode] = [fmt.typo(p) for p in s[mode]]
        s["title"] = fmt.typo(s["title"])
    for u in unverified:
        title_u = next((s["title"] for s in sections if s["id"] == u["section"]), u["section"])
        msg = f"Раздел «{title_u}»: числа {', '.join(u['numbers'])} не найдены во вставленном тексте – проверьте их."
        if msg not in warnings:
            warnings.append(msg)
    result = {"title": title or "Эконометрический анализ",
              "generated": datetime.datetime.now().isoformat(timespec="seconds"),
              "gretl_version": None, "data_file": None, "dataset": {}, "warnings": warnings,
              "sections": sections, "variables": {},
              "verification": {"unverified": unverified}, "outdir": outdir}
    with open(os.path.join(outdir, "result.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=1,
                  default=lambda o: None if isinstance(o, float) and (math.isnan(o) or math.isinf(o)) else str(o))
    return result
