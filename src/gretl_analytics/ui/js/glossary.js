// @ts-check
// Словарь переменных: имя в Gretl → русское название и единицы. Падежи считает Python (core/morph.py).
// Словарь повторяет текст: переменные из вставки добавляются, исчезнувшие из неё убираются.
// Правки пользователя запоминаются по имени переменной (state.memory) и возвращаются при следующей вставке.
"use strict";

App.glossary = {
  /** Падежные формы пересчитываются после паузы в наборе. */
  refreshForms: App.debounce(async () => {
    const g = App.state.glossary.filter((e) => e.var && e.ru);
    try {
      const r = await App.call("variables", "", g);
      App.state.forms = r.forms || {};
      App.state.morphology = r.morphology;
      App.glossary.paintForms();
    } catch (e) { /* формы необязательны */ }
  }, 400),

  render() {
    const S = App.state, box = App.$("glossary"), el = App.el;
    box.replaceChildren();
    App.$("gl-count").textContent = S.glossary.length ? String(S.glossary.length) : "";
    if (!S.morphology) box.append(el("p", { class: "caption" }, "Склонение недоступно: не найден словарь pymorphy3."));
    if (!S.glossary.length) {
      box.append(el("p", { class: "gl-empty" }, "Словарь пуст. Вставьте вывод Gretl: переменные появятся здесь сами."));
      return;
    }
    // имена и названия пишутся как введены: без автозаглавной буквы и автоисправления
    const plain = { autocapitalize: "off", autocorrect: "off", autocomplete: "off", spellcheck: "false" };
    S.glossary.forEach((entry, i) => {
      /** @param {"var"|"ru"|"unit"} key */
      const update = (key) => (/** @type {Event} */ ev) => {
        const e = S.glossary[i];
        e[key] = /** @type {HTMLInputElement} */ (ev.target).value;
        if (e.var) S.memory[e.var] = { ru: e.ru || "", unit: e.unit || "" };
        App.persist();
        App.glossary.refreshForms();
      };
      box.append(el("div", { class: "gl-row" },
        el("input", { ...plain, class: "var", value: entry.var || "", placeholder: "price", "aria-label": "Имя в Gretl", oninput: update("var") }),
        el("input", { ...plain, value: entry.ru || "", placeholder: "цена дома", "aria-label": "Название по-русски", oninput: update("ru") }),
        el("input", { ...plain, value: entry.unit || "", placeholder: "тыс. долл.", "aria-label": "Единицы", oninput: update("unit") }),
        el("button", { class: "gl-del", title: "Удалить", "aria-label": "Удалить " + (entry.var || "строку"),
          onclick: () => { S.glossary.splice(i, 1); App.persist(); App.glossary.render(); App.glossary.refreshForms(); } }, "×"),
        el("span"),
        el("div", { class: "gl-forms" })));
    });
    this.paintForms();
  },

  paintForms() {
    document.querySelectorAll(".gl-row").forEach((row, i) => {
      const entry = App.state.glossary[i];
      const f = entry && App.state.forms[entry.var];
      const node = /** @type {HTMLElement} */ (row.querySelector(".gl-forms"));
      node.textContent = f ? [f.gen, f.dat, f.ins].join(", ") : "";
      node.title = f ? `Кого? чего? ${f.gen}\nКому? чему? ${f.dat}\nКого? что? ${f.acc}\nКем? чем? ${f.ins}` : "";
    });
  },

  /** Привести словарь к переменным текущего текста. */
  async syncNow() {
    const S = App.state, note = App.$("gl-note");
    /** @type {{name: string, suggest: string, unit: string}[]} */
    let found = [];
    if (S.text.trim()) {
      try { found = (await App.call("variables", S.text, [])).variables || []; } catch (e) { return; }
    }
    const old = new Map(S.glossary.map((e) => [e.var, e]));
    const next = found.map((v) => old.get(v.name)
      || { var: v.name, ...(S.memory[v.name] || { ru: v.suggest || "", unit: v.unit || "" }) });
    const blank = S.glossary.filter((e) => !e.var);          // строка, которую пользователь ещё заполняет
    const added = found.filter((v) => !old.has(v.name)).length;
    const removed = S.glossary.filter((e) => e.var && !found.some((v) => v.name === e.var)).length;
    if (!added && !removed) return;
    S.glossary = next.concat(blank);
    note.textContent = [added && `Добавлено: ${added}`, removed && `убрано: ${removed}`].filter(Boolean).join(", ")
      + (added ? ". Проверьте названия: их можно исправить." : ".");
    App.persist();
    App.glossary.render();
    App.glossary.refreshForms();
  },

  /** То же с паузой: вызывается при наборе и вставке текста. */
  sync: App.debounce(() => App.glossary.syncNow(), 400),

  add() {
    App.state.glossary.push({ var: "", ru: "", unit: "" });
    this.render();
    const inputs = document.querySelectorAll(".gl-row .var");
    /** @type {HTMLElement} */ (inputs[inputs.length - 1]).focus();
  },
};
