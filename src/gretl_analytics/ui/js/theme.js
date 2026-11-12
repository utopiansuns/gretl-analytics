// @ts-check
// Светлая, тёмная или системная тема. Страница отчёта следует теме (paper.css).
"use strict";

App.theme = {
  media: window.matchMedia("(prefers-color-scheme: dark)"),

  /** Применить выбор: auto следует за системой. @param {string} choice */
  apply(choice) {
    const dark = choice === "dark" || (choice === "auto" && this.media.matches);
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    document.querySelectorAll("[data-theme-choice]").forEach((b) =>
      b.setAttribute("aria-checked", String(/** @type {HTMLElement} */ (b).dataset.themeChoice === choice)));
  },

  /** Выбор пользователя: применить, запомнить и передать окну (на macOS меняет цвет стекла). @param {string} choice */
  set(choice) {
    App.state.theme = choice;
    this.apply(choice);
    App.call("set_theme", choice).catch(() => {});
  },

  init() {
    document.querySelectorAll("[data-theme-choice]").forEach((b) =>
      b.addEventListener("click", () => this.set(/** @type {HTMLElement} */ (b).dataset.themeChoice || "auto")));
    this.media.addEventListener("change", () => this.apply(App.state.theme));
    this.apply(App.state.theme);
  },
};
