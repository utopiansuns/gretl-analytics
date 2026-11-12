// @ts-check
// Правка отчёта прямо на листе, как в Word: набор, удаление, вставка, ⌘Z.
// Каждый редактируемый элемент знает, какой кусок данных он показывает (data-ed и номера),
// поэтому правки сразу попадают в App.state.result: их получают копирование и «Сохранить в Word».
// Enter делит абзац на два, Backspace в начале абзаца соединяет его с предыдущим.
"use strict";

App.editor = {
  init() {
    const paper = App.$("paper");
    paper.addEventListener("input", (/** @type {Event} */ e) => { const t = this.target(e.target); if (t) this.input(t); });
    paper.addEventListener("keydown", (/** @type {KeyboardEvent} */ e) => this.key(e));
    paper.addEventListener("paste", (/** @type {ClipboardEvent} */ e) => this.paste(e));
  },

  /** @param {any} node @returns {HTMLElement|null} */
  target: (node) => (node && node.closest ? node.closest("[data-ed]") : node && node.parentElement && node.parentElement.closest("[data-ed]")),

  /** Абзацы раздела в текущем режиме («Подробно» и «Кратко» правятся отдельно). @param {number} si @returns {string[]} */
  paras(si) {
    const s = App.state.result.sections[si];
    return App.state.brief ? s.brief : s.full;
  },

  /** @param {HTMLElement} el */
  text: (el) => el.innerText.replace(/ /g, " ").replace(/\n$/, ""),

  /** Перенести текст элемента в данные отчёта. @param {HTMLElement} el */
  input(el) {
    const S = App.state, d = el.dataset, txt = this.text(el);
    if (d.ed === "p") this.paras(Number(d.sec))[Number(d.p)] = txt;
    else if (d.ed === "title") S.result.sections[Number(d.sec)].title = txt;
    else if (d.ed === "finding") S.findings[Number(d.f)].text = txt;
    else if (d.ed === "cell") {
      const t = S.result.sections[Number(d.sec)].tables[Number(d.t)];
      if (d.r === "h") t.header[Number(d.c)] = txt; else t.rows[Number(d.r)][Number(d.c)] = txt;
    } else if (d.ed === "doctitle") {
      S.title = txt;
      App.$("title").value = txt;
      App.persist();
      return;
    }
    this.touched();
  },

  /** Отметить, что отчёт правили: появляется «Отменить правки». */
  touched() {
    App.state.edited = true;
    App.$("reset-edits").hidden = false;
  },

  /** Запомнить сформированный отчёт, чтобы правки можно было отменить. */
  snapshot() {
    const S = App.state;
    S.original = JSON.parse(JSON.stringify({ result: S.result, findings: S.findings }));
    S.edited = false;
    App.$("reset-edits").hidden = true;
  },

  reset() {
    const S = App.state;
    if (!S.original) return;
    const o = JSON.parse(JSON.stringify(S.original));
    S.result = o.result;
    S.findings = o.findings;
    S.edited = false;
    App.$("reset-edits").hidden = true;
    App.report.render(false);
    App.status("Правки отменены: на листе текст, который сформировало приложение.");
  },

  /** @param {KeyboardEvent} e */
  key(e) {
    const el = this.target(e.target);
    if (!el || e.isComposing) return;
    const d = el.dataset, sel = window.getSelection();
    if (e.key === "Enter" && !e.shiftKey) {
      if (d.ed === "p" && !el.classList.contains("calc")) { e.preventDefault(); this.split(el); }
      else if (d.ed !== "p") { e.preventDefault(); el.blur(); }
    } else if (e.key === "Backspace" && d.ed === "p" && Number(d.p) > 0 && sel && sel.isCollapsed && this.caret(el) === 0) {
      e.preventDefault();
      this.merge(el);
    }
  },

  /** Вставка только текстом; в обычном абзаце переносы строк становятся пробелами. @param {ClipboardEvent} e */
  paste(e) {
    const el = this.target(e.target);
    if (!el || !e.clipboardData) return;
    e.preventDefault();
    let txt = e.clipboardData.getData("text/plain");
    if (!el.classList.contains("calc")) txt = txt.replace(/\s*\n\s*/g, " ");
    document.execCommand("insertText", false, txt);   // так вставка попадает в историю ⌘Z
  },

  /** Позиция курсора в символах от начала элемента. @param {HTMLElement} el */
  caret(el) {
    const sel = window.getSelection();
    if (!sel || !sel.rangeCount) return -1;
    const r = sel.getRangeAt(0), pre = r.cloneRange();
    pre.selectNodeContents(el);
    pre.setEnd(r.startContainer, r.startOffset);
    return pre.toString().length;
  },

  /** Enter: абзац делится на два по курсору. @param {HTMLElement} el */
  split(el) {
    const si = Number(el.dataset.sec), k = Number(el.dataset.p), list = this.paras(si);
    const txt = this.text(el), at = this.caret(el);
    list.splice(k, 1, txt.slice(0, at).trimEnd(), txt.slice(at).trimStart());
    this.redraw(si, k + 1, 0);
  },

  /** Backspace в начале: абзац присоединяется к предыдущему. @param {HTMLElement} el */
  merge(el) {
    const si = Number(el.dataset.sec), k = Number(el.dataset.p), list = this.paras(si);
    const prev = list[k - 1] || "", cur = this.text(el);
    const glue = prev && cur && !/\s$/.test(prev) ? " " : "";
    list.splice(k - 1, 2, prev + glue + cur);
    this.redraw(si, k - 1, prev.length + glue.length);
  },

  /** Перерисовать лист и поставить курсор в абзац k раздела si на позицию at. @param {number} si @param {number} k @param {number} at */
  redraw(si, k, at) {
    this.touched();
    const desk = App.$("desk"), top = desk.scrollTop;
    App.report.render(false);
    desk.scrollTop = top;
    const el = document.querySelector(`[data-ed="p"][data-sec="${si}"][data-p="${k}"]`);
    if (!el) return;
    /** @type {HTMLElement} */ (el).focus();
    const walk = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    let node = walk.nextNode(), left = at;
    while (node && left > (node.textContent || "").length) { left -= (node.textContent || "").length; node = walk.nextNode(); }
    const r = document.createRange();
    if (node) r.setStart(node, Math.max(0, left)); else r.setStart(el, 0);
    r.collapse(true);
    const sel = window.getSelection();
    if (sel) { sel.removeAllRanges(); sel.addRange(r); }
  },
};
