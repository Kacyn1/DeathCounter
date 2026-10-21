"""Okno „Statystyki sesji”: przebieg aktualnej sesji (śmierci w czasie gry) i porównanie wszystkich sesji gry."""

from __future__ import annotations

import math
from dataclasses import dataclass

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from . import i18n
from .attempts import format_when
from .bosses import format_duration
from .i18n import N_, tr
from .play_session import PlaySession

SERIES = QColor("#b8860b")        # kolor danych (sprawdzony: jasność, nasycenie i kontrast na ciemnym tle)
SERIES_HOVER = QColor("#d4a24c")  # słupek pod kursorem
SURFACE = QColor(32, 33, 37)      # tło okna (paleta programu)
GRID = QColor(58, 60, 66)         # siatka i osie – ledwo odcięte od tła
TEXT = QColor(225, 225, 225)
MUTED = QColor("#9aa0a6")
MAX_BARS = 20                     # tyle ostatnich sesji na wykresie słupkowym (wszystkie są w tabeli)
TABLE_COLUMNS = (N_("Sesja"), N_("Początek"), N_("Czas sesji"), N_("Czas gry"), N_("Śmierci"), N_("Śmierci/h"))


@dataclass(frozen=True)
class SessionRow:
    number: int
    started: float
    seconds: float       # czas sesji
    game_seconds: float  # czas gry (bez menu)
    deaths: int
    current: bool


def sessions(session: PlaySession, now: float) -> list[SessionRow]:
    """Wszystkie sesje gry od najstarszej: historia i na końcu bieżąca (albo ostatnia, jeszcze nie w historii)."""
    rows = [SessionRow(i + 1, r.started, r.seconds, r.game_seconds, r.deaths, False)
            for i, r in enumerate(session.history)]
    if session.started is not None:
        view = session.view(now)
        rows.append(SessionRow(len(rows) + 1, session.started, view.seconds, view.game_seconds, view.deaths, True))
    return rows


def per_hour(deaths: int, seconds: float) -> str:
    """Śmierci na godzinę czasu gry („7,2”); przy czasie krótszym niż minuta – „–” (za mało danych)."""
    return decimal(deaths / (seconds / 3600)) if seconds >= 60 else "–"


def decimal(value: float) -> str:
    text = f"{value:.1f}"
    return text.replace(".", ",") if i18n.language() == "pl" else text


def longest_without_death(times: list[float], seconds: float, early: int = 0) -> float:
    """Najdłuższy odcinek sesji bez śmierci (od początku, między śmierciami i od ostatniej do teraz).
    `early` – śmierci bez zapisanego czasu: nie wiadomo, kiedy były, więc liczymy od pierwszej śmierci z czasem."""
    points = [*([] if early and times else [0.0]), *times, seconds]
    return max(b - a for a, b in zip(points, points[1:]))


def nice_ticks(maximum: float, count: int = 4) -> list[float]:
    """Okrągłe podziałki osi od 0, np. 0, 5, 10, 15 – co najwyżej `count` + 1 wartości."""
    if maximum <= 0:
        return [0.0, 1.0]
    raw = maximum / count
    power = 10 ** math.floor(math.log10(raw))
    step = next(m * power for m in (1, 2, 5, 10) if m * power >= raw)
    step = max(step, 1.0)
    return [i * step for i in range(int(math.ceil(maximum / step)) + 1)]


def time_ticks(seconds: float, count: int = 5) -> list[float]:
    """Podziałki osi czasu w pełnych minutach / godzinach (1, 2, 5, 10, 15, 30 min, 1, 2, 3, 6 h)."""
    steps = [60, 120, 300, 600, 900, 1800, 3600, 7200, 10800, 21600]
    step = next((s for s in steps if seconds / s <= count), steps[-1])
    return [i * step for i in range(int(seconds // step) + 1)]


def clock(seconds: float) -> str:
    """Podpis osi czasu: „0:45”, „1:30” (godziny:minuty)."""
    minutes = int(seconds // 60)
    return f"{minutes // 60}:{minutes % 60:02d}"


class Chart(QWidget):
    """Wspólne elementy wykresów: obszar rysowania, oś Y z siatką i dymek po najechaniu."""

    LEFT, RIGHT, TOP, BOTTOM = 40, 16, 16, 30

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setMinimumHeight(220)
        self._mouse: QPointF | None = None
        self.empty_text = ""

    def plot(self) -> QRectF:
        return QRectF(self.LEFT, self.TOP, self.width() - self.LEFT - self.RIGHT,
                      self.height() - self.TOP - self.BOTTOM)

    def mouseMoveEvent(self, event) -> None:
        self._mouse = event.position()
        self.update()

    def leaveEvent(self, event) -> None:
        self._mouse = None
        self.update()

    def _y_axis(self, painter: QPainter, area: QRectF, ticks: list[float]) -> None:
        painter.setFont(self._small_font())
        for value in ticks:
            y = self._y(area, value, ticks[-1])
            painter.setPen(QPen(GRID, 1))
            painter.drawLine(QPointF(area.left(), y), QPointF(area.right(), y))
            painter.setPen(MUTED)
            painter.drawText(QRectF(0, y - 8, self.LEFT - 8, 16), Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                             f"{value:g}")

    @staticmethod
    def _y(area: QRectF, value: float, top: float) -> float:
        return area.bottom() - (value / top) * area.height() if top else area.bottom()

    def _small_font(self) -> QFont:
        font = QFont(self.font())
        font.setPointSizeF(font.pointSizeF() * 0.9)
        return font

    def _empty(self, painter: QPainter) -> bool:
        if not self.empty_text:
            return False
        painter.setPen(MUTED)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, self.empty_text)
        return True

    def _tooltip(self, painter: QPainter, anchor: QPointF, lines: list[str]) -> None:
        """Dymek obok kursora; nie wychodzi poza wykres."""
        metrics = QFontMetrics(painter.font())
        width = max(metrics.horizontalAdvance(line) for line in lines) + 16
        height = metrics.height() * len(lines) + 10
        x = anchor.x() + 12 if anchor.x() + 12 + width <= self.width() else anchor.x() - 12 - width
        y = min(max(anchor.y() - height / 2, 0), self.height() - height)
        box = QRectF(x, y, width, height)
        painter.setPen(QPen(GRID, 1))
        painter.setBrush(QColor(24, 25, 28))
        painter.drawRoundedRect(box, 4, 4)
        painter.setPen(TEXT)
        for i, line in enumerate(lines):
            painter.drawText(QRectF(x + 8, y + 5 + i * metrics.height(), width - 16, metrics.height()),
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, line)


class DeathTimeline(Chart):
    """Aktualna sesja: łączna liczba śmierci w czasie gry – linia schodkowa (każda śmierć to skok o 1)."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._times: list[float] = []
        self._early = 0       # śmierci bez zapisanego czasu (sprzed zbierania czasów) – na starcie wykresu
        self._seconds = 0.0

    def set_data(self, times: list[float], early: int, seconds: float) -> None:
        self._times, self._early, self._seconds = list(times), early, seconds
        self.update()

    def _count_at(self, t: float) -> int:
        return self._early + sum(1 for time in self._times if time <= t)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._empty(painter):
            return
        area = self.plot()
        total = self._early + len(self._times)
        y_ticks = nice_ticks(max(total, 1))
        top = y_ticks[-1]
        span = max(self._seconds, 60.0)

        def x_of(t: float) -> float:
            return area.left() + t / span * area.width()

        self._y_axis(painter, area, y_ticks)
        painter.setPen(MUTED)
        for t in time_ticks(span):
            x = x_of(t)
            painter.drawText(QRectF(x - 30, area.bottom() + 6, 60, 18), Qt.AlignmentFlag.AlignHCenter, clock(t))

        # Linia schodkowa: poziomo do chwili śmierci, potem skok o 1.
        line = QPainterPath(QPointF(area.left(), self._y(area, self._early, top)))
        count = self._early
        for t in self._times:
            line.lineTo(x_of(t), self._y(area, count, top))
            count += 1
            line.lineTo(x_of(t), self._y(area, count, top))
        end = QPointF(x_of(self._seconds), self._y(area, count, top))
        line.lineTo(end)
        wash = QPainterPath(line)
        wash.lineTo(end.x(), area.bottom())
        wash.lineTo(area.left(), area.bottom())
        wash.closeSubpath()
        fill = QColor(SERIES)
        fill.setAlpha(26)  # ok. 10% – delikatne wypełnienie pod linią
        painter.fillPath(wash, fill)
        pen = QPen(SERIES, 2)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(line)
        # Koniec linii: kropka z obwódką w kolorze tła i wartość obok.
        painter.setPen(QPen(SURFACE, 2))
        painter.setBrush(SERIES)
        painter.drawEllipse(end, 5, 5)
        painter.setPen(TEXT)
        painter.drawText(QRectF(end.x() - 40, end.y() - 24, 80, 16), Qt.AlignmentFlag.AlignHCenter, str(count))

        if self._mouse is not None and area.contains(self._mouse):
            t = (self._mouse.x() - area.left()) / area.width() * span
            if t <= self._seconds:
                x = x_of(t)
                painter.setPen(QPen(MUTED, 1))
                painter.drawLine(QPointF(x, area.top()), QPointF(x, area.bottom()))
                value = self._count_at(t)
                painter.setPen(QPen(SURFACE, 2))
                painter.setBrush(SERIES)
                painter.drawEllipse(QPointF(x, self._y(area, value, top)), 4, 4)
                self._tooltip(painter, QPointF(x, self._y(area, value, top)),
                              [tr("Czas sesji: {time}", time=format_duration(t)), tr("Śmierci: {deaths}", deaths=value)])


class SessionBars(Chart):
    """Wszystkie sesje: liczba śmierci w każdej (ostatnie MAX_BARS sesji)."""

    BAR_WIDTH = 24  # najszerszy słupek; reszta miejsca to odstęp

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._rows: list[SessionRow] = []

    def set_data(self, rows: list[SessionRow]) -> None:
        self._rows = rows[-MAX_BARS:]
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._empty(painter):
            return
        area = self.plot()
        rows = self._rows
        y_ticks = nice_ticks(max([row.deaths for row in rows] + [1]))
        top = y_ticks[-1]
        self._y_axis(painter, area, y_ticks)
        slot = area.width() / len(rows)
        width = min(self.BAR_WIDTH, slot * 0.6)
        metrics = QFontMetrics(self._small_font())
        label_every = max(1, math.ceil((metrics.horizontalAdvance("88") + 8) / slot))
        peak = max(range(len(rows)), key=lambda i: rows[i].deaths)
        hovered = None
        if self._mouse is not None and area.left() <= self._mouse.x() <= area.right() and self._mouse.y() <= area.bottom() + 24:
            hovered = min(int((self._mouse.x() - area.left()) // slot), len(rows) - 1)  # cała kolumna jest celem

        for i, row in enumerate(rows):
            center = area.left() + slot * (i + 0.5)
            y = self._y(area, row.deaths, top)
            if row.deaths:
                bar = QRectF(center - width / 2, y, width, area.bottom() - y)
                painter.fillPath(_rounded_top(bar, min(4.0, bar.height())), SERIES_HOVER if i == hovered else SERIES)
            painter.setFont(self._small_font())
            painter.setPen(MUTED)
            if i % label_every == 0 or i == len(rows) - 1:
                painter.drawText(QRectF(center - slot / 2 - 10, area.bottom() + 6, slot + 20, 18),
                                 Qt.AlignmentFlag.AlignHCenter, str(row.number))
            if i in (peak, len(rows) - 1):  # wartość tylko przy najwyższym i ostatnim słupku
                painter.setPen(TEXT)
                painter.drawText(QRectF(center - 30, y - 20, 60, 16), Qt.AlignmentFlag.AlignHCenter, str(row.deaths))
        if hovered is not None:
            row = rows[hovered]
            title = tr("Sesja {number} (bieżąca)", number=row.number) if row.current else tr("Sesja {number}", number=row.number)
            self._tooltip(painter, QPointF(area.left() + slot * (hovered + 0.5), self._y(area, row.deaths, top)), [
                title, format_when(row.started), tr("Śmierci: {deaths}", deaths=row.deaths),
                tr("Czas sesji: {time}", time=format_duration(row.seconds)),
                tr("Czas gry: {time}", time=format_duration(row.game_seconds)),
                tr("Śmierci na godzinę: {value}", value=per_hour(row.deaths, row.game_seconds))])


def _rounded_top(rect: QRectF, radius: float) -> QPainterPath:
    """Słupek z zaokrąglonym czubkiem i prostą podstawą."""
    path = QPainterPath(QPointF(rect.left(), rect.bottom()))
    path.lineTo(rect.left(), rect.top() + radius)
    path.quadTo(rect.left(), rect.top(), rect.left() + radius, rect.top())
    path.lineTo(rect.right() - radius, rect.top())
    path.quadTo(rect.right(), rect.top(), rect.right(), rect.top() + radius)
    path.lineTo(rect.right(), rect.bottom())
    path.closeSubpath()
    return path


class StatTiles(QWidget):
    """Rząd kafelków: podpis i duża wartość."""

    def __init__(self, labels: list[str], parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.values: list[QLabel] = []
        for label in labels:
            tile = QFrame()
            tile.setStyleSheet("QFrame { background:#26272b; border-radius:6px; }")
            box = QVBoxLayout(tile)
            caption = QLabel(label)
            caption.setStyleSheet("color:#9aa0a6;")
            value = QLabel("–")
            font = value.font()
            font.setPointSizeF(font.pointSizeF() * 1.5)
            font.setBold(True)
            value.setFont(font)
            box.addWidget(caption)
            box.addWidget(value)
            layout.addWidget(tile, 1)
            self.values.append(value)

    def set_values(self, values: list[str]) -> None:
        for label, value in zip(self.values, values):
            label.setText(value)


class SessionStatsWindow(QDialog):
    """Nie blokuje programu – może być otwarte obok w trakcie gry i odświeża się co sekundę."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.resize(760, 580)
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        current = QWidget()
        box = QVBoxLayout(current)
        self.current_tiles = StatTiles([tr("Śmierci"), tr("Czas sesji"), tr("Czas gry"), tr("Śmierci na godzinę"),
                                        tr("Najdłużej bez śmierci"), tr("Od ostatniej śmierci")])
        self.current_title = QLabel()
        self.timeline = DeathTimeline()
        self.current_note = QLabel()
        self.current_note.setWordWrap(True)
        self.current_note.setStyleSheet("color:#9aa0a6;")
        box.addWidget(self.current_tiles)
        box.addWidget(self.current_title)
        box.addWidget(self.timeline, 1)
        box.addWidget(self.current_note)
        self.tabs.addTab(current, tr("Aktualna sesja"))

        everything = QWidget()
        box = QVBoxLayout(everything)
        self.all_tiles = StatTiles([tr("Sesje"), tr("Śmierci łącznie"), tr("Czas sesji łącznie"), tr("Czas gry łącznie"),
                                    tr("Średnio na sesję"), tr("Śmierci na godzinę")])
        self.all_title = QLabel(tr("Śmierci w kolejnych sesjach"))
        self.bars = SessionBars()
        self.table = QTableWidget(0, len(TABLE_COLUMNS))
        self.table.setHorizontalHeaderLabels([tr(c) for c in TABLE_COLUMNS])
        self.table.verticalHeader().hide()
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        header = self.table.horizontalHeader()
        for column in range(len(TABLE_COLUMNS)):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.Stretch)
        box.addWidget(self.all_tiles)
        box.addWidget(self.all_title)
        box.addWidget(self.bars, 1)
        box.addWidget(self.table, 1)
        self.tabs.addTab(everything, tr("Wszystkie sesje"))

    def update_data(self, session: PlaySession, game_name: str, now: float) -> None:
        self.setWindowTitle(tr("Statystyki sesji – {game}", game=game_name))
        self._update_current(session, now)
        self._update_all(sessions(session, now))

    def _update_current(self, session: PlaySession, now: float) -> None:
        if session.started is None:
            self.current_tiles.set_values(["–"] * 6)
            self.current_title.setText(tr("Przebieg sesji"))
            self.timeline.empty_text = tr("Brak sesji – uruchom grę, a sesja zacznie się sama.")
            self.timeline.update()
            self.current_note.setText("")
            return
        view = session.view(now)
        times = session.death_times
        since_last = format_duration(view.seconds - times[-1]) if times else "–"
        self.current_tiles.set_values([
            str(view.deaths), format_duration(view.seconds), format_duration(view.game_seconds),
            per_hour(view.deaths, view.game_seconds),
            format_duration(longest_without_death(times, view.seconds, view.deaths - len(times)))
            if times or not view.deaths else "–",
            since_last])
        ended = not (view.running or view.continues)
        self.current_title.setText(
            tr("Przebieg sesji z {when} (zakończona)", when=format_when(session.started)) if ended
            else tr("Przebieg sesji z {when}", when=format_when(session.started)))
        self.timeline.empty_text = ""
        early = view.deaths - len(times)
        self.timeline.set_data(times, early, view.seconds)
        self.current_note.setText(
            tr("{count} śmierci z tej sesji nie ma zapisanego czasu (sprzed zbierania czasów śmierci) – "
               "są na początku wykresu.", count=early) if early else "")

    def _update_all(self, rows: list[SessionRow]) -> None:
        total_deaths = sum(row.deaths for row in rows)
        total_seconds = sum(row.seconds for row in rows)
        total_game = sum(row.game_seconds for row in rows)
        self.all_tiles.set_values([
            str(len(rows)), str(total_deaths), format_duration(total_seconds), format_duration(total_game),
            decimal(total_deaths / len(rows)) if rows else "–", per_hour(total_deaths, total_game)])
        self.bars.empty_text = "" if rows else tr("Brak sesji – historia zbiera się od wersji 1.12.0.")
        self.bars.set_data(rows)
        if len(rows) > MAX_BARS:
            self.all_title.setText(tr("Śmierci w ostatnich {count} sesjach (wszystkie są w tabeli)", count=MAX_BARS))
        else:
            self.all_title.setText(tr("Śmierci w kolejnych sesjach"))
        self.table.setRowCount(len(rows))
        for i, row in enumerate(reversed(rows)):  # najnowsza na górze
            number = tr("{number} (bieżąca)", number=row.number) if row.current else str(row.number)
            cells = (number, format_when(row.started), format_duration(row.seconds), format_duration(row.game_seconds),
                     str(row.deaths), per_hour(row.deaths, row.game_seconds))
            for column, text in enumerate(cells):
                item = QTableWidgetItem(text)
                if column >= 2:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.table.setItem(i, column, item)

