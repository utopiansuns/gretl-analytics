"""Точка входа собранного приложения (PyInstaller): открывает окно «Аналитики Gretl»."""
import sys

from gretl_analytics.app import run

if __name__ == "__main__":
    sys.exit(run())
