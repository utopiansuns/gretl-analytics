"""Данные пользователя: словарь переменных, последний текст и временные файлы прогонов."""
import json
import os
import shutil
import sys
import tempfile
import time

FOLDER = "GretlAnalytics"
MAX_RUNS = 20
DEFAULTS = {"text": "", "glossary": [], "memory": {}, "title": "Эконометрический анализ", "brief": False, "theme": "auto",
            "sidebar": None}


def data_dir():
    """macOS: ~/Library/Application Support; Windows: %APPDATA%; Linux: ~/.local/share."""
    if os.environ.get("GRETL_ANALYTICS_HOME"):
        base = os.environ["GRETL_ANALYTICS_HOME"]
    elif sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    elif os.name == "nt":
        base = os.environ.get("APPDATA") or os.path.expanduser("~\\AppData\\Roaming")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.expanduser("~/.local/share")
    path = os.path.join(base, FOLDER)
    os.makedirs(path, exist_ok=True)
    return path


class Storage:
    def __init__(self, root=None):
        self.root = root or data_dir()
        self.state_file = os.path.join(self.root, "state.json")
        self.runs = os.path.join(self.root, "runs")
        os.makedirs(self.runs, exist_ok=True)

    def load(self):
        try:
            with open(self.state_file, encoding="utf-8") as f:
                return {**DEFAULTS, **json.load(f)}
        except (OSError, ValueError):
            return dict(DEFAULTS)

    def save(self, data):
        state = self.load()
        state.update({k: data[k] for k in DEFAULTS if k in data})
        tmp = self.state_file + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False)
        os.replace(tmp, self.state_file)
        return state

    def new_run(self):
        """Папка для очередного прогона; хранятся только последние MAX_RUNS."""
        for name in sorted(os.listdir(self.runs))[:-MAX_RUNS]:
            shutil.rmtree(os.path.join(self.runs, name), ignore_errors=True)
        return tempfile.mkdtemp(prefix=time.strftime("%Y%m%d-%H%M%S-"), dir=self.runs)
