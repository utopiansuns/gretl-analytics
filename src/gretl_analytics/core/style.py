"""Тексты в формате студенческих работ по эконометрике («Вывод: …», «Распределение Стьюдента», проверка F).

Привычная структура сохраняется, но типичные ошибки таких работ исключены:
  * критическое t берётся для двусторонней проверки H0: β = 0 (вероятность 0,05 в двух хвостах);
  * незначимым коэффициентам не приписывается влияние;
  * при p > 0,05 гипотеза не отвергается;
  * прогноз – это точечное значение, а не граница интервала.
"""
import math
import re

from . import stats
from .ctx import sig_level, strength
from .meta import MONTHS_NOM
from .models import _effect_sentence, _base_periods, _base_loc


def _fit_word(r2):
    if r2 >= 0.8:
        return "хорошо описывает данные"
    if r2 >= 0.5:
        return "удовлетворительно описывает данные"
    if r2 >= 0.3:
        return "описывает данные слабо"
    return "плохо описывает данные"


def _season_name(p, pd):
    if pd == 12 and 1 <= p <= 12:
        return MONTHS_NOM[p - 1].capitalize()
    if pd == 4:
        return f"{p}-й квартал"
    return f"Период {p}"


def _short_effect(ctx, m, c):
    x = c.meta
    if x.kind == "dummy" and not m.limdep and m.y.kind != "log" and x.gen.startswith("наличия "):
        what = x.gen[len("наличия "):]
        return (f"При наличии {what} {m.y.nom} в среднем на {ctx.abs_n(c.b)} {m.y.unit_or()} "
                f"{'выше' if c.b > 0 else 'ниже'}, чем при отсутствии {what}.")
    s = _effect_sentence(ctx, m, c, simple=len(m.slopes()) == 1)
    return s.replace(" при прочих равных условиях", "").replace(", при одинаковом значении тренда", "")


def _strip_dot(e):
    """Убирает точку в конце предложения, но не у сокращений («тыс. долл.»)."""
    if e.endswith(".") and not re.search(r"(?:^|\s)[а-я]{1,5}\.$", e):
        return e[:-1]
    return e


def model_text(ctx, m, full=True):
    P = []
    slopes = m.slopes()
    sig = [c for c in slopes if sig_level(c.p) and sig_level(c.p) <= 5]
    nsig = [c for c in slopes if c not in sig]
    seasonal = any(c.meta.kind == "season" for c in slopes)

    # 1. Вывод по коэффициентам
    if not seasonal:
        effects = []
        for c in slopes:
            e = _short_effect(ctx, m, c)
            e = e[0].lower() + e[1:]
            if c in nsig:
                e = _strip_dot(e) + " (но коэффициент незначим, поэтому этот эффект статистически не подтверждён)"
            effects.append(_strip_dot(e))
        if len(slopes) == 1:
            x0 = slopes[0].meta
            at = f"{x0.case('loc')} ({slopes[0].name})" if x0.nom != slopes[0].name and x0.kind == "level" else slopes[0].name
            # эффект тренда уже начинается с «коэффициент при тренде показывает, что …»
            lead = "" if effects[0].startswith("коэффициент при") else f"коэффициент при {at} показывает, что "
            P.append(_strip_dot(f"Вывод: {lead}{effects[0]}") + ".")
        else:
            P.append(_strip_dot("Вывод по модели: " + "; ".join(effects)) + ".")
        if len(slopes) > 1:
            if sig:
                P.append("Значимые переменные (на уровне 5%): " + ", ".join(f"{c.meta.nom if c.meta.nom != c.name else c.name}" for c in sig) + ".")
            else:
                P.append("Ни один коэффициент не значим на уровне 5%.")
    else:
        trend = [c for c in slopes if c.meta.kind == "trend"]
        for c in trend:
            P.append(_short_effect(ctx, m, c).rstrip(".") + f" (t = {ctx.t(c.t)}, {ctx.p(c.p)}).")
        bp = _base_periods(m)
        base = _base_loc(bp[0], m.pd) if len(bp) == 1 else "базовом периоде"
        P.append(f"Коэффициенты при фиктивных переменных показывают, насколько {m.y.nom if m.y.kind != 'log' else 'показатель'} "
                 f"в данном периоде {'(в процентах) ' if m.y.kind == 'log' else ''}выше или ниже, чем в {base} (базовый период), "
                 f"при одинаковом значении тренда.")
        s_sig = [c for c in slopes if c.meta.kind == "season" and c in sig]
        s_ns = [c for c in slopes if c.meta.kind == "season" and c not in sig]
        if s_sig:
            P.append("Статистически значимыми на уровне 5% оказались:")
            for c in s_sig:
                P.append(f"{_season_name(c.meta.period, m.pd)}: коэффициент {ctx.n(c.b, sig=4)}, {ctx.p(c.p).replace('p =', 'p-значение').replace('p <', 'p-значение <')}. "
                         + _short_effect(ctx, m, c).split(" (100")[0].rstrip(".") + ".")
        if s_ns:
            P.append("Статистически незначимыми оказались:")
            for c in s_ns:
                P.append(f"{_season_name(c.meta.period, m.pd)}: коэффициент {ctx.n(c.b, sig=4)}, {ctx.p(c.p).replace('p =', 'p-значение').replace('p <', 'p-значение <')}.")

    # 2. Распределение Стьюдента
    if full and not m.asymptotic and m.df > 0 and not seasonal:
        tc = stats.t_crit(0.025, m.df)
        k = len(slopes)
        lines = ["Распределение Стьюдента:",
                 f"t({ctx.int(m.df)}) – число степеней свободы ({ctx.int(m.T)} − {ctx.int(k)} − 1)",
                 "Двусторонняя вероятность = 0,05",
                 f"Критическое значение = {ctx.n(tc, nd=5)}"]
        P.append("\n".join(lines))
        for c in slopes:
            rel = ">" if abs(c.t) > tc else "<"
            verdict = ("гипотеза H0: β = 0 отвергается, коэффициент значим" if abs(c.t) > tc
                       else "гипотеза H0: β = 0 не отвергается, коэффициент незначим")
            P.append(f"{c.meta.ref()}: |t| = {ctx.t(abs(c.t))} {rel} {ctx.n(tc, nd=2)} – {verdict}.")
        if len(slopes) == 1:
            c = slopes[0]
            nm = c.meta.nom if c.meta.nom != c.name else c.name
            ynm = m.y.nom if m.y.nom != m.depvar else m.depvar
            P.append(f"То есть связь между показателями «{nm}» и «{ynm}» статистически значима." if abs(c.t) > tc
                     else f"То есть статистически значимой связи между {c.meta.case('ins')} и {m.y.case('ins')} по этим данным не обнаружено.")
    elif full and m.asymptotic:
        for c in slopes:
            P.append(f"{c.meta.ref()}: z = {ctx.t(c.t)}, {ctx.p(c.p)} – коэффициент {'значим' if sig_level(c.p) and sig_level(c.p) <= 5 else 'незначим'} на уровне 5%.")

    # 3. R²
    s = m.stats
    if m.limdep:
        if "mcfadden" in s:
            P.append(f"Псевдо-R² Макфаддена = {ctx.n(s['mcfadden'], nd=4)} (это не доля объяснённой дисперсии, как в МНК).")
        if "correct_pct" in s:
            P.append(f"Модель верно предсказывает {ctx.n(s['correct_pct'], nd=1)}% наблюдений.")
    elif "rsq" in s:
        P.append(f"Коэффициент детерминации (R-квадрат = {ctx.n(s['rsq'], nd=6)}) показывает, что модель объясняет "
                 f"{ctx.pct(100 * s['rsq'])} вариации {m.y.gen}, то есть {_fit_word(s['rsq'])}.")

    # 4. F-тест
    if "F" in s and "F_df" in s and m.has_const:
        d1, d2 = s["F_df"]
        fc = stats.f_crit(0.05, d1, d2)
        pF = s.get("pvalue_F")
        rej = s["F"] > fc
        if full:
            P.append("\n".join([
                "Проверим гипотезу о значимости уравнения в целом",
                f"F({ctx.int(d1)}, {ctx.int(d2)}) = {ctx.stat(s['F'])} – F-наблюдаемое",
                "Правосторонняя вероятность = 0,05",
                f"Критическое значение = {ctx.n(fc, nd=5)}",
                f"F-наблюдаемое ({ctx.n(s['F'], nd=2)}) {'>' if rej else '<'} F-критическое ({ctx.n(fc, nd=2)})"]))
        txt = ("Вывод: гипотеза о незначимости уравнения отвергается, уравнение значимо в целом"
               if rej else "Вывод: гипотеза о незначимости уравнения не отвергается, уравнение в целом незначимо")
        if pF is not None and not math.isnan(pF):
            from .models import _pF
            txt += f" (p-значение (F) = {ctx.raw(_pF(pF))} {'<' if pF < 0.05 else '>'} 0,05)"
        P.append(txt + ".")

    # 5. Автокорреляция для рядов
    if m.timeseries and "dw" in s:
        dw = s["dw"]
        if dw < 1.5:
            P.append(f"Однако статистика Дарбина–Уотсона равна {ctx.n(dw, nd=2)}, что указывает на сильную положительную "
                     f"автокорреляцию остатков; поэтому стандартные ошибки могут быть занижены и выводы о значимости следует делать с осторожностью.")
        elif dw > 2.5:
            P.append(f"Статистика Дарбина–Уотсона равна {ctx.n(dw, nd=2)}, что указывает на отрицательную автокорреляцию остатков.")
        else:
            P.append(f"Статистика Дарбина–Уотсона равна {ctx.n(dw, nd=2)} – близка к 2, признаков автокорреляции остатков нет.")
    return P


def model_brief(ctx, m):
    full = model_text(ctx, m, full=False)
    return [p for p in full if not p.startswith(("Статистически", "Коэффициенты при фиктивных"))
            and not (":" in p[:12] and "коэффициент" in p[:30])]


# ------------------------------------------------------------------ тесты

def test_text(ctx, key, kb, stat, p, dist_label, extra, full=True):
    """kb – запись tests_kb.KB: (название, H0, H1, вывод при отклонении, при неотклонении, последствия)."""
    name, h0, h1, rej, notrej, conseq = kb
    P = []
    reject = p is not None and p < 0.05
    if key in ("omit", "add") and extra.get("vars"):
        P.append(f"Нулевая гипотеза: параметры регрессии при переменных {extra['vars']} равны нулю.")
    elif key == "chow" and extra.get("break"):
        P.append(f"{name} в точке {ctx.raw(extra['break'])}. Нулевая гипотеза: {h0}.")
    else:
        P.append(f"{name}. Нулевая гипотеза: {h0}.")
    line = f"Тестовая статистика: {dist_label + ' = ' if dist_label else ''}{ctx.n(stat, sig=6)}"
    if p is not None:
        line += (", p-значение < " + ctx.raw("0,0001") if p < 1e-4 else f", p-значение {ctx.pv(p)} {'<' if reject else '>'} 0,05")
    P.append(line + ".")
    if full and dist_label.startswith(("F(", "χ²(")):
        from .tests_kb import _crit
        d = extra.get("_dist")
        c = _crit(d) if d else None
        if c:
            P.append(f"Критическое значение = {ctx.n(c, nd=5)}; {ctx.n(stat, nd=2)} {'>' if stat > c else '<'} {ctx.n(c, nd=2)}, "
                     f"то есть наблюдаемое значение {'больше' if stat > c else 'меньше'} критического.")
    if key in ("omit",):
        P.append("Вывод: " + ("нулевая гипотеза отвергается: эти переменные совместно значимы, исключать их не следует."
                              if reject else "нулевая гипотеза не отвергается: данные переменные не вносят статистически значимого вклада в модель, и их исключение обосновано."))
    elif key == "chow":
        when = f" в точке {ctx.raw(extra['break'])}" if extra.get("break") else ""
        P.append("Вывод: " + (f"гипотеза о равенстве коэффициентов отвергается, то есть{when} действительно произошёл структурный сдвиг."
                              if reject else f"гипотеза о равенстве коэффициентов не отвергается, структурного сдвига{when} нет – можно строить общую регрессию."))
    else:
        P.append("Вывод: " + (f"гипотеза отвергается: {rej}." if reject else f"гипотеза не отвергается: {notrej}."))
    if extra.get("ic"):
        a, b = extra["ic"]
        verb = "Исключение" if key == "omit" else "Добавление"
        P.append(f"{verb} переменных улучшило {ctx.int(a)} из {ctx.int(b)} информационных критериев.")
    if full and reject and conseq:
        P.append("Что это значит: " + conseq)
    return P


# ------------------------------------------------------------------ описательная статистика

def summary_text(ctx, rows, metas, full=True):
    parts = []
    for r in rows:
        mv = metas.get(r["var"])
        nm = mv.nom if mv and mv.nom != r["var"] else r["var"]
        u = f" {mv.unit}" if mv and mv.unit else ""
        parts.append(f"{nm} – от {ctx.g(r['min'], 5)} до {ctx.g(r['max'], 5)}{u} (в среднем {ctx.g(r['mean'], 5)})")
    P = ["Вывод: " + "; ".join(parts) + "."]
    if full:
        for r in rows:
            sk = r.get("skew")
            if sk is None or (isinstance(sk, float) and math.isnan(sk)):
                continue
            side = ("распределение близко к симметричному" if abs(sk) < 0.5 else
                    "распределение скошено вправо (среднее больше медианы)" if sk > 0 else
                    "распределение скошено влево (среднее меньше медианы)")
            cv = r["sd"] / abs(r["mean"]) if r.get("mean") else float("nan")
            mv = metas.get(r["var"])
            P.append(f"{mv.ref() if mv else r['var']}: медиана {ctx.g(r['median'], 5)}, стандартное отклонение {ctx.g(r['sd'], 5)}"
                     + (f", коэффициент вариации {ctx.pct(100 * cv)}" if not math.isnan(cv) else "")
                     + f"; асимметрия {ctx.n(sk, nd=3)} – {side}.")
    return P


# ------------------------------------------------------------------ прогноз

def forecast_text(ctx, fc, model, full=True):
    P = []
    unit = f" {model.y.unit}" if model and model.y.unit else ""
    outs = [r for r in fc["rows"] if r["actual"] is None]
    ins = [r for r in fc["rows"] if r["actual"] is not None]
    if len(outs) <= 3:
        for r in outs:
            _, pr, se, lo, hi = (ctx.raw(x) for x in r["s"])
            P.append(f"Вывод: прогноз для наблюдения {ctx.raw(r['obs'])} составляет {pr}{unit} "
                     f"(95% доверительный интервал: от {lo} до {hi}).")
    else:
        lo_r = min(outs, key=lambda r: r["pred"])
        hi_r = max(outs, key=lambda r: r["pred"])
        P.append(f"Вывод: прогноз построен на {ctx.int(len(outs))} наблюдений вперёд, с {ctx.raw(outs[0]['obs'])} по "
                 f"{ctx.raw(outs[-1]['obs'])}. Прогнозные значения меняются от {ctx.raw(lo_r['s'][1])}{unit} "
                 f"({ctx.raw(lo_r['obs'])}) до {ctx.raw(hi_r['s'][1])}{unit} ({ctx.raw(hi_r['obs'])}); "
                 f"значения и интервалы по каждому периоду приведены в таблице.")
    if outs and model and model.y.kind == "log":
        P.append("Прогноз получен для логарифма показателя; чтобы перейти к самому показателю, прогнозное значение нужно потенцировать (exp).")
    if outs:
        P.append("Прогнозом является именно точечное значение; границы интервала показывают диапазон, в котором значение окажется с вероятностью 95%."
                 " Если значения факторов для прогноза выходят за пределы выборки, прогноз является экстраполяцией и менее надёжен.")
    ev = fc.get("eval", {})
    es = {k: ctx.raw(v) for k, v in fc.get("eval_s", {}).items()}
    if ev:
        bits = []
        if "MAPE" in es:
            bits.append(f"средняя абсолютная процентная ошибка (MAPE) составляет {es['MAPE']}%")
        if "MAE" in es:
            bits.append(f"средняя абсолютная ошибка – {es['MAE']}{unit}")
        if "ME" in ev:
            bits.append("средняя ошибка близка к нулю" if abs(ev["ME"]) < 1e-6 * max(1, ev.get("RMSE", 1)) else f"средняя ошибка {es['ME']}")
        if bits:
            P.append("Вывод: " + ", ".join(bits) + ".")
        U = ev.get("U2", ev.get("U"))
        if U is not None:
            Us = es.get("U2", es.get("U"))
            P.append(f"U-статистика Тейла = {Us}: модель {'точнее' if U < 1 else 'хуже'} наивного прогноза «как в предыдущем периоде»"
                     + (" Это существенный недостаток." if U > 1 else "."))
        if full and all(k in es for k in ("UM", "UR", "UD")):
            P.append(f"UM = {es['UM']}, UR = {es['UR']}, UD = {es['UD']}: для прогноза внутри выборки по МНК-модели это получается "
                     f"автоматически и само по себе качество прогноза не доказывает.")
        if model and model.y.kind == "log" and "MAPE" in es:
            P.append("Так как прогнозируется логарифм, MAPE рассчитана для логарифма, а не для самого показателя.")
    if ins and full:
        inside = sum(1 for r in ins if r["lo"] <= r["actual"] <= r["hi"])
        P.append(f"Фактические значения попали в 95%-ный интервал в {ctx.int(inside)} случаях из {ctx.int(len(ins))}.")
    return P


# ------------------------------------------------------------------ корреляции

def corr_text(ctx, names, mat, n, metas=None):
    from . import tables
    metas = metas or {}

    def ins(v):
        mv = metas.get(v)
        return mv.case("ins") if mv and mv.nom != v else v

    P = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            r = mat.get((a, b))
            if r is None or math.isnan(r):
                continue
            s = (f"Вывод: между {ins(a)} и {ins(b)} наблюдается {strength(r)} {'положительная' if r > 0 else 'отрицательная'} "
                 f"линейная связь (r = {ctx.n(r, nd=4)})")
            if n and n > 2:
                pv = tables.corr_p(r, n)
                s += f", {'статистически значимая' if pv < 0.05 else 'статистически незначимая'} ({ctx.p(pv)})"
            P.append(s + ".")
    P.append("Корреляция показывает только наличие линейной связи, а не причину и следствие.")
    return P
