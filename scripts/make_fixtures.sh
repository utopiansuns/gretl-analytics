#!/bin/bash
# Пересоздаёт tests/fixtures/en: вывод gretlcli на учебных наборах, входящих в поставку Gretl.
# Нужен установленный Gretl (по умолчанию /Applications/Gretl.app; путь можно задать в GRETLCLI).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
GRETLCLI="${GRETLCLI:-/Applications/Gretl.app/Contents/Resources/bin/gretlcli.sh}"
for inp in "$ROOT"/tests/fixtures/gretl_scripts/*.inp; do
  name="$(basename "$inp" .inp)"
  # LC_ALL=C: десятичная точка; эхо команд, пути и служебный заголовок убираются
  LC_ALL=C LANG=C "$GRETLCLI" -b "$inp" 2>&1 \
    | sed -e '1,/^Current session/d' -e '/^? /d' -e '/\.inp$/d' -e '/^Read datafile/,/^$/d' \
          -e '/^Listing [0-9]* variables/,/^$/d' -e '/^periodicity:/d' -e '/^observations range:/d' -e '/^Done$/d' \
    > "$ROOT/tests/fixtures/en/$name.txt"
  echo "tests/fixtures/en/$name.txt"
done
