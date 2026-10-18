"""Tworzy THIRD_PARTY_LICENSES.txt z licencji bibliotek dołączanych do DeathCounter.exe.

Uruchom po zmianie wersji bibliotek:  .venv\\Scripts\\python.exe tools\\make_third_party_licenses.py
Teksty LGPL v3 i GPL v3 (Qt nie dołącza ich do pakietu PySide6) leżą w folderze licenses/.
"""

from __future__ import annotations

import importlib.metadata as md
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "THIRD_PARTY_LICENSES.txt"

# (pakiet, nazwa, strona, licencja, pliki z dist-info albo z folderu licenses/)
LIBRARIES = [
    ("PySide6_Essentials", "Qt for Python (PySide6) i biblioteki Qt", "https://www.qt.io/qt-for-python",
     "LGPL-3.0-only", ["licenses/LGPL-3.0.txt", "licenses/GPL-3.0.txt"]),
    ("shiboken6", "Shiboken6 (część Qt for Python)", "https://www.qt.io/qt-for-python", "LGPL-3.0-only", []),
    ("opencv-python", "OpenCV", "https://opencv.org", "Apache-2.0", ["LICENSE.txt", "LICENSE-3RD-PARTY.txt"]),
    ("numpy", "NumPy", "https://numpy.org", "BSD-3-Clause i licencje dołączonych komponentów",
     ["licenses/LICENSE.txt"]),
    ("dxcam", "DXcam", "https://github.com/ra1nty/DXcam", "MIT", ["licenses/LICENSE"]),
    ("comtypes", "comtypes", "https://github.com/enthought/comtypes", "MIT", ["licenses/LICENSE.txt"]),
]


def dist_file(dist: md.Distribution, name: str) -> str:
    for f in dist.files or []:
        if ".dist-info" in str(f) and str(f).replace("\\", "/").endswith(name):
            return Path(dist.locate_file(f)).read_text(encoding="utf-8", errors="replace")
    raise FileNotFoundError(f"{dist.metadata['Name']}: brak pliku {name}")


def main() -> None:
    parts = [
        "LICENCJE BIBLIOTEK OSÓB TRZECICH – DEATH COUNTER BY MK",
        "=" * 60,
        "",
        "DeathCounter.exe zawiera poniższe biblioteki. Każda z nich jest udostępniana na własnej licencji,",
        "której warunki obowiązują niezależnie od licencji programu Death Counter by MK (GNU GPL v3, plik LICENSE).",
        "",
        "Qt for Python (PySide6) jest objęte licencją GNU LGPL v3. Kod źródłowy Qt jest dostępny na",
        "https://download.qt.io/official_releases/QtForPython/ oraz https://code.qt.io/. Kod źródłowy",
        "programu jest dostępny na https://github.com/Kacyn1/DeathCounter i można go zbudować",
        "z własną, zmodyfikowaną wersją bibliotek Qt.",
        "",
    ]
    sections = []
    for package, name, url, license_name, files in LIBRARIES:
        dist = md.distribution(package)
        title = f"{name} {dist.version}"
        parts.append(f"- {title} – {license_name} – {url}")
        texts = []
        for name in files:
            local = ROOT / name
            texts.append(local.read_text(encoding="utf-8") if name.startswith("licenses/") and local.exists()
                         else dist_file(dist, name))
        if texts:
            sections.append((f"{title} – {license_name}", texts))
    python = Path(sys.base_prefix) / "LICENSE.txt"
    parts.append(f"- Python {sys.version.split()[0]} – Python Software Foundation License – https://www.python.org")
    sections.append((f"Python {sys.version.split()[0]} – PSF License", [python.read_text(encoding="utf-8", errors="replace")]))
    parts.append("")
    for title, texts in sections:
        parts += ["", "#" * 78, f"# {title}", "#" * 78, ""]
        parts += [text.strip() + "\n" for text in texts]
    OUT.write_text("\n".join(parts), encoding="utf-8")
    print(f"Zapisano {OUT} ({OUT.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
