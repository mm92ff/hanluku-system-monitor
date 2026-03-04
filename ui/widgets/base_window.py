# ui/widgets/base_window.py
import logging
from PySide6.QtWidgets import QDialog, QLabel, QListWidget, QPushButton, QLayout, QWidget
from PySide6.QtCore import Qt


DIALOG_CONTENT_MARGINS = (16, 16, 16, 16)
DIALOG_LAYOUT_SPACING = 12


def configure_dialog_layout(
    layout: QLayout,
    margins: tuple[int, int, int, int] = DIALOG_CONTENT_MARGINS,
    spacing: int = DIALOG_LAYOUT_SPACING,
):
    """Wendet gemeinsame Abstände auf Dialog-Layouts an."""
    layout.setContentsMargins(*margins)
    layout.setSpacing(spacing)


def configure_dialog_window(
    window: QWidget,
    width: int,
    height: int,
    min_width: int | None = None,
    min_height: int | None = None,
):
    """Wendet ein konsistentes Mindest-/Startgrößenmuster auf Dialogfenster an."""
    window.setMinimumSize(min_width or width, min_height or height)
    window.resize(width, height)


def style_dialog_button(button: QPushButton, role: str = "secondary"):
    """Stylt Buttons für Dialoge konsistent."""
    style_map = {
        "primary": (
            "QPushButton { padding: 8px 14px; min-width: 110px; font-weight: bold; "
            "background-color: #4CAF50; color: white; }"
        ),
        "accent": (
            "QPushButton { padding: 8px 14px; min-width: 110px; font-weight: bold; "
            "background-color: #2D7FF9; color: white; }"
        ),
        "danger": (
            "QPushButton { padding: 8px 14px; min-width: 110px; font-weight: bold; "
            "background-color: #C54B5C; color: white; }"
        ),
        "secondary": "QPushButton { padding: 8px 14px; min-width: 110px; }",
        "compact": "QPushButton { padding: 6px 10px; min-width: 90px; }",
    }
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setStyleSheet(style_map.get(role, style_map["secondary"]))


def style_info_label(label: QLabel, tone: str = "muted"):
    """Stylt Hinweis-Labels konsistent."""
    style_map = {
        "muted": "color: #888; font-size: 11px;",
        "subtle": "color: #aaa;",
        "success": "color: #4CAF50; font-size: 10px;",
        "error": "color: #C54B5C; font-size: 11px;",
    }
    label.setWordWrap(True)
    label.setStyleSheet(style_map.get(tone, style_map["muted"]))


def style_status_label(label: QLabel, tone: str = "muted"):
    """Stylt Status-/Infofelder mit etwas Innenabstand konsistent."""
    style_map = {
        "muted": "color: #888; padding: 5px;",
        "subtle": "color: #666; padding: 5px;",
        "success": "color: #4CAF50; padding: 5px;",
        "warning": "color: #FF9800; padding: 5px;",
        "error": "color: #F44336; padding: 5px;",
    }
    label.setWordWrap(True)
    label.setStyleSheet(style_map.get(tone, style_map["muted"]))


def style_choice_button(button: QPushButton, selected: bool = False):
    """Stylt Auswahlbuttons mit konsistentem Normal-/Aktivzustand."""
    if selected:
        style = (
            "QPushButton { padding: 8px 14px; min-width: 95px; font-weight: bold; "
            "background-color: #4CAF50; color: white; }"
        )
    else:
        style = "QPushButton { padding: 8px 14px; min-width: 95px; font-weight: bold; }"
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    button.setStyleSheet(style)


def style_preview_label(label: QLabel):
    """Stylt Vorschauflächen konsistent."""
    label.setStyleSheet(
        "background-color: #2b2b2b; color: #ffffff; padding: 20px; border-radius: 5px;"
    )


def style_list_widget(list_widget: QListWidget, item_margin: int = 4):
    """Gibt List-Widgets konsistente Item-Abstände."""
    list_widget.setStyleSheet(f"QListWidget::item {{ margin: {item_margin}px; }}")


def style_color_preview_button(button: QPushButton, hex_color: str):
    """Stylt kleine Farb-Vorschau-Buttons konsistent."""
    button.setStyleSheet(f"background-color: {hex_color}; border: 1px solid #888;")


def style_section_separator_label(label: QLabel):
    """Stylt Abschnittstrenner in langen Formularen konsistent."""
    label.setStyleSheet("margin-top: 10px; padding-top: 5px; border-top: 1px solid #555; color: #aaa;")


class _ToolWindowMixin:
    """Gemeinsame Basis fÃ¼r Tool-Fenster und Tool-Dialoge."""

    def _apply_tool_window_flags(self):
        self.setWindowFlags(
            self.windowFlags()
            | Qt.WindowType.Window
            | Qt.WindowType.WindowStaysOnTopHint
        )


class SafeWindow(_ToolWindowMixin, QWidget):
    """
    Basis-Klasse für alle Einstellungs-Fenster.
    Implementiert ein sicheres Schliessverhalten, das die Hauptanwendung
    nicht versehentlich beendet.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # Stellt sicher, dass das Widget als eigenständiges Fenster behandelt wird
        # und über anderen Fenstern schwebt.
        self._apply_tool_window_flags()

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


class SafeDialog(_ToolWindowMixin, QDialog):
    """Gemeinsame Basis fÃ¼r Tool-Dialoge mit denselben Fensterflags."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._apply_tool_window_flags()
