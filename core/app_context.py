# core/app_context.py
import logging
from typing import Optional
from pathlib import Path

from PySide6.QtCore import QObject

from utils.settings_manager import SettingsManager
from config import default_values
from config.config import reconfigure_logging
from core.translation_manager import TranslationManager
from core.hardware_manager import HardwareManager
from core.monitor_manager import MonitorManager
from core.data_handler import DataHandler
from monitoring.history_manager import HistoryManager # NEU

class AppContext(QObject):
    """
    Ein zentraler Kontext, der als Service-Container für die Hauptkomponenten
    der Anwendung dient. Er initialisiert und verwaltet die Lebenszyklen
    der Manager, um eine lose Kopplung zu gewährleisten.
    """
    def __init__(self, config_dir: Path, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.config_dir = config_dir
        
        # 1. SettingsManager als Erstes initialisieren
        settings_file = self.config_dir / 'settings.json'
        self.settings_manager = SettingsManager(settings_file, default_values.DEFAULT_SETTINGS_BASE)
        logging.info(f"SettingsManager für '{settings_file}' initialisiert.")

        # 2. Logging mit den geladenen Einstellungen rekonfigurieren
        reconfigure_logging(self.settings_manager.get_all_settings())

        # 3. Weitere kernale Manager initialisieren
        self.translator = TranslationManager()
        self.hardware_manager = HardwareManager()
        self.monitor_manager = MonitorManager()
        
        # NEU: HistoryManager initialisieren
        # Wir übergeben den Kontext (self), damit der Manager später auf main_win zugreifen kann
        self.history_manager = HistoryManager(self.settings_manager, self.config_dir, self)

        # 4. Sprache basierend auf den geladenen Einstellungen setzen
        current_lang = self.settings_manager.get_setting("language", "german")
        self.translator.set_language(current_lang)
        
        # 5. Datenverarbeitungs-Manager initialisieren
        self.data_handler = DataHandler(self)
        
        # Referenz auf main_win, wird nach dessen Erstellung gesetzt
        self.main_win = None

        self._connect_signals()
        logging.info("AppContext vollständig initialisiert.")

    def _connect_signals(self):
        """Verbindet Signale zwischen den Managern, um die Entkopplung zu fördern."""
        self.settings_manager.setting_changed.connect(self._on_setting_changed)
        self.settings_manager.setting_changed.connect(self.data_handler.on_setting_changed)
        logging.debug("Signale im AppContext verbunden.")
        
    def _on_setting_changed(self, key: str, value):
        """Reagiert auf spezifische Einstellungsänderungen."""
        if key == "language":
            self.translator.set_language(value)
            logging.info(f"Sprache über Signal auf '{value}' geändert.")
        elif key in ["log_max_size_mb", "log_backup_count", "log_level"]:
            reconfigure_logging(self.settings_manager.get_all_settings())

    def get_settings(self) -> dict:
        """Gibt eine Kopie der aktuellen Einstellungen zurück."""
        return self.settings_manager.get_all_settings()