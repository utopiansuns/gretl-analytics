"""Окно приложения: интерфейс из ui/ в нативном окне системы (pywebview).

Windows: Edge WebView2; macOS: WebKit; Linux: Qt WebEngine.
На macOS окно оформлено как системные приложения macOS 26: прозрачная высокая шапка,
кнопки окна над боковой панелью, панель из системного «стекла» (NSVisualEffectView).
"""
import json
import os
import sys
import time

from . import APP_NAME
from .api import Api

UI_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ui")
IS_MAC = sys.platform == "darwin"


def mac_glass(window):
    """Прозрачная шапка во всю высоту панели инструментов и материал боковой панели под страницей.

    Вызывается в главном потоке, пока окно скрыто. Веб-страница рисует прозрачный фон
    там, где должно быть видно стекло (см. ui/css/app.css, класс native-glass).
    """
    import AppKit
    win = window.native
    win.setStyleMask_(win.styleMask() | AppKit.NSWindowStyleMaskFullSizeContentView)
    win.setTitlebarAppearsTransparent_(True)
    win.setTitleVisibility_(AppKit.NSWindowTitleHidden)
    toolbar = AppKit.NSToolbar.alloc().initWithIdentifier_("main")   # пустая: только высота 52 pt, как у Finder
    toolbar.setShowsBaselineSeparator_(False)
    win.setToolbar_(toolbar)
    win.setToolbarStyle_(AppKit.NSWindowToolbarStyleUnified)
    # pywebview заливает контейнер заголовка цветом окна; делаем его прозрачным
    win.contentView().superview().subviews().lastObject().setBackgroundColor_(AppKit.NSColor.clearColor())
    web = win.contentView()
    web.setValue_forKey_(False, "drawsBackground")
    for view in web.subviews():
        if isinstance(view, AppKit.NSVisualEffectView):
            view.setMaterial_(AppKit.NSVisualEffectMaterialSidebar)


def mac_appearance(window, theme):
    """Светлое, тёмное или системное оформление окна (влияет на цвет стекла и кнопок окна)."""
    import AppKit
    from PyObjCTools import AppHelper
    name = {"light": AppKit.NSAppearanceNameAqua, "dark": AppKit.NSAppearanceNameDarkAqua}.get(theme)
    appearance = AppKit.NSAppearance.appearanceNamed_(name) if name else None
    AppHelper.callAfter(lambda: window.native.setAppearance_(appearance))


def _startup(window, api):
    """Фоновый поток после создания окна: оформление, показ, при необходимости самопроверка."""
    window.events.loaded.wait(15)
    if IS_MAC:
        from PyObjCTools import AppHelper
        AppHelper.callAfter(mac_glass, window)
        mac_appearance(window, api.load_state().get("theme", "auto"))
        time.sleep(0.15)
    window.show()
    sample = os.environ.get("GRETL_ANALYTICS_SELFTEST")
    if sample:
        _selftest(window, api, sample)


_EDIT_TEXT = "Первая часть. Вторая часть."
_EDIT_JS = """(function () {
  const el = document.querySelector('[data-ed="p"]:not(.calc)');
  const si = +el.dataset.sec, k = +el.dataset.p, n = App.editor.paras(si).length;
  el.focus(); el.textContent = "%s"; el.dispatchEvent(new Event("input", {bubbles: true}));
  const put = (node, at) => { const r = document.createRange(); r.setStart(node, at); r.collapse(true);
    const s = getSelection(); s.removeAllRanges(); s.addRange(r); };
  put(el.firstChild, 14);
  el.dispatchEvent(new KeyboardEvent("keydown", {key: "Enter", bubbles: true, cancelable: true}));
  const split = App.editor.paras(si).length === n + 1 && App.editor.paras(si)[k + 1] === "Вторая часть.";
  const el2 = document.querySelector('[data-ed="p"][data-sec="' + si + '"][data-p="' + (k + 1) + '"]');
  put(el2.firstChild, 0);
  el2.dispatchEvent(new KeyboardEvent("keydown", {key: "Backspace", bubbles: true, cancelable: true}));
  const merged = App.editor.paras(si).length === n && App.editor.paras(si)[k] === "%s";
  return JSON.stringify({split: split, merged: merged, edited: App.state.edited});
})()""" % (_EDIT_TEXT, _EDIT_TEXT)


def _selftest(window, api, sample):
    """GRETL_ANALYTICS_SELFTEST=<файл>: вставить текст через интерфейс, построить отчёт и закрыться.

    Код выхода 0 означает, что окно, мост JS и Python, ядро, оглавление, правка на листе (Enter делит абзац,
    Backspace соединяет), ширина панели, словарь (заполняется по тексту и очищается вместе с ним)
    и сохранение правок в Word работают в этой сборке.
    GRETL_ANALYTICS_SELFTEST_SHOT=<файл.png> дополнительно сохраняет снимок окна (macOS).
    """
    with open(sample, encoding="utf-8") as f:
        text = f.read()
    time.sleep(1.0)
    window.evaluate_js(f"window.__selftest({json.dumps(text)})")
    n, ok = 0, False
    for _ in range(120):
        time.sleep(0.25)
        n = window.evaluate_js("document.querySelectorAll('.doc-section').length") or 0
        if int(n) >= 3:
            ok = True
            break
    outline = None
    if ok:   # оглавление: после клика по разделу и после прокрутки до конца подсвечен нужный пункт
        js_on = "(document.querySelector('.outline a.on')||{dataset:{}}).dataset.i"
        window.evaluate_js("document.querySelectorAll('.outline a')[2].click()")
        time.sleep(1.5)
        after_click = window.evaluate_js(js_on)
        window.evaluate_js("var d=document.getElementById('desk'); d.scrollTop=d.scrollHeight")
        time.sleep(0.6)
        at_end = window.evaluate_js(js_on)
        outline = {"click": after_click, "end": at_end, "last": str(int(n) - 1)}
        ok = after_click == "2" and at_end == outline["last"]
        window.evaluate_js("document.getElementById('desk').scrollTop=0")
    editing = None
    if ok:   # правка на листе: Enter делит абзац по курсору, Backspace в начале соединяет обратно
        editing = json.loads(window.evaluate_js(_EDIT_JS) or "{}")
        editing["sidebar"] = window.evaluate_js(
            "App.sidebar.set(440); Math.round(document.getElementById('sidebar').getBoundingClientRect().width)")
        # панель расширилась, а кнопка «Сформировать» осталась видна целиком
        editing["run_visible"] = window.evaluate_js(
            "document.getElementById('run').getBoundingClientRect().right <= window.innerWidth")
        ok = (editing.get("split") and editing.get("merged") and int(editing["sidebar"] or 0) > 400
              and editing["run_visible"] is True)
    word = None
    if ok:   # отчёт Word: в сборке нужны шаблоны python-docx, их отсутствие ловится только здесь
        import tempfile
        try:
            with tempfile.TemporaryDirectory() as tmp:
                edits = json.loads(window.evaluate_js(
                    "JSON.stringify({sections: App.state.result.sections, findings: App.state.findings})"))
                out = api.export_word("full", None, os.path.join(tmp, "selftest.docx"), edits)
                word = out.get("error") or (bool(out.get("path")) and os.path.getsize(out["path"]) > 0)
                if word is True:
                    import docx
                    word = any(p.text == _EDIT_TEXT for p in docx.Document(out["path"]).paragraphs) or "правка не попала в Word"
        except Exception as e:
            word = repr(e)
        ok = word is True
    glossary = None
    if ok:   # словарь повторяет текст: после вставки заполнен, после очистки поля пуст
        filled = window.evaluate_js("App.state.glossary.length") or 0
        window.evaluate_js("document.getElementById('erase').click()")
        time.sleep(1.5)
        emptied = window.evaluate_js("App.state.glossary.length")
        glossary = {"filled": filled, "after_erase": emptied}
        ok = int(filled) > 0 and emptied == 0
    shot = os.environ.get("GRETL_ANALYTICS_SELFTEST_SHOT")
    if shot and IS_MAC:
        import subprocess
        time.sleep(0.8)
        subprocess.run(["screencapture", "-x", "-o", "-l", str(window.native.windowNumber()), shot], check=False)
    log = os.environ.get("GRETL_ANALYTICS_SELFTEST_LOG")
    if log:
        with open(log, "w", encoding="utf-8") as f:
            json.dump({"ok": ok, "sections": n, "outline": outline, "editing": editing, "glossary": glossary,
                       "word": word}, f, ensure_ascii=False)
    window.destroy()
    os._exit(0 if ok else 3)


def mac_no_autocorrect():
    """Отключает автозамену macOS только для этого процесса: заглавную букву в начале поля,
    исправление «опечаток» в именах переменных, замену дефиса на длинное тире.
    Значения кладутся во временный домен аргументов, системные настройки не меняются."""
    try:
        import Foundation
        d = Foundation.NSUserDefaults.standardUserDefaults()
        dom = dict(d.volatileDomainForName_(Foundation.NSArgumentDomain) or {})
        dom.update(dict.fromkeys((
            "NSAutomaticCapitalizationEnabled", "NSAutomaticSpellingCorrectionEnabled",
            "NSAutomaticPeriodSubstitutionEnabled", "NSAutomaticDashSubstitutionEnabled",
            "NSAutomaticTextCompletionEnabled", "WebAutomaticSpellingCorrectionEnabled"), False))
        d.setVolatileDomain_forName_(dom, Foundation.NSArgumentDomain)
    except Exception:   # без PyObjC окно всё равно откроется
        pass


def _free_port():
    import socket
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def run():
    import webview
    if IS_MAC:
        mac_no_autocorrect()
    webview.settings["DRAG_REGION_DIRECT_TARGET_ONLY"] = True   # перетаскивание окна только за пустое место
    api = Api(on_theme=None)
    window = webview.create_window(
        APP_NAME, url=os.path.join(UI_DIR, "index.html"), js_api=api, hidden=True,
        width=1360, height=880, min_size=(1000, 660), vibrancy=IS_MAC,
        background_color="#F5F6F8", text_select=True)
    api._attach(window, on_theme=(lambda theme: mac_appearance(window, theme)) if IS_MAC else None)
    # Свой свободный порт на каждый запуск. Без этого pywebview берёт фиксированный 42001, и второе окно
    # (например, новая версия при открытой старой) показывает интерфейс первого.
    webview.start(_startup, (window, api), debug=bool(os.environ.get("GRETL_ANALYTICS_DEBUG")),
                  private_mode=False, http_port=_free_port())
    return 0


if __name__ == "__main__":
    sys.exit(run())
