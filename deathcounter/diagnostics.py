"""Plik diagnostyczny (diagnostyka.log obok programu): przebieg wykrywania do analizy zgłoszonych błędów.

Zapisuje zdarzenia (start/stop, śmierci, uzbrojenie detektora, pasek bossa, zwycięstwo, błędy) i co kilka
sekund wyniki dopasowania. Plik ma ograniczony rozmiar – starsza część trafia do diagnostyka.log.1.
Nie zawiera obrazów ani danych osobowych.
"""

from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

MAX_BYTES = 2 * 1024 * 1024
SAMPLE_EVERY_SECONDS = 5.0


class DiagnosticLog:
    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._last_sample = 0.0
        self._last_armed: bool | None = None
        self._last_status: str | None = None

    def write(self, message: str) -> None:
        try:
            if self.path.exists() and self.path.stat().st_size > MAX_BYTES:
                self.path.replace(self.path.with_name(self.path.name + ".1"))
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(f"{datetime.now():%Y-%m-%d %H:%M:%S.%f}"[:-3] + f"  {message}\n")
        except OSError:
            pass  # diagnostyka nigdy nie może przeszkodzić w działaniu programu

    def status(self, text: str) -> None:
        if text != self._last_status:
            self._last_status = text
            self.write(f"STAN: {text}")

    def sample(self, result, threshold: float, boss_state: str) -> None:
        """Przejścia detektora zapisuje od razu, a pozostałe wyniki co kilka sekund."""
        armed = result.armed
        if armed != self._last_armed and result.score is not None:
            self._last_armed = armed
            self.write(("DETEKTOR GOTOWY" if armed else "DETEKTOR CZEKA NA ZNIKNIĘCIE NAPISU")
                       + f" (dopasowanie śmierci {result.score:.2f})")
        now = time.monotonic()
        if now - self._last_sample < SAMPLE_EVERY_SECONDS:
            return
        self._last_sample = now
        check = result.check
        image = f"{check.resolution[0]}x{check.resolution[1]} {check.health.value}" if check.resolution else "brak"
        parts = [f"obraz={image}"]
        if result.score is not None:
            parts.append(f"śmierć={result.score:.2f}/{threshold:.2f} {'gotowy' if armed else 'czeka'}")
        if result.bar_score is not None:
            parts.append(f"pasek={result.bar_score:.2f} {'widoczny' if result.bar_visible else 'niewidoczny'}")
        if result.victory_score is not None:
            parts.append(f"zwycięstwo={result.victory_score:.2f}")
        parts.append(f"boss={boss_state}")
        self.write("PRÓBKA " + ", ".join(parts))

    def reset_detector_state(self) -> None:
        self._last_armed = None
