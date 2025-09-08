# main.py
import sys
import os
import ctypes
import logging
from pathlib import Path

from PySide6.QtWidgets import QApplication, QStyleFactory, QMessageBox
from PySide6.QtGui import QPalette, QColor, QFontDatabase
from PySide6.QtCore import Qt, QLocale

from config.config import get_config_dir
from config.constants import AppInfo
from core.app_context import AppContext
from core.main_window import SystemMonitor


def setup_failsafe_logging(config_dir: Path):
    """Richtet ein einfaches Standard-Logging ein, das immer funktioniert."""
    log_file = config_dir / 'monitor.log'
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

def is_admin() -> bool:
    """Prüft, ob die Anwendung mit Administratorrechten läuft (nur Windows)."""
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except (AttributeError, OSError):
        return False

def show_admin_warning():
    """Zeigt eine Warnung an, wenn keine Admin-Rechte vorhanden sind."""
    from core.translation_manager import TranslationManager
    pre_translator = TranslationManager()
    lang = QLocale.system().name().split('_')[0]
    pre_translator.set_language("english" if lang != "de" else "german")

    msg_box = QMessageBox()
    msg_box.setIcon(QMessageBox.Icon.Warning)
    msg_box.setWindowTitle(pre_translator.translate("admin_needed_title"))
    msg_box.setText(pre_translator.translate("admin_needed_text"))
    msg_box.setInformativeText(pre_translator.translate("admin_needed_info"))
    msg_box.setStandardButtons(QMessageBox.StandardButton.Ok)
    msg_box.exec()

def setup_dark_theme(app: QApplication):
    """Konfiguriert ein dunkles Theme für die Anwendung."""
    app.setStyle(QStyleFactory.create("Fusion"))
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(30, 30, 30))
    palette.setColor(QPalette.WindowText, Qt.white)
    palette.setColor(QPalette.Base, QColor(25, 25, 25))
    palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
    palette.setColor(QPalette.ToolTipBase, Qt.white)
    palette.setColor(QPalette.ToolTipText, Qt.black)
    palette.setColor(QPalette.Text, Qt.white)
    palette.setColor(QPalette.Button, QColor(53, 53, 53))
    palette.setColor(QPalette.ButtonText, Qt.white)
    palette.setColor(QPalette.BrightText, Qt.red)
    palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    palette.setColor(QPalette.HighlightedText, Qt.black)
    app.setPalette(palette)

def load_fonts():
    """Lädt die Anwendungs-Schriftarten aus dem assets-Ordner."""
    font_dir = Path(__file__).parent / "assets" / "fonts"
    fonts_to_load = ["FiraCode-Regular.ttf", "FiraCode-Bold.ttf"]
    loaded_count = 0
    
    for font_file in fonts_to_load:
        font_path = font_dir / font_file
        if not font_path.exists():
            logging.warning(f"Schriftart-Datei nicht gefunden: {font_path}")
            continue

        font_id = QFontDatabase.addApplicationFont(str(font_path))
        if font_id == -1:
            logging.warning(f"Schriftart konnte nicht geladen werden: {font_file}")
        else:
            loaded_count += 1
            
    if loaded_count > 0:
        # Logge die erste geladene Schriftart zur Bestätigung
        font_families = QFontDatabase.applicationFontFamilies(0)
        if font_families:
            logging.info(f"{loaded_count} Schriftarten erfolgreich geladen. Familie: '{font_families[0]}'")

def main():
    """Hauptfunktion der Anwendung."""
    try:
        config_dir = get_config_dir()
        setup_failsafe_logging(config_dir)

        # Workaround für Taskleisten-Icon unter Windows
        if sys.platform == "win32":
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(AppInfo.APP_USER_MODEL_ID)

        app = QApplication(sys.argv)
        
        load_fonts()

        if sys.platform == "win32" and not is_admin():
            show_admin_warning()

        setup_dark_theme(app)

        app_context = AppContext(config_dir)
        
        monitor = SystemMonitor(app_context)
        
        sys.exit(app.exec())

    except Exception:
        logging.critical(
            "Ein unerwarteter kritischer Fehler ist aufgetreten. Die Anwendung wird beendet.",
            exc_info=True
        )
        sys.exit(1)


if __name__ == '__main__':
    main()