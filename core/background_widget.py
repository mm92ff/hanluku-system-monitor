# core/background_widget.py
import logging
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QColor, QPainter, QBrush, QPen
from PySide6.QtCore import Qt

class BackgroundWidget(QWidget):
    """Ein benutzerdefiniertes Widget für einen abgerundeten, halbtransparenten Hintergrund."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.background_color = QColor(40, 40, 40, 200)
        self.border_color = None
        self.border_width = 0

    def set_background_color(self, color_hex):
        """Setzt die Grundfarbe des Hintergrunds über einen Hex-String."""
        try:
            alpha = self.background_color.alpha()
            self.background_color = QColor(color_hex)
            self.background_color.setAlpha(alpha)
            self.update()
        except Exception as e:
            logging.error(f"Ungültiger Farbwert für Hintergrund: {color_hex} - {e}")

    def set_background_alpha(self, alpha):
        """Setzt die Transparenz (Alpha-Wert) des Hintergrunds."""
        self.background_color.setAlpha(alpha)
        self.update()

    # --- NEUE METHODEN FÜR GRUPPENRAHMEN ---
    def set_border(self, color: QColor, width: int):
        """Legt einen farbigen Rahmen für das Widget fest."""
        self.border_color = color
        self.border_width = width
        self.update()

    def remove_border(self):
        """Entfernt den Rahmen."""
        self.border_color = None
        self.border_width = 0
        self.update()
    # ----------------------------------------

    def paintEvent(self, event):
        """Zeichnet das Widget."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Zeichne den Hintergrund
        painter.setBrush(QBrush(self.background_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(self.rect(), 5.0, 5.0)

        # Zeichne den optionalen Rahmen (für Gruppen)
        if self.border_color and self.border_width > 0:
            pen = QPen(self.border_color)
            pen.setWidth(self.border_width)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush) # Wichtig: Nur den Rahmen zeichnen
            # Ein leicht kleineres Rechteck für den Rahmen, damit er "sauber" aussieht
            painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 5.0, 5.0)