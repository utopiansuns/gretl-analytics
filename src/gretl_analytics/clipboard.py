"""Буфер обмена без внешних зависимостей: чтение текста и запись текста вместе с HTML.

HTML нужен, чтобы раздел с таблицами вставлялся в Word уже оформленным.
macOS: NSPasteboard (pyobjc приходит вместе с pywebview) или pbcopy/pbpaste.
Windows: Win32 API через ctypes (форматы CF_UNICODETEXT и «HTML Format»).
Linux: wl-clipboard или xclip, если установлены.
"""
import shutil
import subprocess
import sys


# ------------------------------------------------------------------ macOS

def _mac_read():
    try:
        from AppKit import NSPasteboard, NSPasteboardTypeString
        return NSPasteboard.generalPasteboard().stringForType_(NSPasteboardTypeString) or ""
    except Exception:  # noqa: BLE001
        return subprocess.run(["pbpaste"], capture_output=True, text=True, encoding="utf-8").stdout


def _mac_write(text, html):
    try:
        from AppKit import NSPasteboard, NSPasteboardTypeHTML, NSPasteboardTypeString
        pb = NSPasteboard.generalPasteboard()
        pb.clearContents()
        if html:
            pb.setString_forType_(html, NSPasteboardTypeHTML)
        pb.setString_forType_(text, NSPasteboardTypeString)
        return True
    except Exception:  # noqa: BLE001
        subprocess.run(["pbcopy"], input=text, text=True, encoding="utf-8", check=False)
        return True


# ------------------------------------------------------------------ Windows

def _win_api():
    import ctypes
    from ctypes import wintypes
    u32, k32 = ctypes.windll.user32, ctypes.windll.kernel32
    u32.OpenClipboard.argtypes = [wintypes.HWND]
    u32.GetClipboardData.restype = wintypes.HANDLE
    u32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    u32.RegisterClipboardFormatW.argtypes = [wintypes.LPCWSTR]
    k32.GlobalAlloc.restype = wintypes.HGLOBAL
    k32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    k32.GlobalLock.restype = wintypes.LPVOID
    k32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    return ctypes, u32, k32


def _win_read():
    ctypes, u32, k32 = _win_api()
    if not u32.OpenClipboard(None):
        return ""
    try:
        h = u32.GetClipboardData(13)  # CF_UNICODETEXT
        if not h:
            return ""
        p = k32.GlobalLock(h)
        try:
            return ctypes.wstring_at(p)
        finally:
            k32.GlobalUnlock(h)
    finally:
        u32.CloseClipboard()


def _cf_html(fragment):
    """Формат «HTML Format» Windows: заголовок со смещениями в байтах UTF-8."""
    pre = "<html><body><!--StartFragment-->"
    post = "<!--EndFragment--></body></html>"
    header = ("Version:0.9\r\nStartHTML:{0:010d}\r\nEndHTML:{1:010d}\r\n"
              "StartFragment:{2:010d}\r\nEndFragment:{3:010d}\r\n")
    dummy = header.format(0, 0, 0, 0)
    start_html = len(dummy.encode("utf-8"))
    start_frag = start_html + len(pre.encode("utf-8"))
    end_frag = start_frag + len(fragment.encode("utf-8"))
    end_html = end_frag + len(post.encode("utf-8"))
    return (header.format(start_html, end_html, start_frag, end_frag) + pre + fragment + post).encode("utf-8")


def _win_write(text, html):
    ctypes, u32, k32 = _win_api()

    def put(fmt, data):
        h = k32.GlobalAlloc(0x0002, len(data))  # GMEM_MOVEABLE
        p = k32.GlobalLock(h)
        ctypes.memmove(p, data, len(data))
        k32.GlobalUnlock(h)
        u32.SetClipboardData(fmt, h)

    if not u32.OpenClipboard(None):
        return False
    try:
        u32.EmptyClipboard()
        put(13, (text + "\0").encode("utf-16-le"))
        if html:
            put(u32.RegisterClipboardFormatW("HTML Format"), _cf_html(html) + b"\0")
        return True
    finally:
        u32.CloseClipboard()


# ------------------------------------------------------------------ Linux

def _linux_read():
    for cmd in (["wl-paste", "--no-newline"], ["xclip", "-selection", "clipboard", "-o"], ["xsel", "-b", "-o"]):
        if shutil.which(cmd[0]):
            return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8").stdout
    return None


def _linux_write(text, html):
    if html and shutil.which("wl-copy"):
        subprocess.run(["wl-copy", "--type", "text/html"], input=html, text=True, encoding="utf-8", check=False)
        return True
    if html and shutil.which("xclip"):
        subprocess.run(["xclip", "-selection", "clipboard", "-t", "text/html"], input=html, text=True,
                       encoding="utf-8", check=False)
        return True
    for cmd in (["wl-copy"], ["xclip", "-selection", "clipboard"], ["xsel", "-b", "-i"]):
        if shutil.which(cmd[0]):
            subprocess.run(cmd, input=text, text=True, encoding="utf-8", check=False)
            return True
    return False


# ------------------------------------------------------------------

def read_text():
    """Текст из буфера обмена или None, если на этой системе прочитать нельзя."""
    try:
        if sys.platform == "darwin":
            return _mac_read()
        if sys.platform == "win32":
            return _win_read()
        return _linux_read()
    except Exception:  # noqa: BLE001
        return None


def write(text, html=None):
    """Кладёт в буфер текст и (если передан) HTML. True, если получилось."""
    try:
        if sys.platform == "darwin":
            return _mac_write(text, html)
        if sys.platform == "win32":
            return _win_write(text, html)
        return _linux_write(text, html)
    except Exception:  # noqa: BLE001
        return False
