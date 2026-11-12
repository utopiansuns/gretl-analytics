"""Методы, которые интерфейс вызывает из окна приложения (window.pywebview.api.*).

Каждый метод возвращает словарь {"ok": True, ...} или {"ok": False, "error": "..."}:
ошибка показывается в интерфейсе понятным текстом и не роняет окно.
"""
import functools
import os
import re
import subprocess
import sys

from . import clipboard
from .core.analysis import analyze_blocks, find_variables
from .core.parsing import detect_kind, split_text
from .report import key_findings, to_docx
from .storage import Storage


def _plain(obj):
    """Только типы JSON: NaN и бесконечности превращаются в None (иначе JSON.parse в окне упадёт)."""
    import math
    if isinstance(obj, dict):
        return {str(k): _plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple, set)):
        return [_plain(v) for v in obj]
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    return str(obj)


def _safe(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            res = fn(*args, **kwargs)
            return _plain({"ok": True, **(res or {})})
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    return wrapper


def open_file(path):
    """Открывает файл программой по умолчанию (Word, LibreOffice…)."""
    if sys.platform == "darwin":
        subprocess.Popen(["open", path])
    elif os.name == "nt":
        os.startfile(path)  # noqa: S606
    else:
        subprocess.Popen(["xdg-open", path])


class Api:
    def __init__(self, storage=None, on_theme=None):
        self._storage = storage or Storage()
        self._result = None
        self._window = None
        self._on_theme = on_theme

    def _attach(self, window, on_theme=None):
        self._window = window
        self._on_theme = on_theme

    @_safe
    def load_state(self):
        return self._storage.load()

    @_safe
    def save_state(self, data):
        self._storage.save(data or {})

    @_safe
    def platform(self):
        """Что умеет окно: на macOS страница рисует прозрачный фон поверх системного стекла."""
        native_glass = sys.platform == "darwin" and self._window is not None
        return {"os": sys.platform, "glass": native_glass}

    @_safe
    def set_theme(self, theme):
        """auto, light или dark: сохраняется и применяется к окну (на macOS меняет и цвет стекла)."""
        theme = theme if theme in ("auto", "light", "dark") else "auto"
        self._storage.save({"theme": theme})
        if self._on_theme:
            self._on_theme(theme)

    @_safe
    def analyze(self, text, glossary, title):
        out = self._storage.new_run()
        res = analyze_blocks([{"kind": "auto", "text": text or ""}], out, title=title,
                             glossary=[g for g in (glossary or []) if (g.get("var") or "").strip()])
        self._result = res
        return {"result": res, "findings": [{"label": a, "text": b} for a, b in key_findings(res)]}

    @_safe
    def detect(self, text):
        """Что найдено во вставленном тексте: {"model": 2, "test": 1, …} (для подсказки под полем ввода)."""
        counts = {}
        for kind, part in split_text(text or ""):
            kind = kind or detect_kind(part)
            if kind != "unknown":
                counts[kind] = counts.get(kind, 0) + 1
        return {"kinds": counts}

    @_safe
    def variables(self, text, glossary):
        return find_variables(text or "", glossary or [])

    @_safe
    def read_clipboard(self):
        return {"text": clipboard.read_text()}

    @_safe
    def copy(self, text, html=None):
        return {"copied": clipboard.write(text or "", html)}

    @_safe
    def export_word(self, mode="full", title=None, path=None):
        """Сохраняет отчёт: path задаётся в тестах, в приложении открывается диалог сохранения."""
        if not self._result:
            raise RuntimeError("Сначала сформируйте аналитику.")
        mode = "brief" if mode == "brief" else "full"
        name = re.sub(r'[\\/:*?"<>|]+', "_", (title or "Отчёт").strip()) or "Отчёт"
        name += " (кратко).docx" if mode == "brief" else ".docx"
        if path is None:
            import webview
            chosen = self._window.create_file_dialog(webview.SAVE_DIALOG, save_filename=name,
                                                     file_types=("Документ Word (*.docx)",))
            if not chosen:
                return {"cancelled": True}
            path = chosen if isinstance(chosen, str) else chosen[0]
            if not path.lower().endswith(".docx"):
                path += ".docx"
            to_docx(dict(self._result, title=title or self._result.get("title")), path, mode=mode)
            open_file(path)
        else:
            to_docx(dict(self._result, title=title or self._result.get("title")), path, mode=mode)
        return {"path": path}
