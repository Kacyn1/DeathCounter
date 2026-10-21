"""Okno kalibracji: wzorce napisu śmierci oraz (w zakładce „Walka z bossem”) paska bossa i komunikatu zwycięstwa."""

from __future__ import annotations

from dataclasses import dataclass
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
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .template import DeathTemplate, TemplateError, read_image
from .i18n import tr, N_

FrameProvider = Callable[[Callable[[np.ndarray | None, str | None], None]], None]
# Zapisuje wzorzec danego rodzaju razem z pełnym zrzutem, z którego go wycięto; zwraca komunikat błędu albo None.
TemplateSaver = Callable[[str, DeathTemplate, np.ndarray], "str | None"]


@dataclass
class SavedCalibration:
    """Zapisany zrzut do pokazania w kalibracji; `full=False` – brak zrzutu, widać tylko sam wzorzec."""

    frame: np.ndarray
    full: bool


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
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, tr("Brak obrazu – przechwyć ekran lub wczytaj zrzut."))
            return
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawImage(self._target_rect(), self._image)
        if self._selection is not None:
            painter.setPen(QPen(QColor(230, 60, 60), 2))
            painter.drawRect(self._to_widget(self._selection))


@dataclass(frozen=True)
class TemplateKind:
    key: str
    subject: str       # co jest na obrazie, np. „napis śmierci”
    moment: str        # kiedy nacisnąć skrót / przechwycić ekran
    what_to_select: str
    check_hint: str


KINDS = {
    "death": TemplateKind(
        "death",
        N_("napis śmierci"),
        N_("gdy widać ekran śmierci (np. „NIE ŻYJESZ”)"),
        N_("Zaznacz myszą prostokąt obejmujący <b>sam napis</b>, z niewielkim marginesem."),
        N_("Na ekranie śmierci wynik powinien przekroczyć próg, a na zwykłym zrzucie z gry być wyraźnie niższy."),
    ),
    "boss_bar": TemplateKind(
        "boss_bar",
        N_("pasek zdrowia bossa"),
        N_("w trakcie walki, gdy widać pasek zdrowia bossa"),
        N_("Zaznacz <b>lewy koniec paska</b>: ozdobną ramkę i początek paska. Nie zaznaczaj nazwy bossa "
           "(każdy boss ma inną) ani całego paska – jego wypełnienie maleje, gdy boss traci zdrowie."),
        N_("Na obrazie z walki wynik powinien przekroczyć próg, a na zrzucie bez bossa być wyraźnie niższy."),
    ),
    "victory": TemplateKind(
        "victory",
        N_("komunikat zwycięstwa"),
        N_("gdy po pokonaniu bossa widać komunikat zwycięstwa"),
        N_("Zaznacz myszą prostokąt obejmujący <b>sam napis</b> komunikatu, z niewielkim marginesem."),
        N_("Na obrazie z komunikatem wynik powinien przekroczyć próg, a na zwykłym zrzucie z gry być wyraźnie niższy."),
    ),
    "menu": TemplateKind(
        "menu",
        N_("menu główne gry"),
        N_("gdy widać menu główne (ekran tytułowy z „Kontynuuj” / „Nowa gra”)"),
        N_("Zaznacz coś, co jest w menu głównym zawsze i tylko tam – np. <b>logo gry</b> albo napisy menu. "
           "Nie zaznaczaj animowanego tła."),
        N_("Na zrzucie menu wynik powinien przekroczyć próg, a na zrzucie z rozgrywki być wyraźnie niższy."),
    ),
    "hud": TemplateKind(
        "hud",
        N_("pasek zdrowia postaci"),
        N_("w trakcie rozgrywki, gdy widać pasek zdrowia postaci"),
        N_("Zaznacz <b>lewy koniec paska zdrowia</b> postaci: ramkę i początek paska, bez całego paska – "
           "jego wypełnienie zmienia się razem ze zdrowiem."),
        N_("Na zrzucie z rozgrywki wynik powinien przekroczyć próg, a na zrzucie menu i ekranu wczytywania być wyraźnie niższy."),
    ),
}


class CalibrationPage(QWidget):
    """Pobranie obrazu, zaznaczenie fragmentu, sprawdzenie i zapis wzorca jednego rodzaju."""

    def __init__(
        self,
        kind: TemplateKind,
        frame_provider: FrameProvider,
        saver: TemplateSaver,
        current_template: DeathTemplate | None,
        saved: SavedCalibration | None,
        threshold: float,
        margin: float,
        hotkey_text: str | None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.kind = kind
        self._frame_provider = frame_provider
        self._saver = saver
        self._current = current_template
        self._saved = saved if current_template is not None else None
        self._showing_saved = False
        self._threshold = threshold
        self._margin = margin

        hotkey = tr("naciśnij <b>{hotkey_text}</b> w grze {moment}", hotkey_text=hotkey_text, moment=tr(kind.moment)) if hotkey_text else tr("użyj przechwytywania z opóźnieniem")
        intro = QLabel(
            tr("<ol style='margin:0'><li>Pobierz obraz, na którym widać {subject}: {hotkey}, przechwyć ekran z opóźnieniem albo wczytaj zrzut ekranu z gry (np. F12 w Steam).</li><li>{what_to_select}</li><li>Kliknij „Sprawdź wzorzec”. {check_hint}</li><li>Kliknij „Zapisz wzorzec”.</li></ol>", subject=tr(kind.subject), hotkey=hotkey, what_to_select=tr(kind.what_to_select), check_hint=tr(kind.check_hint))
        )
        intro.setWordWrap(True)
        intro.setTextFormat(Qt.TextFormat.RichText)

        self.image = SelectableImage()
        self.image.selection_changed.connect(self._on_selection_changed)

        self.delay = QSpinBox()
        self.delay.setRange(0, 30)
        self.delay.setValue(5)
        self.delay.setSuffix(" s")
        self.capture_button = QPushButton(tr("Przechwyć ekran"))
        self.capture_button.clicked.connect(self._start_capture)
        load_button = QPushButton(tr("Wczytaj zrzut z pliku…"))
        load_button.clicked.connect(self._load_file)
        self._hotkey_frame: np.ndarray | None = None
        self.hotkey_button = QPushButton(tr("Zrzut ze skrótu"))
        self.hotkey_button.setToolTip(tr("Wstawia ostatni zrzut zrobiony skrótem {value}.", value=hotkey_text or tr('zrzutu')))
        self.hotkey_button.setEnabled(False)
        self.hotkey_button.clicked.connect(lambda: self.set_frame(self._hotkey_frame))
        self.saved_button = QPushButton(tr("Pokaż zapisany wzorzec"))
        self.saved_button.setToolTip(tr("Wraca do obrazu, z którego wycięto zapisany wzorzec, z zaznaczonym obszarem."))
        self.saved_button.clicked.connect(self.show_saved)
        source_row = QHBoxLayout()
        source_row.addWidget(QLabel(tr("Opóźnienie:")))
        source_row.addWidget(self.delay)
        source_row.addWidget(self.capture_button)
        source_row.addWidget(load_button)
        source_row.addWidget(self.hotkey_button)
        source_row.addStretch(1)
        source_row.addWidget(self.saved_button)

        self.saved_note = QLabel(
            tr("Ten wzorzec zapisano we wcześniejszej wersji programu, bez pełnego zrzutu – widać tylko zaznaczony "
            "fragment. Po ponownym zapisaniu wzorca kalibracja będzie pokazywać cały obraz.")
        )
        self.saved_note.setWordWrap(True)
        self.saved_note.setStyleSheet("color:#e0a050;")

        self.check_button = QPushButton(tr("Sprawdź wzorzec"))
        self.check_button.clicked.connect(self._check)
        self.check_label = QLabel()
        self.check_label.setWordWrap(True)
        check_row = QHBoxLayout()
        check_row.addWidget(self.check_button)
        check_row.addWidget(self.check_label, 1)

        self.selection_label = QLabel()
        self.state_label = QLabel()
        self.save_button = QPushButton(tr("Zapisz wzorzec"))
        self.save_button.clicked.connect(self._save)
        save_row = QHBoxLayout()
        save_row.addWidget(self.selection_label, 1)
        save_row.addWidget(self.state_label)
        save_row.addWidget(self.save_button)

        layout = QVBoxLayout(self)
        layout.addWidget(intro)
        layout.addLayout(source_row)
        layout.addWidget(self.saved_note)
        layout.addWidget(self.image, 1)
        layout.addLayout(check_row)
        layout.addLayout(save_row)

        self._countdown = QTimer(self)
        self._countdown.setInterval(1000)
        self._countdown.timeout.connect(self._tick)
        self._remaining = 0
        self._refresh_state()
        if self._saved is not None:
            self.show_saved()
        else:
            self._update_saved_view()
            self._on_selection_changed()

    # --- pozyskiwanie obrazu ---

    def show_saved(self) -> None:
        """Zapisany zrzut z obszarem, z którego wycięto bieżący wzorzec."""
        if self._saved is None or self._current is None:
            return
        self.image.set_frame(self._saved.frame, QRect(*self._current.roi))
        self.check_label.clear()
        self._showing_saved = True
        self._update_saved_view()
        self._on_selection_changed()

    def set_hotkey_frame(self, frame: np.ndarray) -> None:
        self._hotkey_frame = frame
        self.hotkey_button.setEnabled(True)

    def set_frame(self, frame: np.ndarray) -> None:
        # Bez automatycznego zaznaczenia: „Sprawdź wzorzec” ma wtedy testować zapisany wzorzec na nowym obrazie.
        self.image.set_frame(frame)
        self.check_label.clear()
        self._showing_saved = False
        self._update_saved_view()

    def _update_saved_view(self) -> None:
        self.saved_button.setEnabled(self._saved is not None and not self._showing_saved)
        self.saved_note.setVisible(self._showing_saved and self._saved is not None and not self._saved.full)

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
        self.capture_button.setText(tr("Przechwytywanie za {remaining} s…", remaining=self._remaining))

    def _capture_now(self) -> None:
        self.capture_button.setText(tr("Przechwytywanie…"))
        self._frame_provider(self._on_captured)

    def _on_captured(self, frame: np.ndarray | None, error: str | None) -> None:
        self.capture_button.setEnabled(True)
        self.capture_button.setText(tr("Przechwyć ekran"))
        if frame is None:
            QMessageBox.warning(self, tr("Kalibracja"), error or tr("Nie udało się pobrać obrazu."))
            return
        self.set_frame(frame)
        window = self.window()
        window.raise_()
        window.activateWindow()

    def _load_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, tr("Wybierz zrzut ekranu"), "", tr("Obrazy (*.png *.jpg *.jpeg *.bmp);;Wszystkie pliki (*)")
        )
        if not path:
            return
        try:
            self.set_frame(read_image(path))
        except TemplateError as exc:
            QMessageBox.warning(self, tr("Kalibracja"), str(exc))

    # --- wzorzec ---

    def _refresh_state(self) -> None:
        if self._current is None:
            self.state_label.setText(tr("<span style='color:#e0a050'>wzorzec: brak</span>"))
        else:
            w, h = self._current.reference_size
            self.state_label.setText(tr("<span style='color:#5fd38d'>wzorzec: zapisany (z obrazu {w}×{h})</span>", w=w, h=h))

    def _on_selection_changed(self) -> None:
        selection = self.image.selection()
        if selection is None:
            self.selection_label.setText(tr("Zaznaczenie: brak"))
        else:
            x, y, w, h = selection
            saved = tr(" – zapisany wzorzec") if self._showing_saved and selection == self._current.roi else ""
            self.selection_label.setText(tr("Zaznaczenie: {w}×{h} px w punkcie ({x}, {y}){saved}", w=w, h=h, x=x, y=y, saved=saved))
        self.save_button.setEnabled(selection is not None)
        self.check_button.setEnabled(self.image.frame is not None and (selection is not None or self._current is not None))

    def _candidate(self) -> DeathTemplate:
        selection = self.image.selection()
        if selection is not None:
            return DeathTemplate.from_frame(self.image.frame, selection)
        if self._current is not None:
            return self._current
        raise TemplateError(tr("Zaznacz {subject} na obrazie.", subject=tr(self.kind.subject)))

    def _check(self) -> None:
        try:
            candidate = self._candidate()
        except TemplateError as exc:
            self.check_label.setText(f"<span style='color:#e06c6c'>{exc}</span>")
            return
        score = candidate.match(self.image.frame, self._margin)
        found = score >= self._threshold
        verdict = (
            tr("<b style='color:#5fd38d'>WYKRYTO</b>")
            if found
            else tr("<b style='color:#e0a050'>NIE WYKRYTO</b>")
        )
        source = tr("zaznaczenia") if self.image.selection() is not None else tr("zapisanego wzorca")
        self.check_label.setText(
            tr("Dopasowanie {source} do tego obrazu: <b>{score:.2f}</b> (próg {threshold:.2f}) → {verdict}", source=source, score=score, threshold=self._threshold, verdict=verdict)
        )

    def _save(self) -> None:
        selection = self.image.selection()
        if self.image.frame is None or selection is None:
            return
        try:
            template = DeathTemplate.from_frame(self.image.frame, selection)
        except TemplateError as exc:
            QMessageBox.warning(self, tr("Kalibracja"), str(exc))
            return
        error = self._saver(self.kind.key, template, self.image.frame)
        if error:
            QMessageBox.critical(self, tr("Błąd zapisu wzorca"), error)
            return
        self._current = template
        self._saved = SavedCalibration(self.image.frame, full=True)
        self._showing_saved = True
        self._update_saved_view()
        self._on_selection_changed()
        self._refresh_state()
        self.check_label.setText(tr("<span style='color:#5fd38d'>Wzorzec zapisany i używany przez wykrywanie.</span>"))


class CalibrationDialog(QDialog):
    """Zakładki „Napis śmierci”, „Walka z bossem” (pasek bossa, komunikat zwycięstwa) i „Menu i rozgrywka”
    (menu główne, pasek zdrowia postaci).
    Każdy wzorzec zapisuje się od razu przyciskiem „Zapisz wzorzec”; okno zostaje otwarte."""

    def __init__(
        self,
        parent: QWidget | None,
        frame_provider: FrameProvider,
        saver: TemplateSaver,
        templates: dict[str, DeathTemplate | None],
        saved: dict[str, SavedCalibration | None],
        thresholds: dict[str, float],
        margin: float,
        hotkey_text: str | None,
        initial_frame: np.ndarray | None = None,
        initial_kind: str = "death",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Kalibracja wzorców"))
        self.resize(1000, 800)

        self.pages = {
            key: CalibrationPage(
                kind, frame_provider, saver, templates.get(key), saved.get(key), thresholds[key], margin, hotkey_text
            )
            for key, kind in KINDS.items()
        }
        self.tabs = QTabWidget()
        self.tabs.addTab(self.pages["death"], tr("Napis śmierci"))
        self.boss_tabs = QTabWidget()
        self.boss_tabs.addTab(self.pages["boss_bar"], tr("Pasek bossa"))
        self.boss_tabs.addTab(self.pages["victory"], tr("Komunikat zwycięstwa"))
        boss_page = QWidget()
        boss_layout = QVBoxLayout(boss_page)
        boss_hint = QLabel(
            tr("Pasek bossa rozpoczyna walkę i wznawia timer, a komunikat zwycięstwa kończy ją na stałe. "
            "Skalibruj oba, aby „Śledź walkę z bossem” działało samo.")
        )
        boss_hint.setWordWrap(True)
        boss_hint.setStyleSheet("color:#9aa0a6;")
        boss_layout.addWidget(boss_hint)
        boss_layout.addWidget(self.boss_tabs, 1)
        self.tabs.addTab(boss_page, tr("Walka z bossem"))
        self.play_tabs = QTabWidget()
        self.play_tabs.addTab(self.pages["menu"], tr("Menu główne"))
        self.play_tabs.addTab(self.pages["hud"], tr("Pasek zdrowia postaci"))
        play_page = QWidget()
        play_layout = QVBoxLayout(play_page)
        play_hint = QLabel(
            tr("Menu główne oddziela czas gry od czasu sesji: czas w menu się nie liczy. Pasek zdrowia postaci "
               "pokazuje, kiedy po wyjściu z menu zaczęła się rozgrywka – bez niego czas gry rusza zaraz po menu, "
               "razem z ekranem wczytywania.")
        )
        play_hint.setWordWrap(True)
        play_hint.setStyleSheet("color:#9aa0a6;")
        play_layout.addWidget(play_hint)
        play_layout.addWidget(self.play_tabs, 1)
        self.tabs.addTab(play_page, tr("Menu i rozgrywka"))
        self.show_kind(initial_kind)

        close_button = QPushButton(tr("Zamknij"))
        close_button.clicked.connect(self.accept)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(close_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs, 1)
        layout.addLayout(buttons)

        if initial_frame is not None:
            # Świeży zrzut ze skrótu trafia do otwieranej zakładki; pozostałe pokazują zapisane wzorce,
            # a zrzut można w nich wstawić przyciskiem „Zrzut ze skrótu”.
            for page in self.pages.values():
                page.set_hotkey_frame(initial_frame)
            self.pages[initial_kind].set_frame(initial_frame)

    def show_kind(self, key: str) -> None:
        if key == "death":
            self.tabs.setCurrentIndex(0)
        elif key in ("menu", "hud"):
            self.tabs.setCurrentIndex(2)
            self.play_tabs.setCurrentWidget(self.pages[key])
        else:
            self.tabs.setCurrentIndex(1)
            self.boss_tabs.setCurrentWidget(self.pages[key])

    def current_page(self) -> CalibrationPage:
        if self.tabs.currentIndex() == 0:
            return self.pages["death"]
        if self.tabs.currentIndex() == 2:
            return self.play_tabs.currentWidget()
        return self.boss_tabs.currentWidget()

    def set_frame(self, frame: np.ndarray) -> None:
        """Zrzut ze skrótu w trakcie kalibracji trafia do zakładki, która jest właśnie otwarta."""
        for page in self.pages.values():
            page.set_hotkey_frame(frame)
        self.current_page().set_frame(frame)
