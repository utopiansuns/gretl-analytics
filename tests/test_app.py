"""Мост интерфейса (Api) и командная строка."""
import json
import os
import subprocess
import sys

from conftest import fixture
from gretl_analytics.api import Api
from gretl_analytics.storage import Storage


def test_api_flow(tmp_path):
    api = Api(Storage(str(tmp_path / "home")))
    text = fixture("ru", "data7-3.txt")
    assert api.detect(text)["kinds"] == {"data": 1, "model": 2, "test": 1}

    r = api.analyze(text, [{"var": "pool", "ru": "бассейн", "unit": "0/1"}, {"var": "", "ru": "пусто"}], "Отчёт")
    assert r["ok"] and len(r["result"]["sections"]) >= 5 and r["findings"]
    json.dumps(r, allow_nan=False)        # ответ должен разбираться JSON.parse в окне

    v = api.variables("", [{"var": "price", "ru": "цена"}])
    assert v["forms"]["price"]["ins"] == "ценой"

    api.save_state({"text": "abc", "glossary": [{"var": "x", "ru": "икс", "unit": ""}], "junk": 1})
    st = api.load_state()
    assert st["text"] == "abc" and st["glossary"][0]["ru"] == "икс" and "junk" not in st

    out = str(tmp_path / "r.docx")
    assert api.export_word("full", "Отчёт", path=out)["path"] == out and os.path.getsize(out) > 5000


def test_export_with_edits(tmp_path):
    """Правки с листа попадают в Word: изменённый и пустой абзац, ячейка таблицы, основные выводы."""
    import docx
    api = Api(Storage(str(tmp_path / "home")))
    res = api.analyze(fixture("ru", "data3-1.txt"), [], "Отчёт")["result"]
    sections = json.loads(json.dumps(res["sections"]))
    model = next(s for s in sections if s["kind"] == "model")
    model["full"][0] = "Свой текст абзаца."
    model["full"].append("   ")
    model["tables"][0]["rows"][0][0] = "свободный член"
    findings = [{"label": "", "text": "Мой главный вывод."}, {"label": "Пусто", "text": ""}]
    out = str(tmp_path / "e.docx")
    api.export_word("full", "Отчёт", path=out, edited={"sections": sections, "findings": findings})
    d = docx.Document(out)
    texts = [p.text for p in d.paragraphs]
    assert "Свой текст абзаца." in texts and "– Мой главный вывод." in texts
    assert not any(t.startswith("– Пусто") for t in texts)
    assert any(c.text == "свободный член" for t in d.tables for row in t.rows for c in row.cells)
    assert api.load_state()["sidebar"] is None
    api.save_state({"sidebar": 480})
    assert api.load_state()["sidebar"] == 480


def test_api_errors_are_messages(tmp_path):
    api = Api(Storage(str(tmp_path / "home")))
    r = api.export_word("full", "x", path=str(tmp_path / "x.docx"))
    assert r == {"ok": False, "error": "RuntimeError: Сначала сформируйте аналитику."}


def _cli(*args):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    p = subprocess.run([sys.executable, "-m", "gretl_analytics", *args], capture_output=True, text=True,
                       encoding="utf-8", env=env, timeout=120)
    return json.loads(p.stdout.strip().splitlines()[-1])


def test_cli(tmp_path):
    text = tmp_path / "in.txt"
    text.write_text(fixture("ru", "data3-1.txt"), encoding="utf-8")
    gloss = tmp_path / "g.json"
    gloss.write_text(json.dumps([{"var": "price", "ru": "цена дома"}], ensure_ascii=False), encoding="utf-8")
    r = _cli("paste", "--text", str(text), "--glossary", str(gloss), "--out", str(tmp_path / "out"))
    assert r["ok"] and not r["unverified"]
    assert _cli("vars", "--text", str(text), "--glossary", str(gloss))["forms"]["price"]["gen"] == "цены дома"
    e = _cli("export", "--result", r["result"], "--out", str(tmp_path / "r.docx"), "--mode", "brief")
    assert e["ok"] and (tmp_path / "r.docx").exists()
