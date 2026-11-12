"""Разбор вставленного текста: части находятся автоматически, все числа подтверждены."""
import pytest

from conftest import assert_clean, fixture, kinds, text_of
from gretl_analytics.core.parsing import split_text

RU_EXPECT = {
    "data3-1.txt": ["data", "summary", "model", "forecast"],
    "data3-4.txt": ["data", "summary", "model", "forecast"],
    "data4-1.txt": ["data", "model", "forecast"],
    "data3-12.txt": ["model", "test"],
    "data7-3.txt": ["data", "model", "test"],
    "data7-24.txt": ["data", "model", "test"],
    "bjg.txt": ["model", "forecast"],
}


@pytest.mark.parametrize("name,expected", RU_EXPECT.items())
def test_ru_whole_paste(analyze, name, expected):
    r = analyze(fixture("ru", name))
    assert set(expected) <= set(kinds(r)), kinds(r)
    assert_clean(r)


def test_en_gretlcli_output(analyze):
    r = analyze(fixture("en", "data3-1.txt"))
    assert kinds(r)[:3] == ["summary", "model", "forecast"]
    assert_clean(r)

    r = analyze(fixture("en", "data7-3.txt"))
    assert [s.get("test_key") for s in r["sections"] if s["kind"] == "test"] == ["vif", "white", "omit", "normality"]
    assert kinds(r)[0] == "corr" and "r = 0,9058" in text_of(r)
    assert_clean(r)

    r = analyze(fixture("en", "data3-12.txt"))
    assert [s.get("test_key") for s in r["sections"] if s["kind"] == "test"] == ["chow", "autocorr"]
    assert_clean(r)


def test_split_text_kinds():
    assert [k for k, _ in split_text(fixture("en", "data7-3.txt")) if k] == \
        ["corr", "model", "test", "test", "test", "model", "test"]


def test_model_window_tests_are_separated(analyze):
    """Два теста подряд в окне модели русского Gretl становятся отдельными разделами."""
    text = fixture("ru", "data7-3.txt").split("Модель 2:")[0] + (
        "\nТест Вайта (White) на гетероскедастичность -\n"
        "  Нулевая гипотеза: гетероскедастичность отсутствует\n"
        "  Тестовая статистика: LM = 10,9708\n"
        "  р-значение = P(Хи-квадрат(8) > 10,9708) = 0,203357\n\n"
        "Тест на нормальность распределения остатков -\n"
        "  Нулевая гипотеза: ошибка имеет нормальное распределение\n"
        "  Тестовая статистика: Хи-квадрат(2) = 0,646\n"
        "  р-значение = 0,72392\n")
    r = analyze(text)
    assert {s["test_key"] for s in r["sections"] if s["kind"] == "test"} >= {"white", "normality"}
    assert_clean(r)


def test_student_prose_is_ignored(analyze):
    """Пояснения из Word не мешают разбору, и их числа не попадают в отчёт."""
    text = fixture("ru", "data3-1.txt").replace(
        "Модель 1: МНК",
        "Вывод: по таблице видно, что цены сильно различаются, разброс около 123,45 тыс.\n"
        "Распределение Стьюдента:\nКритическое значение = 9,87654\n\nМодель 1: МНК")
    r = analyze(text)
    assert "123,45" not in text_of(r) and "9,87654" not in text_of(r)
    assert_clean(r)
