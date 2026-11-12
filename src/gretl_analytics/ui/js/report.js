// @ts-check
// Страница отчёта: та же структура, что и в Word (report/docx_report.py), плюс копирование разделов.
"use strict";

App.report = {
  /** Абзацы раздела в выбранном режиме. @param {any} s @returns {string[]} */
  paras: (s) => (App.state.brief ? s.brief : s.full) || [],

  /** Абзацы для копирования и Word: без пустых, оставшихся после правки. @param {any} s */
  filled(s) { return this.paras(s).filter((p) => p.trim()); },

  /** @param {any} x */
  isNum: (x) => /^[-−+<>]?\s*\d[\d\s.,e+−-]*%?\s*\**$/.test(String(x).trim()) || x === "-" || /^\*+$/.test(String(x)),

  /** Подпись таблицы без повтора заголовка раздела. @param {any} t @param {string} title */
  caption(t, title) {
    let lines = (t.caption || "").split("\n").map((/** @type {string} */ x) => x.replace(" (Gretl)", "")).filter((/** @type {string} */ x) => x.trim());
    if (lines[0] && lines[0].trim() === title.trim()) lines = lines.slice(1);
    let cap = lines[0] || "";
    if (cap.startsWith("Зависимая переменная")) cap = "Оценки коэффициентов (" + cap[0].toLowerCase() + cap.slice(1) + ")";
    if (!cap && !t.header) cap = "Характеристики качества модели";
    return cap;
  },

  /** @param {any} t @param {string} title @param {number} n @param {number} si @param {number} ti */
  table(t, title, n, si, ti) {
    const el = App.el, rows = t.rows.slice(0, 120);
    /** @param {string} r @param {number} c */
    const ed = (r, c) => ({ "data-ed": "cell", "data-sec": si, "data-t": ti, "data-r": r, "data-c": c, contenteditable: "plaintext-only" });
    const ncol = Math.max(...[t.header || [], ...rows].map((/** @type {any[]} */ r) => r.length));
    const num = [...Array(ncol)].map((_, j) => t.header ? j > 0 && rows.every((/** @type {any[]} */ r) => !r[j] || this.isNum(r[j])) : j % 2 === 1);
    const table = el("table", { class: t.header ? "" : "plain" },
      t.header ? el("thead", {}, el("tr", {}, t.header.map((/** @type {string} */ x, /** @type {number} */ j) => el("th", { class: num[j] ? "n" : "", ...ed("h", j) }, x)))) : null,
      el("tbody", {}, rows.map((/** @type {any[]} */ r, /** @type {number} */ i) => el("tr", {}, [...Array(ncol)].map((_, j) => el("td", { class: num[j] ? "n" : "", ...ed(String(i), j) }, r[j] ?? ""))))));
    return el("div", { class: "tbl" }, el("p", { class: "cap" }, `Таблица ${n} – ${this.caption(t, title) || title}`), table,
      t.rows.length > rows.length ? el("p", { class: "more" }, `Ещё ${t.rows.length - rows.length} строк в отчёте Word.`) : null);
  },

  /** Абзац с учётом его роли: вывод, расчётный блок, проверка коэффициента. @param {string} p */
  paragraph(p) {
    const el = App.el;
    if (p.includes("\n")) return el("div", { class: "calc" }, p);
    const m = p.match(/^(Вывод(?: по модели)?:)\s*([\s\S]*)$/);
    if (m) return el("p", { class: "concl" }, el("b", {}, m[1]), " " + m[2]);
    const c = p.match(/^([^:]{1,60}): (\|t\| = |z = )([\s\S]*)$/);
    if (c) return el("p", { class: "check" }, el("i", {}, c[1]), ": " + c[2] + c[3]);
    return el("p", {}, p);
  },

  /** HTML раздела для вставки в Word. @param {any} s @param {boolean} withTables */
  html(s, withTables) {
    const esc = App.esc;
    let h = `<div style="font-family:'Times New Roman',serif;font-size:14pt">`;
    if (withTables) {
      h += `<p><b>${esc(s.title)}</b></p>`;
      for (const t of s.tables || []) {
        const cap = this.caption(t, s.title);
        if (cap) h += `<p>${esc(cap)}</p>`;
        h += `<table border="1" cellspacing="0" cellpadding="3" style="border-collapse:collapse;font-size:12pt">`;
        if (t.header) h += "<tr>" + t.header.map((/** @type {string} */ x) => `<th style="font-weight:normal;text-align:center">${esc(x)}</th>`).join("") + "</tr>";
        for (const r of t.rows) h += "<tr>" + r.map((/** @type {string} */ x) => `<td>${esc(x)}</td>`).join("") + "</tr>";
        h += "</table>";
      }
    }
    // абзацы по ГОСТ 7.32: отступ 1,25 см, полуторный интервал, по ширине; «Вывод:» полужирным
    const ps = "margin:0;text-indent:1.25cm;line-height:150%;text-align:justify";
    for (const p of this.filled(s)) {
      const body = esc(p).replace(/\n/g, "<br>").replace(/^(Вывод(?: по модели)?:)/, "<b>$1</b>");
      h += `<p style="${ps}">${body}</p>`;
    }
    return h + "</div>";
  },

  /** Тот же раздел простым текстом. @param {any} s @param {boolean} withTables */
  text(s, withTables) {
    const out = [s.title];
    if (withTables) for (const t of s.tables || []) {
      const cap = this.caption(t, s.title);
      if (cap) out.push(cap);
      if (t.header) out.push(t.header.join("\t"));
      for (const r of t.rows) out.push(r.join("\t"));
    }
    return out.concat(this.filled(s)).join("\n");
  },

  /** @param {string} text @param {string} html */
  async copy(text, html) {
    try { if ((await App.call("copy", text, html)).copied) return App.toast("Скопировано"); } catch (e) { /* ниже запасной путь */ }
    try { await navigator.clipboard.writeText(text); App.toast("Скопировано без оформления"); }
    catch (e) { App.status("Не удалось скопировать. Выделите текст на странице и скопируйте вручную.", true); }
  },

  copyAll() {
    const r = App.state.result;
    if (!r) return;
    this.copy(r.sections.map((/** @type {any} */ s) => this.text(s, true)).join("\n\n"),
              r.sections.map((/** @type {any} */ s) => this.html(s, true)).join(""));
  },

  closeMenus() {
    document.querySelectorAll(".sec-menu").forEach((m) => m.remove());
    document.querySelectorAll(".sec-copy[aria-expanded=true]").forEach((b) => b.setAttribute("aria-expanded", "false"));
  },

  /** @param {any} s @param {number} i */
  section(s, i) {
    const el = App.el;
    const final = s.kind === "conclusions";   // структурный элемент по ГОСТ: без номера, по центру
    const btn = el("button", { class: "sec-copy", "aria-haspopup": "menu", "aria-expanded": "false" }, "Копировать");
    const node = el("section", { class: "doc-section", id: "sec-" + i },
      el("h2", { class: final ? "structural" : "" }, final ? null : el("span", { class: "num" }, String(i + 1)),
        final ? el("span", { class: "t" }, "Заключение")
          : el("span", { class: "t", "data-ed": "title", "data-sec": i, contenteditable: "plaintext-only" }, s.title), btn));
    btn.addEventListener("click", (ev) => {
      ev.stopPropagation();
      const open = btn.getAttribute("aria-expanded") === "true";
      this.closeMenus();
      if (open) return;
      btn.setAttribute("aria-expanded", "true");
      node.append(el("div", { class: "sec-menu", role: "menu" },
        el("button", { role: "menuitem", onclick: () => { this.closeMenus(); this.copy(this.filled(s).join("\n"), this.html(s, false)); } }, "Скопировать текст"),
        el("button", { role: "menuitem", onclick: () => { this.closeMenus(); this.copy(this.text(s, true), this.html(s, true)); } }, "Скопировать с таблицами")));
    });
    (s.tables || []).forEach((/** @type {any} */ t, /** @type {number} */ ti) => node.append(this.table(t, s.title, ++this.nTable, i, ti)));
    if (s.equation && !App.state.brief) {
      node.append(el("div", { class: "eq" },
        el("div", { class: "main" }, s.equation.text.replace(/^\^(\S+)/, "$1").replace(/\*/g, "·"),
          el("span", { class: "no" }, `(${++this.nFormula})`)),
        el("div", { class: "se" }, s.equation.se),
        el("div", { class: "cap" }, "в скобках указаны стандартные ошибки")));
    }
    this.paras(s).forEach((p, k) => {
      const e = this.paragraph(p);
      Object.assign(e.dataset, { ed: "p", sec: String(i), p: String(k) });
      e.setAttribute("contenteditable", "plaintext-only");
      node.append(e);
    });
    if (s.note) node.append(el("p", { class: "note" }, "Примечание – " + s.note));   // ГОСТ: после материала
    return node;
  },

  nTable: 0,
  nFormula: 0,

  /** Перерисовать страницу. @param {boolean} animate */
  render(animate) {
    const S = App.state, r = S.result, el = App.el;
    if (!r) return;
    const paper = App.$("paper");
    const today = new Date().toLocaleDateString("ru-RU", { day: "numeric", month: "long", year: "numeric" });
    const kids = [el("h1", { class: "doc-title", "data-ed": "doctitle", contenteditable: "plaintext-only" }, S.title || "Эконометрический анализ"),
                  el("p", { class: "doc-sub" }, `Аналитический отчёт по результатам расчётов в Gretl, ${today}`)];
    for (const w of r.warnings || []) kids.push(el("p", { class: "doc-warn" }, w));
    if (S.findings.length) {
      kids.push(el("section", { class: "findings", "aria-label": "Основные выводы" }, el("h2", { class: "structural" }, "Основные выводы"),
        el("p", {}, "По результатам анализа получены следующие основные выводы:"),
        S.findings.map((f, k) => el("p", { class: "dash" }, "– ", f.label ? el("b", {}, f.label + ". ") : null,
          el("span", { "data-ed": "finding", "data-f": k, contenteditable: "plaintext-only" }, f.text)))));
    }
    this.nTable = this.nFormula = 0;
    r.sections.forEach((/** @type {any} */ s, /** @type {number} */ i) => kids.push(this.section(s, i)));
    paper.replaceChildren(...kids);
    if (animate) { paper.classList.remove("arrive"); void paper.offsetWidth; paper.classList.add("arrive"); }
    App.$("doc-actions").hidden = false;
    this.outline(r.sections);
  },

  /** Оглавление справа с подсветкой текущего раздела. @param {any[]} sections */
  outline(sections) {
    const el = App.el, nav = App.$("outline"), desk = App.$("desk");
    nav.replaceChildren(el("h3", {}, "Разделы"), ...sections.map((s, i) => el("a", {
      href: "#sec-" + i, "data-i": i,
      onclick: (/** @type {Event} */ ev) => {
        ev.preventDefault();
        this.mark(i);
        this.lockUntil = Date.now() + 900;   // пока идёт плавная прокрутка, подсветка остаётся на выбранном
        App.$("sec-" + i).scrollIntoView({ behavior: "smooth", block: "start" });
      },
    }, s.kind === "conclusions" ? "Заключение" : `${i + 1} ${s.title.replace(/, использованы наблюдения.*$/, "")}`)));
    if (!this.tracking) {
      this.tracking = true;
      // подсветка считается прямо в обработчике: разделов немного, а requestAnimationFrame
      // в фоновом окне macOS приостанавливает, и подсветка отставала бы
      desk.addEventListener("scroll", () => { if (Date.now() > this.lockUntil) this.mark(this.current()); }, { passive: true });
    }
    this.mark(this.current());
  },

  /** Номер раздела, который сейчас читается: последний, чей заголовок поднялся выше трети окна. */
  current() {
    const desk = App.$("desk"), secs = [...document.querySelectorAll(".doc-section")];
    if (!secs.length) return -1;
    if (desk.scrollTop + desk.clientHeight >= desk.scrollHeight - 4) return secs.length - 1;   // долистали до конца
    const line = desk.getBoundingClientRect().top + desk.clientHeight / 3;
    let k = 0;
    secs.forEach((s, i) => { if (s.getBoundingClientRect().top <= line) k = i; });
    return k;
  },

  /** @param {number} i */
  mark(i) {
    App.$("outline").querySelectorAll("a").forEach((a) => a.classList.toggle("on", a.dataset.i === String(i)));
  },

  tracking: false,
  lockUntil: 0,
};
