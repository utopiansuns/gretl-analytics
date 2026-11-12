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
 *         forms: Object<string, Object<string, string>>, morphology: boolean}}
 */
App.state = { text: "", glossary: [], memory: {}, title: "Эконометрический анализ", brief: false, theme: "auto",
  result: null, findings: [], forms: {}, morphology: true };

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
