"""Точка входа собранного приложения (PyInstaller): открывает окно «Аналитики Gretl».

Windows. Файлы из скачанного архива помечены как полученные из Интернета (поток Zone.Identifier,
Mark of the Web), и .NET Framework отказывается загружать такие сборки: окно падает с ошибкой
«Failed to resolve Python.Runtime.Loader.Initialize». Поэтому до открытия окна приложение снимает
пометку со своих .dll, а если окно всё же не запустилось, объясняет, что делать.

GRETL_ANALYTICS_CHECK=<файл.json> – проверка сборки без окна (для CI): снять пометку, загрузить
компоненты окна, записать результат в файл, код выхода 0 при успехе.
GRETL_ANALYTICS_NO_UNBLOCK=1 – не снимать пометку (чтобы в CI воспроизвести исходную ошибку).
"""
import json
import os
import sys

WINDOWS = sys.platform == "win32"
APP_DIR = os.path.dirname(os.path.abspath(sys.executable if getattr(sys, "frozen", False) else __file__))


def unblock(root=APP_DIR):
    """Снимает пометку «из Интернета» с .dll приложения. Возвращает число снятых пометок.

    На дисках без NTFS (FAT, exFAT) пометок нет, и ошибки просто пропускаются."""
    removed = 0
    for folder, _, files in os.walk(root):
        for name in files:
            if name.lower().endswith(".dll"):
                try:
                    os.remove(os.path.join(folder, name) + ":Zone.Identifier")
                    removed += 1
                except OSError:
                    pass
    return removed


def explain(error):
    """Понятное сообщение вместо трассировки, если окно не запустилось."""
    import ctypes
    text = ("Не удалось открыть окно приложения.\n\n"
            "Чаще всего Windows заблокировала файлы, скачанные из Интернета. Удалите распакованную папку, "
            "щёлкните по скачанному архиву правой кнопкой мыши → «Свойства» → отметьте «Разблокировать» → OK "
            "и распакуйте архив заново. Папку лучше держать на диске C:, например в «Документах».\n\n"
            "Если не помогло, установите с сайта Microsoft .NET Framework 4.8 и Microsoft Edge WebView2 Runtime.\n\n"
            f"Подробности: {error}")
    ctypes.windll.user32.MessageBoxW(None, text, "Аналитика для Gretl", 0x10)


def check(path):
    """Проверка без окна: загружаются ли .NET и компоненты окна pywebview."""
    result = {"unblocked": 0, "ok": False}
    try:
        if not os.environ.get("GRETL_ANALYTICS_NO_UNBLOCK"):
            result["unblocked"] = unblock()
        import importlib
        importlib.import_module("clr")                         # .NET через pythonnet
        importlib.import_module("webview.platforms.winforms")  # окно на WinForms и WebView2
        result["ok"] = True
    except Exception as e:  # noqa: BLE001
        result["error"] = f"{type(e).__name__}: {e}"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False)
    return 0 if result["ok"] else 1


def main():
    if os.environ.get("GRETL_ANALYTICS_CHECK"):
        return check(os.environ["GRETL_ANALYTICS_CHECK"])
    if WINDOWS and not os.environ.get("GRETL_ANALYTICS_NO_UNBLOCK"):
        unblock()
    from gretl_analytics.app import run
    try:
        return run()
    except Exception as e:  # noqa: BLE001
        if not WINDOWS:
            raise
        explain(f"{type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
