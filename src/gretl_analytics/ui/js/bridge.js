// @ts-check
// Мост к Python: методы класса Api (api.py) доступны как window.pywebview.api.<имя>.
"use strict";

App.ready = new Promise((resolve) => {
  if (window.pywebview && window.pywebview.api) resolve(undefined);
  else window.addEventListener("pywebviewready", () => resolve(undefined));
});

/**
 * Вызов метода Python. Ошибка из Python приходит как {ok: false, error} и превращается в исключение.
 * @param {string} name @param {...any} args @returns {Promise<any>}
 */
App.call = async (name, ...args) => {
  await App.ready;
  const r = await window.pywebview.api[name](...args);
  if (!r || !r.ok) throw new Error((r && r.error) || "Не удалось выполнить действие.");
  return r;
};

/** Сохранение состояния с задержкой, чтобы не писать на диск на каждое нажатие клавиши. */
App.persist = App.debounce(() => {
  const S = App.state;
  App.call("save_state", { text: S.text, glossary: S.glossary, memory: S.memory, title: S.title, brief: S.brief }).catch(() => {});
}, 400);
