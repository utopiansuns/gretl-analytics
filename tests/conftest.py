"""Общие помощники тестов.

Данные: вывод Gretl на учебных наборах из поставки Gretl (Ramanathan, bjg).
  fixtures/ru  русский интерфейс Gretl (в том числе таблицы, вставленные через Word);
  fixtures/en  gretlcli, пересоздаётся скриптом scripts/make_fixtures.sh.
"""
import json
import os

import pytest

from gretl_analytics.core.analysis import analyze_blocks

HERE = os.path.dirname(os.path.abspath(__file__))


def fixture(lang, name):
    with open(os.path.join(HERE, "fixtures", lang, name), encoding="utf-8") as f:
        return f.read()


def text_of(result):
    """Всё, что видит пользователь: заголовки, ячейки таблиц, подробный и краткий текст."""
    out = []
    for s in result["sections"]:
        out.append(s["title"])
        for t in s["tables"]:
            out += [" ".join(x) for x in t["rows"]]
        out += s["full"] + s["brief"]
    return "\n".join(out)


def kinds(result):
    return [s["kind"] for s in result["sections"]]


def assert_clean(result):
    assert not result["warnings"], result["warnings"]
    assert not result["verification"]["unverified"], result["verification"]["unverified"]


@pytest.fixture
def analyze(tmp_path):
    counter = iter(range(10_000))

    def run(text, glossary=None, title=None):
        return analyze_blocks([{"kind": "auto", "text": text}], str(tmp_path / f"run{next(counter)}"),
                              glossary=glossary, title=title)
    return run


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    """Данные приложения в тестах пишутся во временную папку, а не в профиль пользователя."""
    monkeypatch.setenv("GRETL_ANALYTICS_HOME", str(tmp_path / "home"))


def dumps(obj):
    return json.dumps(obj, ensure_ascii=False)
