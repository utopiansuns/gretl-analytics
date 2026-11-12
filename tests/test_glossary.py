"""Словарь переменных и склонение русских названий."""
import re
from conftest import assert_clean, fixture, text_of
from gretl_analytics.core import morph
from gretl_analytics.core.analysis import find_variables


def test_inflection():
    assert morph.available()
    f = morph.forms("цена")
    assert (f["gen"], f["acc"], f["ins"]) == ("цены", "цену", "ценой")
    assert morph.inflect("жилая площадь", "gen") == "жилой площади"
    assert morph.inflect("цена продажи", "ins") == "ценой продажи"
    assert morph.inflect("расходы на рекламу", "gen") == "расходов на рекламу"
    assert morph.inflect("ВВП", "gen") == "ВВП"
    assert morph.inflect("price", "gen") == "price"
    assert morph.agree("цена", "связан", "связана", "связано", "связаны") == "связана"


def test_glossary_applies_everywhere(analyze):
    g = [{"var": "price", "ru": "цена дома", "unit": "тыс. долл."}, {"var": "sqft", "ru": "жилая площадь", "unit": "кв. футов"}]
    r = analyze(fixture("en", "data3-1.txt"), glossary=g)
    T = text_of(r)
    assert "коэффициент при жилой площади (sqft)" in T
    assert "при увеличении жилой площади на 1 кв. фут цена дома в среднем увеличивается" in T
    assert "вариации цены дома" in T
    assert "цена дома – от 199,90 до 505,00 тыс. долл." in T
    assert_clean(r)


def test_glossary_dummy(analyze):
    g = [{"var": "price", "ru": "цена", "unit": "тыс. долл."}, {"var": "pool", "ru": "бассейн", "unit": "0/1"}]
    T = text_of(analyze(fixture("en", "data7-3.txt"), glossary=g))
    assert "при наличии бассейна цена в среднем на 52,79 тыс. долл. выше, чем при отсутствии бассейна" in T


def test_glossary_in_correlations(analyze):
    g = [{"var": "price", "ru": "цена"}, {"var": "sqft", "ru": "жилая площадь"}]
    T = text_of(analyze(fixture("en", "data7-3.txt"), glossary=g))
    assert "между ценой и жилой площадью наблюдается весьма высокая положительная линейная связь" in T


def test_find_variables():
    res = find_variables(fixture("ru", "data7-3.txt"), [{"var": "price", "ru": "цена"}])
    names = [v["name"] for v in res["variables"]]
    assert names[:2] == ["price", "sqft"] and "pool" in names and "const" not in names
    pool = next(v for v in res["variables"] if v["name"] == "pool")
    assert pool["kind"] == "dummy" and pool["suggest"] == "наличие бассейна"
    assert res["forms"]["price"]["acc"] == "цену"


def test_glossary_case_kept(analyze):
    """Название из словаря со строчной буквы не превращается в заглавное внутри предложения."""
    r = analyze(fixture("ru", "data3-1.txt"), glossary=[{"var": "price", "ru": "цена дома", "unit": "тыс. долл."}])
    text = " ".join(p for s in r["sections"] for p in s["full"])
    assert "цены дома" in text or "цена дома" in text
    assert not re.search(r"[^.:!?\n]\s+Цен[аыеу] дома", text)
    assert all(not re.match(r"[а-яё]", p) for s in r["sections"] for p in s["full"])


def test_suggestions_from_gretl_datasets():
    """Без описания данных набор Gretl узнаётся по составу переменных, и названия с единицами берутся из него."""
    r = find_variables(fixture("en", "data7-3.txt"))
    got = {v["name"]: (v["suggest"], v["unit"]) for v in r["variables"]}
    assert got["price"] == ("цена продажи", "тыс. долл.")
    assert got["sqft"] == ("жилая площадь", "кв. футов")
    assert got["bedrms"] == ("число спален", "ед.")
    assert got["pool"] == ("наличие бассейна", "0/1")
    got = {v["name"]: (v["suggest"], v["unit"]) for v in find_variables(fixture("ru", "data3-4.txt"))["variables"]}
    assert got["tax"] == ("подоходный налог", "млрд долл.")


def test_ambiguous_names_and_own_data():
    from gretl_analytics.core.meta import gretl_vars, guess_known
    assert len(gretl_vars()) > 1000
    # одно имя в разных наборах: решает соседство переменных
    assert guess_known(["C", "Wp", "Wg"])["C"][0] == "потребление"          # модель Клейна
    assert guess_known(["C", "Q", "PF"])["C"][0] == "издержки"               # издержки авиакомпаний
    # своё исследование: однозначное название остаётся, денежная единица не угадывается
    own = guess_known(["sqft", "rubles_spent"])
    assert own["sqft"] == ("жилая площадь", "кв. футов") and "rubles_spent" not in own
    assert "C" not in guess_known(["C", "my_var"])                             # неоднозначно без контекста


def test_guess_derived_names():
    from gretl_analytics.core.meta import guess_by_name
    assert guess_by_name("l_price") == ("логарифм цены", "")
    assert guess_by_name("l_sqft") == ("логарифм жилой площади", "")
    assert guess_by_name("d_unemp") == ("изменение уровня безработицы", "п.п.")
    assert guess_by_name("sqft_1") == ("жилая площадь с лагом 1", "кв. футов")
    assert guess_by_name("xyz") is None
