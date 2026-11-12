// @ts-check
// Сборка интерфейса: ввод, режимы, формирование отчёта и сохранение в Word.
"use strict";

(function () {
  const S = App.state, $ = App.$;
  const KINDS = { data: "описание данных", summary: "описательная статистика", model: "модель", test: "тест",
    forecast: "прогноз", corr: "корреляции" };

  /** @param {"input"|"glossary"} name */
  function showTab(name) {
    for (const t of ["input", "glossary"]) {
      $("tab-" + t).setAttribute("aria-selected", String(t === name));
      $("panel-" + t).hidden = t !== name;
    }
  }

  const detect = App.debounce(async () => {
    const out = $("detected");
    if (!S.text.trim()) { out.textContent = ""; return; }
    try {
      const r = await App.call("detect", S.text);
      const parts = Object.entries(r.kinds).map(([k, n]) => `${KINDS[/** @type {keyof KINDS} */ (k)] || k}${Number(n) > 1 ? " ×" + n : ""}`);
      out.innerHTML = parts.length ? "Найдено: <b>" + App.esc(parts.join(", ")) + "</b>"
        : "Вывод Gretl не найден. Нужны таблица коэффициентов, тест, статистика или прогноз.";
    } catch (e) { out.textContent = ""; }
  }, 350);

  /** @param {string} t */
  function setText(t) { S.text = t; $("text").value = t; App.persist(); detect(); App.glossary.sync(); }

  /** @param {boolean} append */
  async function paste(append) {
    let t = null;
    try { t = (await App.call("read_clipboard")).text; } catch (e) { /* ниже подсказка */ }
    if (t == null) {
      $("text").focus();
      App.status(`Нажмите ${App.isMac ? "⌘V" : "Ctrl+V"} в поле ввода: прямой доступ к буферу на этой системе недоступен.`, true);
      return;
    }
    if (!t.trim()) { App.status("Буфер обмена пуст. Скопируйте вывод в Gretl и попробуйте снова.", true); return; }
    setText(append && S.text.trim() ? S.text.replace(/\s+$/, "") + "\n\n" + t : t);
    App.status(append ? "Фрагмент добавлен в конец." : "Текст вставлен.");
  }

  async function run() {
    if (!S.text.trim()) { App.status("Вставьте вывод Gretl в панель слева.", true); showTab("input"); $("text").focus(); return; }
    const b = $("run");
    b.disabled = true;
    App.status("Формирую аналитику…");
    try {
      await App.glossary.syncNow();   // словарь должен соответствовать тексту до расчёта
      const r = await App.call("analyze", S.text, S.glossary, S.title);
      S.result = r.result;
      S.findings = r.findings || [];
      App.report.render(true);
      $("desk").scrollTop = 0;
      App.status(r.result.warnings.length ? "Готово, есть замечания: они в начале отчёта." : "Готово. Отчёт можно копировать или сохранить в Word.");
    } catch (e) { App.status(/** @type {Error} */ (e).message, true); }
    finally { b.disabled = false; }
  }

  async function saveWord() {
    if (!S.result) return;
    App.status("Сохраняю отчёт…");
    try {
      const r = await App.call("export_word", S.brief ? "brief" : "full", S.title);
      App.status(r.cancelled ? "Сохранение отменено." : "Отчёт сохранён и открыт.");
    } catch (e) { App.status(/** @type {Error} */ (e).message, true); }
  }

  /** @param {boolean} brief */
  function setMode(brief) {
    S.brief = brief;
    $("mode-full").setAttribute("aria-checked", String(!brief));
    $("mode-brief").setAttribute("aria-checked", String(brief));
    App.report.render(false);
    App.persist();
  }

  $("tab-input").onclick = () => showTab("input");
  $("tab-glossary").onclick = () => showTab("glossary");
  $("mode-full").onclick = () => setMode(false);
  $("mode-brief").onclick = () => setMode(true);
  $("title").oninput = (/** @type {Event} */ e) => { S.title = /** @type {HTMLInputElement} */ (e.target).value; App.persist(); };
  $("text").oninput = (/** @type {Event} */ e) => { S.text = /** @type {HTMLTextAreaElement} */ (e.target).value; App.persist(); detect(); App.glossary.sync(); };
  $("paste").onclick = () => paste(false);
  $("append").onclick = () => paste(true);
  $("erase").onclick = () => { setText(""); App.status("Поле очищено."); };
  $("add-row").onclick = () => App.glossary.add();
  $("run").onclick = run;
  $("save-word").onclick = saveWord;
  $("copy-all").onclick = () => App.report.copyAll();
  $("run-kbd").textContent = App.isMac ? "⌘↵" : "Ctrl+Enter";
  document.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) { e.preventDefault(); run(); }
    if (e.key === "Escape") App.report.closeMenus();
  });
  document.addEventListener("click", () => App.report.closeMenus());

  // самопроверка собранного приложения (app.py, GRETL_ANALYTICS_SELFTEST)
  window.__selftest = (/** @type {string} */ text) => { setText(text); run(); };

  (async function init() {
    App.theme.init();
    try {
      const p = await App.call("platform");
      document.documentElement.classList.toggle("native-glass", !!p.glass);
    } catch (e) { /* обычное окно */ }
    try {
      const st = await App.call("load_state");
      Object.assign(S, { text: st.text || "", glossary: st.glossary || [], memory: st.memory || {}, title: st.title || S.title,
        brief: !!st.brief, theme: st.theme || "auto" });
    } catch (e) { /* первое открытие */ }
    $("text").value = S.text;
    $("title").value = S.title;
    App.theme.apply(S.theme);
    $("mode-full").setAttribute("aria-checked", String(!S.brief));
    $("mode-brief").setAttribute("aria-checked", String(S.brief));
    App.glossary.render();
    App.glossary.refreshForms();
    App.glossary.sync();
    detect();
  })();
})();
