#!/usr/bin/env python3
"""Сборка автономного приложения «Аналитика для Gretl» для текущей системы.

  macOS   → dist/Аналитика для Gretl.app и dist/Analitika-dlya-Gretl-<версия>-macOS-<arch>.dmg
  Windows → dist/Analitika-dlya-Gretl-<версия>-Windows-x64.zip (внутри GretlAnalytics.exe)
  Linux   → dist/Analitika-dlya-Gretl-<версия>-Linux-x64.tar.gz

Python и все библиотеки упаковываются внутрь: на целевом компьютере ничего ставить не нужно.
Запуск из корня проекта: python packaging/build.py  (после pip install -e ".[build]")
"""
import os
import platform
import plistlib
import shutil
import subprocess
import sys
import tarfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DIST = os.path.join(ROOT, "dist")
WORK = os.path.join(ROOT, "build")
NAME = "GretlAnalytics"
DISPLAY = "Аналитика для Gretl"
BUNDLE_ID = "io.github.gretl-analytics"

sys.path.insert(0, os.path.join(ROOT, "src"))
from gretl_analytics import __version__ as VERSION  # noqa: E402


def run(cmd):
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)


def pyinstaller():
    sep = ";" if os.name == "nt" else ":"
    ui = os.path.join(ROOT, "src", "gretl_analytics", "ui")
    icon = os.path.join(HERE, "icons", "icon.icns" if sys.platform == "darwin" else "icon.ico")
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
           "--name", NAME, "--distpath", DIST, "--workpath", WORK, "--specpath", WORK,
           "--paths", os.path.join(ROOT, "src"), "--icon", icon,
           "--add-data", f"{ui}{sep}gretl_analytics/ui",
           "--add-data", f"{os.path.join(ROOT, 'src', 'gretl_analytics', 'core', 'gretl_vars.tsv')}{sep}gretl_analytics/core",
           "--collect-data", "pymorphy3_dicts_ru", "--collect-data", "docx",
           "--collect-submodules", "pymorphy3", "--collect-submodules", "gretl_analytics",
           "--collect-all", "webview", "--hidden-import", "pymorphy3_dicts_ru",
           # python-docx ищет шаблоны по пути docx/parts/../templates: папка docx/parts должна существовать
           "--add-data", f"{os.path.join(HERE, 'docx-parts.keep')}{sep}docx/parts"]
    if sys.platform == "darwin":
        cmd += ["--osx-bundle-identifier", BUNDLE_ID]
    run(cmd + [os.path.join(HERE, "launcher.py")])


def mac_app():
    src = os.path.join(DIST, f"{NAME}.app")
    app = os.path.join(DIST, f"{DISPLAY}.app")
    shutil.rmtree(app, ignore_errors=True)
    os.rename(src, app)
    plist = os.path.join(app, "Contents", "Info.plist")
    with open(plist, "rb") as f:
        info = plistlib.load(f)
    info.update({"CFBundleName": DISPLAY, "CFBundleDisplayName": DISPLAY, "CFBundleShortVersionString": VERSION,
                 "CFBundleVersion": VERSION, "LSMinimumSystemVersion": "11.0", "NSHighResolutionCapable": True,
                 "LSApplicationCategoryType": "public.app-category.education"})
    with open(plist, "wb") as f:
        plistlib.dump(info, f)
    run(["codesign", "--force", "--deep", "--sign", "-", app])
    return app


def mac_dmg(app):
    dmg = os.path.join(DIST, f"Analitika-dlya-Gretl-{VERSION}-macOS-{platform.machine()}.dmg")
    stage = os.path.join(WORK, "dmg")
    shutil.rmtree(stage, ignore_errors=True)
    os.makedirs(stage)
    run(["ditto", app, os.path.join(stage, os.path.basename(app))])
    os.symlink("/Applications", os.path.join(stage, "Applications"))
    shutil.copy(os.path.join(HERE, "dmg-readme.txt"), os.path.join(stage, "Как установить.txt"))
    if os.path.exists(dmg):
        os.remove(dmg)
    run(["hdiutil", "create", "-volname", DISPLAY, "-srcfolder", stage, "-ov", "-format", "UDZO", dmg])
    return dmg


def archive():
    folder = os.path.join(DIST, NAME)
    if os.name == "nt":
        out = os.path.join(DIST, f"Analitika-dlya-Gretl-{VERSION}-Windows-x64.zip")
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            for dp, _, files in os.walk(folder):
                for fn in files:
                    p = os.path.join(dp, fn)
                    z.write(p, os.path.join(NAME, os.path.relpath(p, folder)))
        return out
    out = os.path.join(DIST, f"Analitika-dlya-Gretl-{VERSION}-Linux-x64.tar.gz")
    with tarfile.open(out, "w:gz") as t:
        t.add(folder, arcname=NAME)
    return out


def main():
    pyinstaller()
    if sys.platform == "darwin":
        out = mac_dmg(mac_app())
        shutil.rmtree(os.path.join(DIST, NAME), ignore_errors=True)   # промежуточная папка, всё уже в .app
    else:
        out = archive()
    print("\nГотово:", out)


if __name__ == "__main__":
    main()
