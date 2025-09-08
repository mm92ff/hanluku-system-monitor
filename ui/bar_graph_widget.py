# ui/bar_graph_widget.py
from __future__ import annotations
from typing import Optional

from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtGui import QColor, QPainter, QBrush, QFontMetrics, QFont
from PySide6.QtCore import Qt, QSize


class BarGraphWidget(QWidget):
    """
    Ein einfaches Widget zur Anzeige eines horizontalen Balkendiagramms.
    """
    MIN_BAR_HEIGHT = 6
    MIN_FONT_SIZE = 6

    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 0
        self._bar_color = QColor("#FFFFFF")
        self._background_color = QColor(60, 60, 60)

        self.setMinimumSize(50, self.MIN_BAR_HEIGHT)
        self._font_height = 10  # Standardwert
        self._updating_size = False
        # GELÖSCHT: Der problematische Aufruf _update_height_from_font() wurde hier entfernt.
        # Die Höhenberechnung erfolgt nun ausschliesslich über updateFontHeight().

    def setValue(self, value: Optional[float]):
        """Setzt den aktuellen Wert (0-100) des Balkens."""
        self._value = max(0, min(100, value or 0))
        self.update()

    def setColor(self, color_hex: str):
        """Setzt die Farbe des Balkens über einen Hex-String."""
        try:
            color = QColor(color_hex)
            self._bar_color = color if color.isValid() else QColor("#FFFFFF")
        except Exception:
            self._bar_color = QColor("#FFFFFF")
        self.update()

    def updateFontHeight(self, font: QFont, height_factor: float):
        """Aktualisiert die Balkenhöhe basierend auf einem neuen Font und dem Höhenfaktor."""
        if self._updating_size or not font:
            return
            
        self._updating_size = True
        try:
            if font.pointSize() < self.MIN_FONT_SIZE:
                font.setPointSize(self.MIN_FONT_SIZE)

            font_metrics = QFontMetrics(font)
            self._font_height = font_metrics.height()
            
            # Balkenhöhe wird mit dem Faktor berechnet
            bar_height = max(self.MIN_BAR_HEIGHT, int(self._font_height * height_factor))
            self.setFixedHeight(bar_height)
        finally:
            self._updating_size = False

    def paintEvent(self, event):
        """Zeichnet das Balkendiagramm."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Hintergrund
        painter.setBrush(QBrush(self._background_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRect(self.rect())

        # Vordergrund-Balken
        if self._value > 0:
            bar_width = (self._value / 100.0) * self.width()
            painter.setBrush(QBrush(self._bar_color))
            painter.drawRect(0, 0, int(bar_width), self.height())

    def sizeHint(self) -> QSize:
        """Gibt die bevorzugte Größe zurück."""
        return QSize(100, self.height())