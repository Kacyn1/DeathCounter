"""Punkt startowy bez okna konsoli (dwuklik uruchamia pythonw) i dla PyInstallera."""

import sys

from deathcounter.app import main

if __name__ == "__main__":
    sys.exit(main())
