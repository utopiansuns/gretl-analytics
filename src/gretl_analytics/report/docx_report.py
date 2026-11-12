"""Отчёт в Word (.docx), оформленный по ГОСТ 7.32-2017.

* Шрифт Times New Roman во всём документе (шрифты темы Word удалены), чёрный цвет.
* Поля: левое 30 мм, правое 15 мм, верхнее и нижнее 20 мм. Основной текст 14 pt,
  полуторный интервал, абзацный отступ 1,25 см, выравнивание по ширине.
* Номера страниц арабскими цифрами внизу по центру, без точки.
* Структурные элементы («ОСНОВНЫЕ ВЫВОДЫ», «ЗАКЛЮЧЕНИЕ», «ПРИМЕЧАНИЯ»): по центру,
  прописными буквами, полужирные, без номера и точки в конце.
* Разделы: номер без точки («1 Описание данных»), абзацный отступ, полужирный шрифт.
* Таблицы ограничены линиями со всех сторон; название «Таблица 1 – …» над таблицей слева,
  без абзацного отступа; шапка по центру и повторяется на новой странице. Шрифт таблиц 12 pt.
* Формулы на отдельной строке по центру, номер в круглых скобках у правого поля: (1).
* Перечисления через тире с абзацного отступа, примечания в виде «Примечание – …».
* Без заливок и цветных рамок: важное выделено полужирным.
"""
import datetime
import re

FONT = "Times New Roman"
RULE = "000000"          # линии таблиц
INDENT_CM = 1.25         # абзацный отступ
TEXT_CM = 21 - 3 - 1.5    # ширина текста между полями

MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября",
          "октября", "ноября", "декабря"]
SKIP_IN_SUMMARY = {"data", "compare", "conclusions"}
NUM_RE = re.compile(r"^[-−+<>]?\s*\d[\d\s.,e+−-]*%?\s*\**$|^-$|^\*+$")


# ------------------------------------------------------------------ низкоуровневые помощники

def _el(tag, **attrs):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    e = OxmlElement(tag)
    for k, v in attrs.items():
        e.set(qn(f"w:{k}"), str(v))
    return e


def _fonts(rpr, name=FONT):
    """Явный шрифт для всех алфавитов и удаление шрифтов темы."""
    from docx.oxml.ns import qn
    rf = rpr.find(qn("w:rFonts"))
    if rf is None:
        rf = _el("w:rFonts")
        rpr.insert(0, rf)
    for a in ("asciiTheme", "hAnsiTheme", "eastAsiaTheme", "cstheme"):
        rf.attrib.pop(qn(f"w:{a}"), None)
    for a in ("ascii", "hAnsi", "eastAsia", "cs"):
        rf.set(qn(f"w:{a}"), name)


def _run(p, text, size=None, bold=False, italic=False, color=None):
    from docx.shared import Pt, RGBColor
    r = p.add_run(text)
    _fonts(r._element.get_or_add_rPr())
    if size:
        r.font.size = Pt(size)
    r.bold, r.italic = bold or None, italic or None
    if color:
        r.font.color.rgb = RGBColor.from_string(color)
    return r


def _table_grid(tb, size=4):
    """Сетка таблицы: линии со всех сторон и между ячейками, 0,5 pt."""
    b = _el("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        b.append(_el(f"w:{edge}", val="single", sz=size, space=0, color=RULE))
    tb._tbl.tblPr.append(b)


def _full_width(tb, margin_twips=85):
    """Таблица на всю ширину текста и внутренние поля ячеек ~1,5 мм."""
    from docx.oxml.ns import qn
    pr = tb._tbl.tblPr
    for old in pr.findall(qn("w:tblW")):
        pr.remove(old)
    pr.append(_el("w:tblW", w=5000, type="pct"))
    mar = _el("w:tblCellMar")
    for side in ("left", "right"):
        mar.append(_el(f"w:{side}", w=margin_twips, type="dxa"))
    pr.append(mar)


def _page_number(section):
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    p = section.footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = _run(p, "", size=12)
    for node in (_el("w:fldChar", fldCharType="begin"), _instr(" PAGE "), _el("w:fldChar", fldCharType="end")):
        r._element.append(node)


def _instr(text):
    from docx.oxml.ns import qn
    e = _el("w:instrText")
    e.set(qn("xml:space"), "preserve")
    e.text = text
    return e


# ------------------------------------------------------------------ документ

class Report:
    def __init__(self):
        from docx import Document
        from docx.shared import Cm, Pt
        self.doc = Document()
        s = self.doc.sections[0]
        s.page_width, s.page_height = Cm(21), Cm(29.7)
        s.left_margin, s.right_margin, s.top_margin, s.bottom_margin = Cm(3), Cm(1.5), Cm(2), Cm(2)
        s.footer_distance = Cm(1.0)
        self.n_table = 0
        self.n_formula = 0
        # шрифт по умолчанию для всего документа и всех стилей
        _fonts(self.doc.styles.element.find(
            "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}docDefaults")
            .find("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}rPrDefault")
            .find("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}rPr"))
        styles_el = self.doc.styles.element
        for rfonts in styles_el.iter("{http://schemas.openxmlformats.org/wordprocessingml/2006/main}rFonts"):
            _fonts(rfonts.getparent())
        for st in self.doc.styles:
            el = getattr(st, "element", None)
            if el is not None and hasattr(st, "font"):
                _fonts(el.get_or_add_rPr())
        normal = self.doc.styles["Normal"]
        normal.font.size = Pt(14)
        pf = normal.paragraph_format
        pf.line_spacing, pf.space_before, pf.space_after = 1.5, Pt(0), Pt(0)
        _page_number(s)

    # --- абзацы
    def para(self, text="", size=14, align="justify", indent=True, spacing=1.5, before=0, after=0,
             bold=False, italic=False, color=None, keep_next=False):
        from docx.enum.text import WD_ALIGN_PARAGRAPH as A
        from docx.shared import Cm, Pt
        p = self.doc.add_paragraph()
        p.alignment = {"justify": A.JUSTIFY, "left": A.LEFT, "center": A.CENTER, "right": A.RIGHT}[align]
        f = p.paragraph_format
        f.first_line_indent = Cm(INDENT_CM) if indent else Cm(0)
        f.line_spacing, f.space_before, f.space_after = spacing, Pt(before), Pt(after)
        f.keep_with_next = keep_next
        f.widow_control = True
        if text:
            _run(p, text, size=size, bold=bold, italic=italic, color=color)
        return p

    def heading(self, text, number):
        """Заголовок раздела: «1 Описание данных», с абзацного отступа, без точки в конце."""
        from docx.shared import Cm
        p = self.para(align="left", indent=False, spacing=1.5, before=18, after=12, keep_next=True)
        p.style = self.doc.styles["Heading 1"]
        p.paragraph_format.first_line_indent = Cm(INDENT_CM)
        _run(p, f"{number} {text.rstrip('.')}", size=14, bold=True, color="000000")
        return p

    def structural(self, text):
        """Заголовок структурного элемента: по центру, прописными, без номера."""
        p = self.para(align="center", indent=False, spacing=1.5, before=18, after=12, keep_next=True)
        p.style = self.doc.styles["Heading 1"]
        p.paragraph_format.first_line_indent = 0
        _run(p, text.upper(), size=14, bold=True, color="000000")
        return p

    def note(self, text):
        """Примечание по ГОСТ: «Примечание – текст»."""
        p = self.para(size=12, indent=True, spacing=1.15, before=2, after=6)
        _run(p, "Примечание – ", size=12)
        _run(p, text, size=12)
        return p

    def conclusion(self, text):
        """«Вывод: …»: полужирная метка, дальше обычный текст."""
        m = re.match(r"^(Вывод(?: по модели)?:)\s*(.*)$", text, re.S)
        p = self.para(align="justify", indent=True, spacing=1.5, before=6, after=6)
        if m:
            _run(p, m.group(1) + " ", bold=True)
            _run(p, m.group(2))
        else:
            _run(p, text)
        return p

    def calc_block(self, text):
        """Расчётный блок (критические значения, проверка t и F): компактно, первая строка полужирная."""
        from docx.shared import Cm
        lines = text.split("\n")
        for i, line in enumerate(lines):
            p = self.para(size=12, align="left", indent=False, spacing=1.15,
                          before=4 if i == 0 else 0, after=4 if i == len(lines) - 1 else 0, keep_next=i < len(lines) - 1)
            p.paragraph_format.left_indent = Cm(0.35)
            _run(p, line, size=12, bold=i == 0)

    def check_line(self, text):
        """Строка проверки значимости по отдельной переменной."""
        from docx.shared import Cm
        p = self.para(size=12, align="left", indent=False, spacing=1.15)
        p.paragraph_format.left_indent = Cm(0.35)
        name, _, rest = text.partition(": |")
        if rest:
            _run(p, name, size=12, italic=True)
            _run(p, ": |" + rest, size=12)
        else:
            _run(p, text, size=12)

    def text(self, t):
        if "\n" in t:
            return self.calc_block(t)
        if t.startswith("Вывод"):
            return self.conclusion(t)
        if re.match(r"^[^:]{1,60}: \|t\| = ", t) or re.match(r"^[^:]{1,60}: z = ", t):
            return self.check_line(t)
        if t.startswith(("Проверим гипотезу", "Распределение Стьюдента")):
            return self.para(t, keep_next=True, indent=False, bold=True, size=14, before=6)
        return self.para(t)

    # --- таблицы
    def table(self, t, section_title):
        from docx.enum.table import WD_TABLE_ALIGNMENT
        from docx.enum.text import WD_ALIGN_PARAGRAPH as A
        from docx.shared import Cm, Pt
        header, rows = t.get("header"), t.get("rows") or []
        if not rows:
            return
        self.n_table += 1
        cap = [c.replace(" (Gretl)", "") for c in (t.get("caption") or "").split("\n") if c.strip()]
        if cap and cap[0].strip() == section_title.strip():
            cap = cap[1:]
        title = cap[0] if cap else section_title
        if title.startswith("Зависимая переменная"):
            title = "Оценки коэффициентов (" + title[:1].lower() + title[1:] + ")"
            cap = [title]
        elif not header and not cap:
            title = "Характеристики качества модели"
        self.para(f"Таблица {self.n_table} – {title.rstrip('.')}", size=14, align="left", indent=False,
                  spacing=1.15, before=12, after=4, keep_next=True)
        for extra in cap[1:]:
            self.para(extra, size=12, align="left", indent=False, spacing=1.15, after=4, keep_next=True)

        allrows = ([header] if header else []) + rows
        ncol = max(len(r) for r in allrows)
        body = rows
        numeric = [j > 0 and all((r[j] if j < len(r) else "") == "" or NUM_RE.match(str(r[j]).strip()) for r in body)
                   for j in range(ncol)]
        if not header:   # таблица статистик «подпись | значение | подпись | значение»
            numeric = [j % 2 == 1 for j in range(ncol)]
        tb = self.doc.add_table(rows=len(allrows), cols=ncol)
        tb.alignment = WD_TABLE_ALIGNMENT.CENTER
        tb.autofit = True
        _table_grid(tb)
        _full_width(tb)
        for i, r in enumerate(allrows):
            is_head = bool(header) and i == 0
            for j in range(ncol):
                cell = tb.cell(i, j)
                cell.text = ""
                cp = cell.paragraphs[0]
                cf = cp.paragraph_format
                cf.first_line_indent, cf.line_spacing = Cm(0), 1.0
                cf.space_before = cf.space_after = Pt(2)
                cp.alignment = A.CENTER if is_head else A.RIGHT if numeric[j] else A.LEFT
                _run(cp, str(r[j]) if j < len(r) else "", size=12)
            if is_head:
                trpr = tb.rows[0]._tr.get_or_add_trPr()
                trpr.append(_el("w:tblHeader"))
        self.para("", size=12, spacing=1.0)

    def equation(self, eq):
        text = re.sub(r"^\^(\S+)", r"\1", eq["text"]).replace("*", "·")
        from docx.enum.text import WD_TAB_ALIGNMENT
        from docx.shared import Cm
        self.n_formula += 1
        self.para("Оценённое уравнение регрессии:", size=14, align="left", indent=True, before=6, keep_next=True)
        # формула по центру, её номер у правого поля (ГОСТ 7.32-2017, 6.8)
        p = self.para(align="left", indent=False, spacing=1.15, keep_next=True)
        tabs = p.paragraph_format.tab_stops
        tabs.add_tab_stop(Cm(TEXT_CM / 2), WD_TAB_ALIGNMENT.CENTER)
        tabs.add_tab_stop(Cm(TEXT_CM), WD_TAB_ALIGNMENT.RIGHT)
        _run(p, "\t" + text, italic=True)
        _run(p, f"\t({self.n_formula})")
        self.para(eq["se"], size=12, align="center", indent=False, spacing=1.15, keep_next=True)
        self.para("(в скобках указаны стандартные ошибки коэффициентов)", size=12, align="center",
                  indent=False, italic=True, spacing=1.15, after=6)

    def key_findings(self, items):
        """«ОСНОВНЫЕ ВЫВОДЫ»: перечисление через тире с абзацного отступа."""
        items = [(label, text) for label, text in items if text.strip()]
        if not items:
            return
        self.structural("Основные выводы")
        self.para("По результатам анализа получены следующие основные выводы:", keep_next=True)
        for label, text in items:
            q = self.para(after=0)
            _run(q, "– ")
            if label:
                _run(q, label + ". ", bold=True)
            _run(q, text)


def key_findings(result):
    """Ключевые результаты для списка «Основные выводы»: первые выводы каждого раздела."""
    items = []
    for s in result["sections"]:
        if s["kind"] in SKIP_IN_SUMMARY:
            continue
        concl = [p for p in (s.get("brief") or []) if p.startswith("Вывод")] or (s.get("brief") or [])[:1]
        label = re.sub(r":.*$", "", s["title"]).strip()
        for p in concl[:2]:
            if "\n" in p:
                continue
            text = re.sub(r"^Вывод(?: по модели)?:\s*", "", p).rstrip(".")
            if s["kind"] == "model":
                # в список попадают только статистически подтверждённые эффекты
                parts = [x.strip() for x in text.split(";") if "незначим" not in x]
                if not parts:
                    continue
                text = "; ".join(parts)
                text = re.sub(r"^Гипотеза о незначимости уравнения отвергается, уравнение значимо в целом",
                              "Уравнение значимо в целом", text[:1].upper() + text[1:])
            items.append((label, text[:1].upper() + text[1:] + "."))
    return items[:10]


def to_docx(result, path, mode="full", section_ids=None, findings=None):
    """Сохраняет отчёт. mode: full (подробно) или brief (только выводы и таблицы).

    findings – «Основные выводы», исправленные пользователем; без них список собирается заново."""
    r = Report()
    today = datetime.date.today()
    r.para(result.get("title") or "Эконометрический анализ", size=18, align="center", indent=False,
           bold=True, spacing=1.15, after=4)
    r.para("Аналитический отчёт по результатам расчётов в Gretl", size=13, align="center", indent=False,
           italic=True, spacing=1.15)
    r.para(f"{today.day} {MONTHS[today.month - 1]} {today.year} г.", size=13, align="center", indent=False,
           spacing=1.15, after=14)

    sections = [s for s in result["sections"] if not section_ids or s["id"] in section_ids]
    r.key_findings(findings if findings is not None else key_findings({"sections": sections}))

    n = 0
    for s in sections:
        if s["kind"] == "conclusions":
            r.structural("Заключение")
        else:
            n += 1
            r.heading(s["title"], n)
        for t in s.get("tables", []):
            r.table(t, s["title"])
        if s.get("equation") and mode == "full":
            r.equation(s["equation"])
        for p in s.get(mode) or []:
            if p.strip():          # пустые абзацы остаются после правки на листе
                r.text(p)
        if s.get("note"):   # примечание идёт после материала, к которому относится
            r.note(s["note"])

    if result.get("warnings"):
        r.structural("Примечания")
        for k, w in enumerate(result["warnings"], 1):
            r.para(f"{k} {w}", size=12, spacing=1.15)
    r.doc.save(path)
    return path
