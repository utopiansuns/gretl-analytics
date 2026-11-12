"""Разбор текста, скопированного из Gretl: русский и английский интерфейс, таблицы из Word.

split_text() делит вставку на части (модель, тест, статистика, прогноз, корреляции, описание данных),
detect_kind() определяет тип части, parse_*() извлекают из неё числа. Интерпретации здесь нет.
"""
import re

from . import stats

NUM = r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?"

# Русский вывод Gretl -> английские формулировки (переводы взяты из gretl.mo)
RU2EN = [
    ("Тест Чоу на наличие структурных сдвигов в точке", "Chow test for structural break at observation"),
    ("Исключение переменных улучшило", "Omitting variables improved"),
    ("Добавление переменных улучшило", "Adding variables improved"),
    ("информационных критериев", "information criteria"),
    (" из ", " of "),
    ("параметры регрессии нулевые для переменных", "the regression parameters are zero for the variables"),
    ("параметры регрессии нулевые", "the regression parameters are zero for the variables"),
    ("на автокорреляцию вплоть до порядка", "for autocorrelation up to order"),
    ("Хи-квадрат", "Chi-square"),
    ("Тестовая статистика", "Test statistic"), ("тестовая статистика", "test statistic"),
    ("асимпт. p-значение", "asymptotic p-value"),
    ("Для 95% доверительных интервалов", "For 95% confidence intervals"),
    ("Для 90% доверительных интервалов", "For 90% confidence intervals"),
    ("Для 99% доверительных интервалов", "For 99% confidence intervals"),
    ("Средняя абсолютная процентная ошибка (MAPE)", "Mean Absolute Percentage Error"),
    ("Средняя процентная ошибка (MPE)", "Mean Percentage Error"),
    ("Средняя абсолютная ошибка (MAE)", "Mean Absolute Error"),
    ("Корень из средней квадратичной ошибки (RMSE)", "Root Mean Squared Error"),
    ("Средняя ошибка (ME)", "Mean Error"),
    ("U-cтатистика Тейла (Theil's U)", "Theil's U2"), ("U-статистика Тейла (Theil's U)", "Theil's U2"),
    ("Пропорция смещения, UM", "Bias proportion, UM"), ("Пропорция регрессии, UR", "Regression proportion, UR"),
    ("Пропорция возмущений, UD", "Disturbance proportion, UD"),
    ("Статистика для оценки прогноза", "Forecast evaluation statistics"),
]

STAT_LABELS = [
    (r"Среднее завис\. перемен|Mean dependent var", "ybar"), (r"Ст\. откл\. завис\. перем|S\.D\. dependent var", "sdy"),
    (r"Сумма кв\. остатков|Sum squared resid", "ess"), (r"Ст\. ошибка модели|S\.E\. of regression", "sigma"),
    (r"Исправ\. R-квадрат|Adjusted R-squared", "adjrsq"), (r"R-квадрат Макфаддена|McFadden R-squared", "mcfadden"),
    (r"(?<![\w.])R-квадрат(?! Макф)|(?<![\w ])R-squared", "rsq"),
    (r"[РP]-значение \(F\)|P-value\(F\)", "pvalue_F"),
    (r"Лог\. правдоподобие|Log-likelihood", "lnl"), (r"Крит\. Акаике|Akaike criterion", "aic"),
    (r"Крит\. Шварца|Schwarz criterion", "bic"), (r"Крит\. Хеннана-Куинна|Hannan-Quinn", "hqc"),
    (r"параметр rho|(?<!\w)rho(?!\w)", "rho"), (r"Стат\. Дарбина-Уотсона|Durbin-Watson", "dw"),
]

METHODS = [(r"^(МНК|OLS)$", "ols", "OLS"), (r"ВМНК|WLS", "wls", "WLS"), (r"Логит|Logit", "logit", "Logit"),
           (r"Пробит|Probit", "probit", "Probit"), (r"ARIMA|ARMA", "arima", "ARIMA"),
           (r"Двухшаговый|TSLS", "tsls", "TSLS"), (r"гетероскедастичн|Heteroskedasticity", "hsk", "Heteroskedasticity-corrected")]


def normalize(text):
    t = text.replace("\r\n", "\n").replace("\r", "\n").replace(" ", " ")
    t = t.replace("−", "-").replace("–", "-").replace("\u2014", "-")
    t = t.replace("р-значение", "p-значение").replace("Р-значение (F)", "P-значение (F)").replace("р-значения", "p-значения")
    # F(12,119) -> F(12, 119), чтобы не принять за десятичную запятую
    t = re.sub(r"\b(F|t|Chi-square|Хи-квадрат)\((\d+),(\d+)\)", r"\1(\2, \3)", t)
    t = re.sub(r"(?<=\d),(?=\d)", ".", t)
    return t


def to_en(t):
    for ru, en in RU2EN:
        t = t.replace(ru, en)
    return t


# ------------------------------------------------------------------ определение типа

def parse_data_desc(text):
    """Строки описания набора данных: «price = Sale price in thousands of dollars (Range 199.9 - 505)»."""
    labels = {}
    for line in text.split("\n"):
        m = re.match(r"^\s*([A-Za-z_]\w*)\s*=\s*(\S.*)$", line)
        if m:
            labels[m.group(1)] = m.group(2).strip()
        elif labels and line.strip() and line.startswith((" ", "\t")) and not re.match(r"^\s*\(?Range", line):
            last = list(labels)[-1]
            labels[last] += " " + line.strip()
    return labels


def detect_kind(text):
    t = normalize(text)
    if len(parse_data_desc(text)) >= 1 and not _coef_rows(t) and not re.search(r"Тест|Test|Среднее|Mean ", t):
        return "data"
    if re.search(r"прогнозировани|prediction|доверительный интервал|95% interval", t) and \
            re.search(r"\d+\s+-\s+" + NUM + r"|\(" + NUM + r", " + NUM + r"\)", t):
        return "forecast"
    if re.search(r"(Коэффициент|коэффициент|coefficient)[\s\S]{0,40}(Ст\. ошибка|ст\. ошибка|std\. error)", t) \
            and not re.search(r"(Тест|тест|test).{0,60}(Вайта|Уайта|White|Чоу|Chow|RESET|Рамсея)", t, re.I):
        return "model"
    if re.search(r"Тест|тест|Test|test|Нулевая гипотеза|Null hypothesis|Метод инфляционных|Variance Inflation|VIF", t):
        return "test"
    if re.search(r"Среднее|Mean\b", t) and re.search(r"Медиана|Median", t):
        return "summary"
    if re.search(r"корреляц|Correlation", t, re.I) or _corr_rows(t):
        return "corr"
    if _coef_rows(t):
        return "model"
    return "unknown"


# ------------------------------------------------------------------ разбиение общего текста

_KEEP = re.compile(r"^(Тест|Test|Нулевая|Null|Альтернативная|Тестовая|Исключение|Добавление|Статистика для|Для \d|"
                   r"Модель|Model|Зависимая|Dependent|Средн|Корень|Пропорция|U-|Неисправ|Unadjusted|Метод|"
                   r"Расширен|Augmented|Коэффициенты корреляции|Описательная|Summary|Набл|Obs|с константой|with constant|"
                   r"Стандартные ошибки|Robust|Приближенное|Асимпт)")
_TEST_HDR = re.compile(r"^(?:(?:Тест|Test)(?!овая|\s+statistic)\b|Неучт|Метод инфляционных|Variance Inflation|"
                       r"Расширенный тест|Augmented Dickey)", re.I)
_NULL_HDR = re.compile(r"^(Нулевая гипотеза|Null hypothesis)")


def _is_prose(s):
    """Строка с пояснениями студента (из Word), а не вывод Gretl."""
    if _KEEP.match(s):
        return False
    if re.match(r"^(Вывод|Итак|То есть|Таким образом|Следовательно|Проверим|Проверяем|Найд|Распределение Стьюдента)", s):
        return True
    words = re.findall(r"[А-Яа-яЁё]{3,}", s)
    return len(words) >= 5 and not re.search(r"\t|\s{3,}\S", s)


def split_text(text):
    """Разрезает вставленный целиком текст на фрагменты: модель, тест, статистика, прогноз…
    Возвращает [(вид или None, текст)]."""
    segs = []
    cur = None  # [kind, lines, nonblank, has_p]

    def start(kind):
        nonlocal cur
        cur = [kind, [], 0, False]
        segs.append(cur)

    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        s = normalize(raw).strip()
        if s and _is_prose(s):
            continue
        kind = cur[0] if cur else None
        new = None
        if re.match(r"^(Модель|Model) \d+:|^(Расширенная регрессия|Augmented regression)", s):
            new = "model"
        elif (_TEST_HDR.match(s) and not raw.startswith("  ")) or (len(s) < 90 and not raw[:1].isspace() and re.search(r"\b(test|тест)\b", s, re.I)
                                     and not re.search(r"statistic|p-value|p-значение|^Null|^Нулевая|"
                                                       r"Likelihood ratio|отношения правдоподобия", s, re.I)):
            new = "test"
        elif _NULL_HDR.match(s):
            if not (kind == "test" and not cur[3]):
                new = "test"
        elif re.match(r"^(Описательная статистика|Summary statistics)", s) or \
                (kind != "summary" and (re.search(r"Среднее.*Медиана|Mean.*Median", s))):
            new = "summary"
        elif re.match(r"^(Для \d+% доверительных|For \d+% confidence)", s) or \
                (kind != "forecast" and re.search(r"прогнозирование|\bprediction\b", s)):
            new = "forecast"
        elif re.match(r"^(Коэффициенты корреляции|Correlation [Cc]oefficients|Корреляционная матрица|Матрица корреляц)", s):
            new = "corr"
        elif kind in (None, "data") and re.match(r"^[A-Za-z_]\w*\s*=\s*[A-Za-zА-Яа-я(]", s) and re.search(r"[A-Za-zА-Яа-я]{3,}.*[A-Za-zА-Яа-я]{3,}", s.split("=", 1)[1]):
            if kind != "data":
                new = "data"
        if new and not (new == kind and cur[2] == 0):
            if not (new == "summary" and kind == "summary" and cur[2] <= 1):
                start(new)
        if cur is None:
            start(None)
        cur[1].append(raw)
        if s:
            cur[2] += 1
            if re.search(r"Test statistic|Тестовая статистика|TR\^2 =|LM =|= P\(|^F\(\d+, \d+\) = ", s):
                cur[3] = True
    out = []
    for kind, lines, _, _ in segs:
        t = "\n".join(lines).strip("\n")
        if not re.search(r"\d", t):
            continue
        out.append((kind, t))
    return out


# ------------------------------------------------------------------ модель

def _coef_rows(t):
    """Строки таблицы коэффициентов: (имя, [числа], звёздочки). p-значение может быть записано как «<0.0001»."""
    rows = []
    for line in t.split("\n"):
        m = re.match(rf"^\s*([A-Za-z_][\w]*)((?:\s+<?\s*{NUM}){{3,5}})\s*(\*{{0,3}})\s*$", line)
        if m:
            nums = re.findall(rf"<?\s*{NUM}", m.group(2))
            rows.append((m.group(1), [x.replace(" ", "") for x in nums], m.group(3)))
    return rows


def _num(x):
    """Число из ячейки; «<0.0001» превращается в 0.00005."""
    return 5e-5 if x.startswith("<") else float(x)


def parse_model(text):
    t = normalize(text)
    info = {"stats": {}}
    m = re.search(r"(?:Модель|Model) (\d+): (.+?), (?:использованы наблюдения|using observations) (\S+?)-(\S+?)(?=\s|$|\()", t)
    if m:
        info["number"], info["method"], info["obs_from"], info["obs_to"] = int(m.group(1)), m.group(2).strip(), m.group(3), m.group(4)
    mT = re.search(r"\((?:T|n) = (\d+)\)", t)
    m = re.search(r"(?:Зависимая переменная|Dependent variable): (\S+)", t)
    if m:
        info["depvar"] = m.group(1)
    # таблица коэффициентов заканчивается там, где начинаются статистики модели
    end = re.search(r"Среднее завис|Mean dependent var|Сумма кв\. остатков|Sum squared resid", t)
    rows = _coef_rows(t[:end.start()] if end else t)
    asym = bool(re.search(r"(?<![\w-])z(?![\w-])\s", t)) and not re.search(r"t-статистика|t-ratio", t)
    # логит и пробит в Gretl: коэффициент, ст. ошибка, z, наклон (предельный эффект), p-значения нет
    head = next((ln for ln in t.split("\n") if re.search(r"коэффициент|coefficient", ln, re.I)), "")
    slope_layout = bool(re.search(r"\b(slope|наклон)\b", head, re.I)) and not re.search(r"p-value|p-значение", head, re.I)
    names, b, se, pv, slopes = [], [], [], [], {}
    for name, nums, _stars in rows:
        if len(nums) < (3 if slope_layout else 4):
            continue
        names.append(name)
        b.append(_num(nums[0]))
        se.append(_num(nums[1]))
        if slope_layout:
            pv.append(2 * stats.norm_sf(abs(_num(nums[2]))))
            if len(nums) > 3:
                slopes[name] = _num(nums[3])
        else:
            pv.append(_num(nums[3]))
            if len(nums) > 4:
                slopes[name] = _num(nums[4])
    if not names:
        return None
    st = info["stats"]
    for line in t.split("\n"):
        for pat, key in STAT_LABELS:
            mm = re.search(rf"(?:{pat})\s+({NUM})", line)
            if mm and key not in st:
                st[key] = float(mm.group(1))
        mF = re.search(rf"\bF\((\d+), (\d+)\)\s+({NUM})", line)
        if mF:
            st["F"], st["F_df"] = float(mF.group(3)), (int(mF.group(1)), int(mF.group(2)))
    mc = re.search(r"(?:Количество 'корректно предсказанных' случаев|Number of cases 'correctly predicted') = (\d+) \(([\d.]+)%\)", t)
    if mc:
        st["correct_n"], st["correct_pct"] = int(mc.group(1)), float(mc.group(2))
    ml = re.search(rf"(?:Критерий отношения правдоподобия|Likelihood ratio test): Chi-square\((\d+)\) = ({NUM}) \[({NUM})\]", to_en(t))
    if ml:
        st["lr"], st["lr_df"], st["lr_p"] = float(ml.group(2)), int(ml.group(1)), float(ml.group(3))
    if slopes:
        info["slopes"] = slopes
    method = info.get("method", "")
    cmd, meth_en = "ols", "OLS"
    for pat, c, en in METHODS:
        if re.search(pat, method):
            cmd, meth_en = c, en
            break
    if not method:
        info["method"] = "OLS"
    else:
        info["method"] = meth_en if cmd in ("ols", "wls", "logit", "probit", "tsls") else method
    k = len(names)
    T = int(mT.group(1)) if mT else None
    if T is None and info.get("obs_from", "").isdigit() and info.get("obs_to", "").isdigit():
        T = int(info["obs_to"]) - int(info["obs_from"]) + 1
    if T is None and "F_df" in st:
        T = st["F_df"][1] + k
    df = (T - k) if T else 0
    bundle = {"coeff": b, "stderr": se, "parnames": names, "depvar": info.get("depvar", "y"), "T": T or 0,
              "df": df, "command": cmd, "asymptotic": 1 if (asym or cmd in ("logit", "probit")) else 0}
    ts = bool(mT) or bool(re.search(r"\d{4}:\d{1,2}", info.get("obs_from", "")))
    pd = 1
    if re.search(r":\d{2}$", info.get("obs_from", "")):
        pd = 12
    elif re.search(r":\d$", info.get("obs_from", "")):
        pd = 4
    return {"bundle": bundle, "info": info, "pvalues": dict(zip(names, pv)),
            "dsinfo": {"datatype": 2 if ts else 1, "pd": pd}}


# ------------------------------------------------------------------ тесты

TEST_KEYS = [
    (r"инфляцион|Variance Inflation|\bVIF\b", "vif"),
    (r"Чоу|Chow", "chow"), (r"RESET|Рамсея", "reset"),
    (r"Коэнкер|Koenker", "koenker"), (r"Бройша-П[эа]гана|Breusch-Pagan", "bp"),
    (r"Дики-Фуллера|Dickey-Fuller", "adf"), (r"KPSS", "kpss"),
    (r"Вайта|Уайта|White", "white"), (r"Бройша-Годфри|Breusch-Godfrey|автокорреляц|autocorrelation", "autocorr"),
    (r"ARCH", "arch"), (r"QLR|Квандт", "qlr"), (r"CUSUMSQ", "cusumsq"), (r"CUSUM", "cusum"),
    (r"Дики-Фуллера|Dickey-Fuller", "adf"), (r"KPSS", "kpss"), (r"коинтеграц|cointegration", "coint"),
    (r"Добавление переменных|Adding variables|добавлени", "add"),
    (r"параметры регрессии нулевые|regression parameters are zero|Исключение переменных|Omitting variables", "omit"),
    (r"нормальн|normal", "normality"), (r"ограничени|restriction", "restrict"),
    (r"Хаусман|Hausman", "hausman"),
]


def parse_test(text):
    t = to_en(normalize(text))
    key = None
    for pat, k in TEST_KEYS:
        if re.search(pat, t, re.I):
            key = k
            break
    stat, p, dist = None, None, {}
    m = re.search(rf"P\((F|Chi-square)\((\d+)(?:, (\d+))?\) > ({NUM})\) = ({NUM})", t)
    if m:
        stat, p = float(m.group(4)), float(m.group(5))
        dist = {"dist": "F", "df": (int(m.group(2)), int(m.group(3)))} if m.group(1) == "F" else {"dist": "chi2", "df": (int(m.group(2)),)}
    else:
        m2 = re.search(rf"(tau_\w+\(\d+\)) = ({NUM})", t)
        m = None if m2 else (re.search(rf"\b(F)\((\d+), (\d+)\) = ({NUM})", t) or re.search(rf"(Chi-square)\((\d+)\)() = ({NUM})", t))
        if m2:
            stat = float(m2.group(2))
            dist = {"dist": "tau", "label": m2.group(1)}
        elif m:
            stat = float(m.group(4))
            dist = {"dist": "F", "df": (int(m.group(2)), int(m.group(3)))} if m.group(1) == "F" else {"dist": "chi2", "df": (int(m.group(2)),)}
        if stat is None:
            m3 = re.search(rf"(?:Test statistic|test statistic|TR\^2|LMF|LM)\s*:?\s*\w*\s*=\s*({NUM})", t)
            if m3:
                stat = float(m3.group(1))
        mp = re.search(rf"(?:p-значение|p-value)\s*=?\s*({NUM})", t, re.I)
        if mp:
            p = float(mp.group(1))
        elif re.search(r"p-значение\s*=?\s*0[.]?0+\b|p-value\s*=?\s*<", t, re.I):
            p = 5e-5
    return {"key": key or "unknown", "stat": stat, "p": p, "dist": dist, "text": t}


# ------------------------------------------------------------------ описательная статистика

SUM_COLS = [(r"Среднее|Mean", "mean"), (r"Медиана|Median", "median"), (r"Минимум|Minimum", "min"),
            (r"Максимум|Maximum", "max"), (r"Ст\. откл\.|Std\. Dev\.", "sd"), (r"Вариация|C\.V\.", "cv"),
            (r"Асимметрия|Skewness", "skew"), (r"Эксцесс|Ex\. kurtosis", "exkurt"),
            (r"95% пер-ль|95% perc\.", "p95"), (r"5% пер-ль|5% perc\.", "p05"),
            (r"Межкв|IQ range", "iqr"), (r"Пропущ|Missing", "missing")]


def parse_summary(text):
    t = normalize(text)
    rows = {}
    order = []
    cols = None
    for line in t.split("\n"):
        if not line.strip():
            continue
        found = []
        for pat, key in SUM_COLS:
            for m in re.finditer(pat, line):
                if key == "p05" and line[max(0, m.start() - 1):m.start()] == "9":
                    continue
                found.append((m.start(), key))
        nums = re.findall(NUM, line)
        mv = re.match(rf"^\s*([A-Za-z_]\w*)\s+((?:{NUM}\s*)+)$", line)
        if found and not mv:
            # «вертикальный» формат одной переменной: «Среднее   317,49»
            if len(found) == 1 and len(nums) == 1 and re.search(rf"\s{NUM}\s*$", line):
                rows.setdefault("_single", {})[found[0][1]] = float(nums[0])
                continue
            seen = set()
            cols = [k for _, k in sorted(found) if not (k in seen or seen.add(k))]
            continue
        if mv and cols:
            vals = re.findall(NUM, mv.group(2))
            name = mv.group(1)
            if name not in rows:
                rows[name] = {}
                order.append(name)
            for k, v in zip(cols, vals):
                rows[name][k] = float(v)
    if "_single" in rows:
        mvar = re.search(r"(?:для переменной|for the variable) '(\w+)'", t)
        name = mvar.group(1) if mvar else "x"
        rows[name] = rows.pop("_single")
        order.append(name)
    out = []
    for n in order:
        r = rows[n]
        iqr = r.get("iqr", float("nan"))
        out.append({"var": n, "mean": r.get("mean", float("nan")), "median": r.get("median", float("nan")),
                    "min": r.get("min", float("nan")), "max": r.get("max", float("nan")), "sd": r.get("sd", float("nan")),
                    "skew": r.get("skew", float("nan")), "exkurt": r.get("exkurt", float("nan")),
                    "p05": r.get("p05", float("nan")), "p95": r.get("p95", float("nan")),
                    "q1": 0.0, "q3": iqr, "n": float("nan"), "missing": r.get("missing", 0.0)})
    return out


# ------------------------------------------------------------------ корреляции

def _corr_rows(t):
    return [l for l in t.split("\n") if re.match(rf"^\s*(?:{NUM}\s+)+[A-Za-z_]\w*\s*$", l)]


def parse_corr(text):
    t = normalize(text)
    names, mat = [], {}
    # формат Gretl: верхний треугольник, имя переменной в конце строки
    rows = _corr_rows(t)
    if rows:
        header = None
        for line in t.split("\n"):
            toks = line.split()
            if toks and all(re.match(r"^[A-Za-z_]\w*$", x) for x in toks) and len(toks) >= 2:
                header = toks
        if header:
            names = header
            for line in rows:
                toks = line.split()
                name, vals = toks[-1], [float(x) for x in toks[:-1]]
                i = names.index(name) if name in names else None
                if i is None:
                    continue
                for j, v in enumerate(vals):
                    col = names[len(names) - len(vals) + j]
                    mat[(name, col)] = mat[(col, name)] = v
    else:
        # полная матрица: «имя  числа…»
        lines = [l for l in t.split("\n") if l.strip()]
        for line in lines:
            toks = line.split()
            if toks and all(re.match(r"^[A-Za-z_]\w*$", x) for x in toks):
                names = toks
        for line in lines:
            m = re.match(rf"^\s*([A-Za-z_]\w*)\s+((?:{NUM}\s*)+)$", line)
            if m and names:
                vals = [float(x) for x in re.findall(NUM, m.group(2))]
                for col, v in zip(names, vals):
                    mat[(m.group(1), col)] = mat[(col, m.group(1))] = v
    mn = re.search(r"для n = (\d+)|for n = (\d+)|n = (\d+)", t)
    n = int(next(g for g in mn.groups() if g)) if mn else None
    return names, mat, n
