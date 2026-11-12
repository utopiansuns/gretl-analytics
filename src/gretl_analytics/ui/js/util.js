// @ts-check
// Общие мелочи интерфейса: создание элементов, задержка, строка состояния, всплывающая подсказка.
"use strict";

/** Пространство имён приложения: модули кладут сюда свои функции. */
window.App = window.App || {};

/**
 * Состояние окна. Сохраняется через Python (storage.py), кроме result и forms.
 * @type {{text: string, glossary: {var: string, ru: string, unit: string}[],
 *         memory: Object<string, {ru: string, unit: string}>, title: string, brief: boolean,
 *         theme: string, result: any, findings: {label: string, text: string}[],
 *         forms: Object<string, Object<string, string>>, morphology: boolean, edited: boolean, original: any}}
 */
App.state = { text: "", glossary: [], memory: {}, title: "Эконометрический анализ", brief: false, theme: "auto",
  result: null, findings: [], forms: {}, morphology: true, edited: false, original: null };

/** @param {string} id @returns {any} */
App.$ = (id) => document.getElementById(id);

App.isMac = /Mac/.test(navigator.platform || navigator.userAgent);

/**
 * Элемент с атрибутами и потомками. Текст вставляется как текст, не как HTML.
 * @param {string} tag @param {Object<string, any>} [attrs] @param {...any} kids @returns {HTMLElement}
 */
App.el = (tag, attrs, ...kids) => {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v == null || v === false) continue;
    if (k === "class") e.className = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v === true ? "" : String(v));
  }
  for (const k of kids.flat()) if (k != null && k !== false) e.append(k);
  return e;
};

/** @param {any} s @returns {string} */
App.esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c] || c));

/** @template {(...a: any[]) => any} F @param {F} fn @param {number} ms */
App.debounce = (fn, ms) => {
  /** @type {any} */ let t;
  return (/** @type {any[]} */ ...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
};

/** @param {string} msg @param {boolean} [err] */
App.status = (msg, err) => {
  const s = App.$("status");
  s.textContent = msg;
  s.classList.toggle("err", !!err);
};

/** @param {string} msg */
App.toast = (msg) => {
  const t = App.$("toast");
  t.textContent = msg;
  t.classList.add("show");
  clearTimeout(App.toast.timer);
  App.toast.timer = setTimeout(() => t.classList.remove("show"), 1800);
};

/** Ширина левой панели: перетаскивание края мышью или стрелками, двойной щелчок – исходная ширина. */
App.sidebar = {
  MIN: 260,
  /** @type {number|null} */ width: null,

  /** @param {number|null|undefined} w */
  set(w) {
    const root = document.documentElement.style;
    if (!w) { this.width = null; root.removeProperty("--sidebar-width"); return; }
    const max = Math.max(this.MIN, Math.min(760, window.innerWidth - 900));   // листу и кнопкам остаётся место
    this.width = Math.round(Math.min(max, Math.max(this.MIN, w)));
    root.setProperty("--sidebar-width", this.width + "px");
  },

  save() { App.call("save_state", { sidebar: this.width }).catch(() => {}); },

  init() {
    const h = App.$("resizer");
    h.addEventListener("pointerdown", (/** @type {PointerEvent} */ e) => {
      e.preventDefault();
      h.setPointerCapture(e.pointerId);
      document.body.classList.add("resizing");
      const move = (/** @type {PointerEvent} */ ev) => this.set(ev.clientX);
      const up = () => {
        h.removeEventListener("pointermove", move);
        document.body.classList.remove("resizing");
        this.save();
      };
      h.addEventListener("pointermove", move);
      h.addEventListener("pointerup", up, { once: true });
    });
    h.addEventListener("dblclick", () => { this.set(null); this.save(); });
    h.addEventListener("keydown", (/** @type {KeyboardEvent} */ e) => {
      if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
      e.preventDefault();
      const now = App.$("sidebar").getBoundingClientRect().width + 8;
      this.set(now + (e.key === "ArrowRight" ? 20 : -20));
      this.save();
    });
    window.addEventListener("resize", () => { if (this.width) this.set(this.width); });
  },
};
