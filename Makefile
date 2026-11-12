# Команды проекта. Список: make help
PY := .venv/bin/python

.PHONY: help install run test lint package icons fixtures clean

help:           ## показать команды
	@grep -E '^[a-z]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-9s %s\n", $$1, $$2}'

$(PY):
	python3 -m venv .venv

install: $(PY)  ## окружение разработки: пакет и инструменты
	$(PY) -m pip install -q -e ".[dev,build]"

run:            ## открыть приложение из исходников
	$(PY) -m gretl_analytics

test:           ## тесты
	$(PY) -m pytest -q

lint:           ## проверка кода
	$(PY) -m pyflakes src tests packaging scripts

package:        ## собрать приложение для этой системы (на Mac: .dmg в dist/)
	$(PY) packaging/build.py

icons:          ## перерисовать значки в packaging/icons
	$(PY) scripts/make_icons.py

fixtures:       ## пересоздать tests/fixtures/en (нужен установленный Gretl)
	scripts/make_fixtures.sh

clean:          ## удалить артефакты сборки
	rm -rf dist build .pytest_cache src/*.egg-info
	find . -name __pycache__ -prune -exec rm -rf {} +
