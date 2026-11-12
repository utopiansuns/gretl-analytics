"""Отчёт Word: единый шрифт, структура и выделение выводов."""
import re
import zipfile

import pytest

from conftest import fixture
from gretl_analytics.report import key_findings, to_docx

docx = pytest.importorskip("docx")
G = [{"var": "price", "ru": "цена дома", "unit": "тыс. долл."}, {"var": "pool", "ru": "бассейн", "unit": "0/1"}]


@pytest.fixture
def report(analyze, tmp_path):
    r = analyze(fixture("ru", "data7-3.txt"), glossary=G, title="Цены на жильё")
    path = str(tmp_path / "report.docx")
    to_docx(r, path)
    return r, path


def xml(path, part):
    with zipfile.ZipFile(path) as z:
        return z.read(part).decode("utf-8")


def test_single_font_everywhere(report):
    _, path = report
    for part in ("word/document.xml", "word/styles.xml"):
        x = xml(path, part)
        assert "Theme=" not in x, f"шрифт темы в {part}"
        fonts = set(re.findall(r'w:(?:ascii|hAnsi|cs)="([^"]+)"', x))
        assert fonts == {"Times New Roman"}, fonts


def test_structure(report):
    _, path = report
    d = docx.Document(path)
    texts = [p.text for p in d.paragraphs]
    assert texts[0] == "Цены на жильё"
    # ГОСТ 7.32: номер раздела без точки, структурные элементы прописными и без номера
    headings = [p.text for p in d.paragraphs if p.style.name == "Heading 1" and p.text[:1].isdigit()]
    assert headings[0] == "1 Описание данных" and not any(h.endswith(".") for h in headings)
    assert "ЗАКЛЮЧЕНИЕ" in texts and "ОСНОВНЫЕ ВЫВОДЫ" in texts
    captions = [t for t in texts if t.startswith("Таблица ")]
    assert [int(c.split()[1]) for c in captions] == list(range(1, len(captions) + 1))
    assert all(" – " in c for c in captions)
    i = texts.index("ОСНОВНЫЕ ВЫВОДЫ")
    assert any("при наличии бассейна" in t for t in texts[i + 1:i + 8])
    x = xml(path, "word/document.xml")
    assert "w:shd" not in x, "в отчёте не должно быть заливок"
    colors = set(re.findall(r'w:color w:val="([0-9A-Fa-f]{6})"', x))
    assert colors <= {"000000"}, colors
    bold_labels = [r.text for p in d.paragraphs for r in p.runs if r.bold and r.text.startswith("Вывод")]
    assert bold_labels, "метка «Вывод:» должна быть полужирной"
    # формулы нумеруются по порядку, номер в скобках у правого поля
    formulas = [t for t in texts if re.search(r"\t\(\d+\)$", t)]
    assert formulas and [int(re.search(r"\((\d+)\)$", t).group(1)) for t in formulas] == list(range(1, len(formulas) + 1))
    assert texts[i + 1].endswith(":"), "перед перечислением нужна вводная фраза с двоеточием"


def test_findings_skip_insignificant(report):
    r, _ = report
    items = key_findings(r)
    assert items and all("незначим" not in text for _, text in items)


def test_brief_mode(analyze, tmp_path):
    r = analyze(fixture("ru", "data3-1.txt"))
    path = str(tmp_path / "brief.docx")
    to_docx(r, path, mode="brief")
    texts = [p.text for p in docx.Document(path).paragraphs]
    assert not any(t.startswith("Распределение Стьюдента") for t in texts)
