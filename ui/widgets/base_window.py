# ui/widgets/base_window.py
import logging
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt

class SafeWindow(QWidget):
    """
    Basis-Klasse für alle Einstellungs-Fenster.
    Implementiert ein sicheres Schliessverhalten, das die Hauptanwendung
    nicht versehentlich beendet.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # Stellt sicher, dass das Widget als eigenständiges Fenster behandelt wird
        # und über anderen Fenstern schwebt.
        self.setWindowFlags(
            self.windowFlags() |
            Qt.WindowType.Window |
            Qt.WindowType.WindowStaysOnTopHint
        )

    def close_safely(self):
        """Schliesst das Fenster sicher, ohne das Hauptprogramm zu beenden."""
        try:
            self.hide()
            self.deleteLater()
            logging.debug(f"{self.__class__.__name__} sicher geschlossen")
        except Exception as e:
            logging.error(
                f"Fehler beim sicheren Schliessen von {self.__class__.__name__}: {e}"
            )

    def closeEvent(self, event):
        """Überschreibt das Standard-Close-Event für sicheres Schliessen."""
        event.accept()
        self.close_safely()