"""Формулировки: структура студенческой работы и статистически корректные решения."""
import pytest

from conftest import assert_clean, dumps, fixture, text_of
from gretl_analytics.core import stats


def test_model_text(analyze):
    T = text_of(analyze(fixture("ru", "data3-1.txt")))
    for v in ["0,138750", "0,820522", "54,86051", "7,407", "317,49", "607,4", "484,8"]:
        assert v in T, v
    assert "при увеличении жилой площади на 1 кв. фут цена продажи в среднем увеличивается на 0,1388 тыс. долл." in T
    assert "t(12) – число степеней свободы (14 − 1 − 1)" in T
    assert "Критическое значение = 2,17881" in T              # двустороннее t-критическое
    assert "Критическое значение = 4,74723" in T              # F-критическое
    assert "прогноз для наблюдения 15 составляет 607,4" in T  # точечный прогноз, а не граница интервала


def test_hypothesis_decisions(analyze):
    T = text_of(analyze(fixture("ru", "data7-24.txt")))
    assert "F(3, 217) = 2,37761" in T
    assert "нулевая гипотеза не отвергается" in T and "p-значение 0,0708 > 0,05" in T
    T = text_of(analyze(fixture("ru", "data3-12.txt")))
    assert "F(2, 29) = 24,8063" in T and "произошёл структурный сдвиг" in T and "p-значение < 0,0001" in T
    assert "Расширенная регрессия для теста Чоу" in T


def test_reset_rejection_reaches_conclusions(analyze):
    r = analyze(fixture("en", "bjg.txt"))
    assert "спецификация модели признаётся неадекватной" in text_of(r)
    assert "ошибка функциональной формы (RESET)" in r["sections"][-1]["full"][1]


def test_seasonal_model_and_forecast(analyze):
    r = analyze(fixture("ru", "bjg.txt"), glossary=[{"var": "g", "ru": "число авиапассажиров", "unit": "тыс. чел."}])
    T = text_of(r)
    assert "35,1\u00a0%" in T and "январе (базовый период)" in T
    assert "прогноз построен на 12 наблюдений вперёд, с 1961:01 по 1961:12" in T
    assert_clean(r)


@pytest.mark.parametrize("lang,name", [("ru", "data3-12.txt"), ("ru", "data7-3.txt"), ("ru", "bjg.txt"),
                                       ("en", "data7-3.txt"), ("en", "bjg.txt")])
def test_no_em_dashes(analyze, lang, name):
    r = analyze(fixture(lang, name), glossary=[{"var": "price", "ru": "цена", "unit": "тыс. долл."}])
    assert "\u2014" not in dumps(r)  # длинное тире


def test_critical_values_match_gretl():
    """Совпадают с critical() Gretl 2026c."""
    assert stats.t_crit(0.025, 12) == pytest.approx(2.17881, abs=1e-5)
    assert stats.t_crit(0.025, 7) == pytest.approx(2.36462, abs=1e-5)
    assert stats.f_crit(0.05, 1, 12) == pytest.approx(4.74723, abs=1e-5)
    assert stats.f_crit(0.05, 6, 7) == pytest.approx(3.86597, abs=1e-5)
    assert stats.f_crit(0.05, 2, 29) == pytest.approx(3.32765, abs=1e-5)


def test_unit_root_tests_agree(analyze):
    """ADF и KPSS из одного вывода: ряд нестационарен (KPSS отвергает H0 по границе p < 0,01)."""
    r = analyze(fixture("en", "bjg.txt"))
    tests = {s["test_key"]: " ".join(s["full"]) for s in r["sections"] if s["kind"] == "test"}
    assert "autocorr" not in tests, "строка про автокорреляцию в выводе ADF не должна становиться тестом"
    assert "τ_c(1) = −1,95198" in tests["adf"] and "ряд, вероятно, нестационарен" in tests["adf"]
    assert "p < 0,01" in tests["kpss"] and "гипотеза о стационарности отвергается" in tests["kpss"]
    assert_clean(r)


def test_logit_reads_z_and_slope(analyze):
    """У логита в Gretl столбцы z и наклон без p-значения: p считается по z, наклон не путается с p."""
    r = analyze(fixture("en", "logit.txt"))
    T = text_of(r)
    assert [s["kind"] for s in r["sections"]] == ["model", "conclusions"]
    assert "Значимые переменные (на уровне 5\u00a0%): GPA, PSI." in T
    assert "Предельный эффект в точке средних значений регрессоров (столбец slope в Gretl) равен 0,5339" in T
    assert_clean(r)


def test_typography(analyze):
    """Русская научная типографика: минус, тире в диапазонах, степень десяти, пробел перед %."""
    from gretl_analytics.core.fmt import typo
    assert typo("p = 3,76e-17; 1,2e+05") == "p = 3,76·10⁻¹⁷; 1,2·10⁵"
    assert typo("1949:01-1960:12, 1-32, l_price-1") == "1949:01–1960:12, 1–32, l_price-1"
    assert typo("90,1% и 5%-ном") == "90,1 % и 5%-ном"
    r = analyze(fixture("ru", "data3-12.txt"))
    T = text_of(r)
    assert "наблюдения 1962–1994" in T and "Дарбина–Уотсона" in T
    assert "показывает, что коэффициент при" not in T          # нет повтора в выводе по тренду
    assert "модель ?" not in T
    assert "e-1" not in "\n".join(p for s in r["sections"] for p in s["full"])
