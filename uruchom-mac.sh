#!/bin/sh
# Tryb deweloperski na macOS: interfejs programu bez czesci z Windows (przechwytywanie obrazu, OCR,
# nakladka nad gra, globalne skroty, RTSS). Pierwsze uruchomienie tworzy .venv-mac przez uv
# (https://docs.astral.sh/uv/). Uzycie: ./uruchom-mac.sh  albo  ./uruchom-mac.sh test
set -e
cd "$(dirname "$0")"

if [ ! -x .venv-mac/bin/python ]; then
    uv venv .venv-mac --python 3.12
    uv pip install --python .venv-mac PySide6-Essentials opencv-python numpy pytest
fi

if [ "$1" = "test" ]; then
    exec .venv-mac/bin/python -m pytest -q
fi
exec .venv-mac/bin/python -m deathcounter
