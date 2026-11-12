"""Запуск: без аргументов открывается окно приложения; подкоманды работают без интерфейса.

  gretl-analytics                                   окно приложения
  gretl-analytics paste  --text out.txt [--glossary g.json] [--title T] --out DIR
  gretl-analytics vars   --text out.txt [--glossary g.json]
  gretl-analytics export --result DIR/result.json --out report.docx [--mode full|brief]
  gretl-analytics doctor
Ответы подкоманд печатаются одной строкой JSON.
"""
import argparse
import json
import os
import sys
import traceback


def _out(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False, default=str) + "\n")


def _read(path, default=""):
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return f.read()
    return default


def main(argv=None):
    ap = argparse.ArgumentParser(prog="gretl-analytics", description="Аналитика для Gretl")
    sub = ap.add_subparsers(dest="cmd")
    a = sub.add_parser("paste", help="аналитика по тексту вывода Gretl")
    a.add_argument("--text", required=True, help="файл с выводом Gretl")
    a.add_argument("--glossary", help='JSON: [{"var": "price", "ru": "цена", "unit": "тыс. долл."}]')
    a.add_argument("--title")
    a.add_argument("--out", required=True)
    a = sub.add_parser("vars", help="переменные в тексте и формы русских названий")
    a.add_argument("--text", required=True)
    a.add_argument("--glossary")
    a = sub.add_parser("export", help="отчёт Word")
    a.add_argument("--result", required=True)
    a.add_argument("--out", required=True)
    a.add_argument("--mode", default="full", choices=["full", "brief"])
    sub.add_parser("doctor", help="проверка окружения")
    args = ap.parse_args(argv)

    if args.cmd is None:
        from .app import run
        return run()
    try:
        if args.cmd == "paste":
            from .core.analysis import analyze_blocks
            res = analyze_blocks([{"kind": "auto", "text": _read(args.text)}], args.out, title=args.title,
                                 glossary=json.loads(_read(args.glossary, "[]")))
            _out({"ok": True, "result": os.path.join(args.out, "result.json"), "sections": len(res["sections"]),
                  "warnings": res["warnings"], "unverified": res["verification"]["unverified"]})
        elif args.cmd == "vars":
            from .core.analysis import find_variables
            _out({"ok": True, **find_variables(_read(args.text), json.loads(_read(args.glossary, "[]")))})
        elif args.cmd == "export":
            from .report import to_docx
            with open(args.result, encoding="utf-8") as f:
                to_docx(json.load(f), args.out, mode=args.mode)
            _out({"ok": True, "path": args.out})
        elif args.cmd == "doctor":
            import importlib.util
            from .core import morph
            _out({"ok": True, "python": sys.version.split()[0], "morphology": morph.available(),
                  **{m: importlib.util.find_spec(m) is not None for m in ("docx", "webview")}})
    except Exception as e:  # noqa: BLE001
        _out({"ok": False, "error": f"{type(e).__name__}: {e}", "trace": traceback.format_exc()[-2000:]})
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
