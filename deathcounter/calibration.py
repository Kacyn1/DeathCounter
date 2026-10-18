"""Okno kalibracji: pobranie obrazu z napisem „NIE ŻYJESZ”, zaznaczenie go i sprawdzenie wzorca."""

from __future__ import annotations

from typing import Callable

import numpy as np
from PySide6.QtCore import QPoint, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .template import DeathTemplate, TemplateError, read_image

FrameProvider = Callable[[Callable[[np.ndarray | None, str | None], None]], None]


def frame_to_qimage(frame: np.ndarray) -> QImage:
    frame = np.ascontiguousarray(frame)
    height, width = frame.shape[:2]
    if frame.ndim == 2:
        return QImage(frame.data, width, height, frame.strides[0], QImage.Format.Format_Grayscale8).copy()
    if frame.shape[2] == 4:
        frame = np.ascontiguousarray(frame[:, :, :3])
    return QImage(frame.data, width, height, frame.strides[0], QImage.Format.Format_BGR888).copy()


class SelectableImage(QWidget):
    """Podgląd obrazu z możliwością zaznaczenia prostokąta myszą (we współrzędnych obrazu)."""

    selection_changed = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMinimumSize(640, 360)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setCursor(Qt.CursorShape.CrossCursor)
        self._frame: np.ndarray | None = None
        self._image: QImage | None = None
        self._selection: QRect | None = None
        self._drag_start: QPoint | None = None

    @property
    def frame(self) -> np.ndarray | None:
        return self._frame

    def set_frame(self, frame: np.ndarray, selection: QRect | None = None) -> None:
        self._frame = frame
        self._image = frame_to_qimage(frame)
        self._selection = selection
        self.selection_changed.emit()
        self.update()

    def selection(self) -> tuple[int, int, int, int] | None:
        if self._selection is None or self._selection.width() < 2 or self._selection.height() < 2:
            return None
        r = self._selection
        return r.x(), r.y(), r.width(), r.height()

    def _target_rect(self) -> QRectF:
        if self._image is None:
            return QRectF()
        scale = min(self.width() / self._image.width(), self.height() / self._image.height())
        w, h = self._image.width() * scale, self._image.height() * scale
        return QRectF((self.width() - w) / 2, (self.height() - h) / 2, w, h)

    def _to_image(self, pos) -> QPoint:
        target = self._target_rect()
        x = (pos.x() - target.x()) / target.width() * self._image.width()
        y = (pos.y() - target.y()) / target.height() * self._image.height()
        x = int(max(0, min(self._image.width(), x)))
        y = int(max(0, min(self._image.height(), y)))
        return QPoint(x, y)

    def _to_widget(self, rect: QRect) -> QRectF:
        target = self._target_rect()
        sx = target.width() / self._image.width()
        sy = target.height() / self._image.height()
        return QRectF(target.x() + rect.x() * sx, target.y() + rect.y() * sy, rect.width() * sx, rect.height() * sy)

    def mousePressEvent(self, event) -> None:
        if self._image is not None and event.button() == Qt.MouseButton.LeftButton:
            self._drag_start = self._to_image(event.position())
            self._selection = QRect(self._drag_start, self._drag_start)
            self.update()

    def mouseMoveEvent(self, event) -> None:
        if self._drag_start is not None:
            self._selection = QRect(self._drag_start, self._to_image(event.position())).normalized()
            self.update()

    def mouseReleaseEvent(self, event) -> None:
        if self._drag_start is not None:
            self._drag_start = None
            self.selection_changed.emit()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(16, 16, 18))
        if self._image is None:
            painter.setPen(QColor(150, 150, 150))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Brak obrazu – przechwyć ekran lub wczytaj zrzut.")
            return
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawImage(self._target_rect(), self._image)
        if self._selection is not None:
            painter.setPen(QPen(QColor(230, 60, 60), 2))
            painter.drawRect(self._to_widget(self._selection))


class CalibrationDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None,
        frame_provider: FrameProvider,
        current_template: DeathTemplate | None,
        threshold: float,
        margin: float,
        hotkey_text: str | None,
        initial_frame: np.ndarray | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Kalibracja – wzorzec napisu „NIE ŻYJESZ”")
        self.resize(1000, 720)
        self._frame_provider = frame_provider
        self._current = current_template
        self._threshold = threshold
        self._margin = margin
        self.result_template: DeathTemplate | None = None

        hotkey = (
            f"naciśnij <b>{hotkey_text}</b> w grze, gdy widać ekran śmierci"
            if hotkey_text
            else "użyj przechwytywania z opóźnieniem"
        )
        intro = QLabel(
            "<ol style='margin:0'>"
            f"<li>Pobierz obraz z napisem „NIE ŻYJESZ”: {hotkey}, przechwyć ekran z opóźnieniem "
            "albo wczytaj zrzut ekranu z gry (np. F12 w Steam).</li>"
            "<li>Zaznacz myszą prostokąt obejmujący <b>sam napis</b>, z niewielkim marginesem.</li>"
            "<li>Kliknij „Sprawdź wzorzec”. Na ekranie śmierci wynik powinien przekroczyć próg, "
            "a na zwykłym zrzucie z gry być wyraźnie niższy.</li>"
            "</ol>"
        )
        intro.setWordWrap(True)
        intro.setTextFormat(Qt.TextFormat.RichText)

        self.image = SelectableImage()
        self.image.selection_changed.connect(self._on_selection_changed)

        self.delay = QSpinBox()
        self.delay.setRange(0, 30)
        self.delay.setValue(5)
        self.delay.setSuffix(" s")
        self.capture_button = QPushButton("Przechwyć ekran")
        self.capture_button.clicked.connect(self._start_capture)
        load_button = QPushButton("Wczytaj zrzut z pliku…")
        load_button.clicked.connect(self._load_file)
        source_row = QHBoxLayout()
        source_row.addWidget(QLabel("Opóźnienie:"))
        source_row.addWidget(self.delay)
        source_row.addWidget(self.capture_button)
        source_row.addWidget(load_button)
        source_row.addStretch(1)

        self.selection_label = QLabel()
        self.check_button = QPushButton("Sprawdź wzorzec")
        self.check_button.clicked.connect(self._check)
        self.check_label = QLabel()
        self.check_label.setWordWrap(True)
        check_row = QHBoxLayout()
        check_row.addWidget(self.check_button)
        check_row.addWidget(self.check_label, 1)

        self.save_button = QPushButton("Zapisz wzorzec")
        self.save_button.setDefault(True)
        self.save_button.clicked.connect(self._save)
        cancel_button = QPushButton("Zamknij")
        cancel_button.clicked.connect(self.reject)
        buttons = QHBoxLayout()
        buttons.addWidget(self.selection_label, 1)
        buttons.addWidget(self.save_button)
        buttons.addWidget(cancel_button)

        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addLayout(source_row)
        layout.addWidget(self.image, 1)
        layout.addLayout(check_row)
        layout.addLayout(buttons)

        self._countdown = QTimer(self)
        self._countdown.setInterval(1000)
        self._countdown.timeout.connect(self._tick)
        self._remaining = 0

        if initial_frame is not None:
            self.set_frame(initial_frame)
        self._on_selection_changed()

    # --- pozyskiwanie obrazu ---

    def set_frame(self, frame: np.ndarray) -> None:
        # Bez automatycznego zaznaczenia: „Sprawdź wzorzec” ma wtedy testować zapisany wzorzec na nowym obrazie.
        self.image.set_frame(frame)
        self.check_label.clear()

    def _start_capture(self) -> None:
        self._remaining = self.delay.value()
        self.capture_button.setEnabled(False)
        if self._remaining == 0:
            self._capture_now()
        else:
            self._update_countdown_text()
            self._countdown.start()

    def _tick(self) -> None:
        self._remaining -= 1
        if self._remaining <= 0:
            self._countdown.stop()
            self._capture_now()
        else:
            self._update_countdown_text()

    def _update_countdown_text(self) -> None:
        self.capture_button.setText(f"Przechwytywanie za {self._remaining} s…")

    def _capture_now(self) -> None:
        self.capture_button.setText("Przechwytywanie…")
        self._frame_provider(self._on_captured)

    def _on_captured(self, frame: np.ndarray | None, error: str | None) -> None:
        self.capture_button.setEnabled(True)
        self.capture_button.setText("Przechwyć ekran")
        if frame is None:
            QMessageBox.warning(self, "Kalibracja", error or "Nie udało się pobrać obrazu.")
            return
        self.set_frame(frame)
        self.raise_()
        self.activateWindow()

    def _load_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Wybierz zrzut ekranu", "", "Obrazy (*.png *.jpg *.jpeg *.bmp);;Wszystkie pliki (*)"
        )
        if not path:
            return
        try:
            self.set_frame(read_image(path))
        except TemplateError as exc:
            QMessageBox.warning(self, "Kalibracja", str(exc))

    # --- wzorzec ---

    def _on_selection_changed(self) -> None:
        selection = self.image.selection()
        if selection is None:
            self.selection_label.setText("Zaznaczenie: brak")
        else:
            x, y, w, h = selection
            self.selection_label.setText(f"Zaznaczenie: {w}×{h} px w punkcie ({x}, {y})")
        self.save_button.setEnabled(selection is not None)
        self.check_button.setEnabled(self.image.frame is not None and (selection is not None or self._current is not None))

    def _candidate(self) -> DeathTemplate:
        selection = self.image.selection()
        if selection is not None:
            return DeathTemplate.from_frame(self.image.frame, selection)
        if self._current is not None:
            return self._current
        raise TemplateError("Zaznacz napis „NIE ŻYJESZ” na obrazie.")

    def _check(self) -> None:
        try:
            candidate = self._candidate()
        except TemplateError as exc:
            self.check_label.setText(f"<span style='color:#e06c6c'>{exc}</span>")
            return
        score = candidate.match(self.image.frame, self._margin)
        found = score >= self._threshold
        verdict = (
            "<b style='color:#5fd38d'>napis WYKRYTY</b>"
            if found
            else "<b style='color:#e0a050'>napis NIEWYKRYTY</b>"
        )
        source = "zaznaczenia" if self.image.selection() is not None else "zapisanego wzorca"
        self.check_label.setText(
            f"Dopasowanie {source} do tego obrazu: <b>{score:.2f}</b> (próg {self._threshold:.2f}) → {verdict}"
        )

    def _save(self) -> None:
        selection = self.image.selection()
        if self.image.frame is None or selection is None:
            return
        try:
            template = DeathTemplate.from_frame(self.image.frame, selection)
        except TemplateError as exc:
            QMessageBox.warning(self, "Kalibracja", str(exc))
            return
        self.result_template = template
        self.accept()
