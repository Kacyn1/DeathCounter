"""Sekcja okna, którą zwija i rozwija kliknięcie w jej tytuł."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QGroupBox, QStyle, QStyleOptionGroupBox, QVBoxLayout, QWidget


class CollapsibleBox(QGroupBox):
    """QGroupBox z zawartością w `content`; tytuł ze strzałką ▾ (rozwinięta) / ▸ (zwinięta)."""

    collapsed_changed = Signal(bool)

    def __init__(self, title: str, collapsed: bool = False, parent=None) -> None:
        super().__init__(parent)
        self._title = title
        self.content = QWidget()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.content)
        self.setMouseTracking(True)
        self.collapsed = not collapsed  # wymusza ustawienie tytułu i widoczności poniżej
        self.set_collapsed(collapsed)

    def set_collapsed(self, collapsed: bool) -> None:
        if collapsed == self.collapsed:
            return
        self.collapsed = collapsed
        self.content.setVisible(not collapsed)
        self.setTitle(f"{'▸' if collapsed else '▾'} {self._title}")
        self.collapsed_changed.emit(collapsed)

    def _on_title(self, pos) -> bool:
        option = QStyleOptionGroupBox()
        self.initStyleOption(option)
        label = self.style().subControlRect(QStyle.ComplexControl.CC_GroupBox, option,
                                            QStyle.SubControl.SC_GroupBoxLabel, self)
        # Cały pasek tytułu, nie tylko sam napis – łatwiej trafić.
        return pos.y() <= label.bottom() + 4

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._on_title(event.position().toPoint()):
            self.set_collapsed(not self.collapsed)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def mouseMoveEvent(self, event) -> None:
        on_title = self._on_title(event.position().toPoint())
        self.setCursor(Qt.CursorShape.PointingHandCursor if on_title else Qt.CursorShape.ArrowCursor)
        super().mouseMoveEvent(event)
