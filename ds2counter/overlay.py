"""Przezroczysta nakładka „DEATHS: N”, która nie przechwytuje kliknięć."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from . import winapi
from .config import OverlaySettings

TEXT_COLOR = QColor(242, 230, 201)
OUTLINE_COLOR = QColor(0, 0, 0, 230)
TOPMOST_REFRESH_MS = 1500


class OverlayWindow(QWidget):
    def __init__(self, settings: OverlaySettings) -> None:
        super().__init__(
            None,
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowTransparentForInput
            | Qt.WindowType.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setWindowTitle("DS2 Death Counter – nakładka")
        self._deaths = 0
        self._settings = settings
        self._font = QFont("Segoe UI")
        self._font.setBold(True)
        # Gra może sama ustawiać się „na wierzchu”, więc co jakiś czas przypominamy o nakładce.
        self._topmost_timer = QTimer(self)
        self._topmost_timer.setInterval(TOPMOST_REFRESH_MS)
        self._topmost_timer.timeout.connect(self._raise_topmost)
        self.apply_settings(settings)

    @property
    def text(self) -> str:
        return f"DEATHS: {self._deaths}"

    def set_deaths(self, deaths: int) -> None:
        if deaths != self._deaths:
            self._deaths = deaths
            self._update_geometry()
            self.update()

    def apply_settings(self, settings: OverlaySettings) -> None:
        self._settings = settings
        self._font.setPixelSize(settings.font_size)
        self._update_geometry()
        if self.isVisible():
            self._apply_capture_affinity()
        self.update()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        hwnd = int(self.winId())
        winapi.make_click_through(hwnd)
        winapi.set_topmost(hwnd)
        self._apply_capture_affinity()
        self._topmost_timer.start()

    def hideEvent(self, event) -> None:
        self._topmost_timer.stop()
        super().hideEvent(event)

    def paintEvent(self, event) -> None:
        outline = self._outline_width()
        metrics = QFontMetrics(self._font)
        path = QPainterPath()
        path.addText(outline + 2, outline + 2 + metrics.ascent(), self._font, self.text)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(OUTLINE_COLOR, outline * 2)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.strokePath(path, pen)
        painter.fillPath(path, TEXT_COLOR)
        painter.end()

    def _outline_width(self) -> int:
        return max(2, self._settings.font_size // 12)

    def _update_geometry(self) -> None:
        metrics = QFontMetrics(self._font)
        pad = self._outline_width() + 2
        self.setFixedSize(metrics.horizontalAdvance(self.text) + 2 * pad, metrics.height() + 2 * pad)
        self.move(QPoint(self._settings.x, self._settings.y))

    def _raise_topmost(self) -> None:
        winapi.set_topmost(int(self.winId()))

    def _apply_capture_affinity(self) -> None:
        winapi.exclude_from_capture(int(self.winId()), self._settings.hide_from_capture)
