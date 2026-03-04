# core/app_context.py
import logging
from copy import deepcopy
from enum import Enum
from typing import Optional
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from utils.settings_manager import SettingsManager
from config import default_values
from config.config import reconfigure_logging
from config.constants import SettingsKey
from core.translation_manager import TranslationManager
from core.hardware_manager import HardwareManager
from core.monitor_manager import MonitorManager
from core.data_handler import DataHandler
from monitoring.history_manager import HistoryManager # NEU


class StartupAction(Enum):
    DATABASE_RECOVERY = "database_recovery"

class AppContext(QObject):
    """
    Ein zentraler Kontext, der als Service-Container für die Hauptkomponenten
    der Anwendung dient. Er initialisiert und verwaltet die Lebenszyklen
    der Manager, um eine lose Kopplung zu gewährleisten.
    """
    language_changed = Signal(str)

    def __init__(self, config_dir: Path, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.config_dir = config_dir
        self._latest_monitor_data: dict = {}
        
        # 1. SettingsManager als Erstes initialisieren
        settings_file = self.config_dir / 'settings.json'
        self.settings_manager = SettingsManager(settings_file, default_values.DEFAULT_SETTINGS_BASE)
        logging.info(f"SettingsManager für '{settings_file}' initialisiert.")

        # 2. Logging mit den geladenen Einstellungen rekonfigurieren
        reconfigure_logging(self.settings_manager.get_all_settings())

        # 3. Weitere kernale Manager initialisieren
        self.translator = TranslationManager()
        self.hardware_manager = HardwareManager()
        self._initialize_selected_hardware()
        self.monitor_manager = MonitorManager()
        
        # NEU: HistoryManager initialisieren
        # Wir übergeben den Kontext (self), damit der Manager später auf main_win zugreifen kann
        self.history_manager = HistoryManager(self.settings_manager, self.config_dir, self)

        # 4. Sprache basierend auf den geladenen Einstellungen setzen
        current_lang = self.settings_manager.get_setting(SettingsKey.LANGUAGE.value, "german")
        self.translator.set_language(current_lang)
        
        # 5. Datenverarbeitungs-Manager initialisieren
        self.data_handler = DataHandler(self)
        
        self._connect_signals()
        logging.info("AppContext vollständig initialisiert.")

    def _connect_signals(self):
        """Verbindet Signale zwischen den Managern, um die Entkopplung zu fördern."""
        self.settings_manager.setting_changed.connect(self._on_setting_changed)
        self.settings_manager.setting_changed.connect(self.data_handler.on_setting_changed)
        logging.debug("Signale im AppContext verbunden.")
        
    def _initialize_selected_hardware(self):
        """Aktiviert die in den Einstellungen gespeicherten CPU- und GPU-Sensoren beim Start."""
        selected_cpu = self.settings_manager.get_setting(SettingsKey.SELECTED_CPU_IDENTIFIER.value, "auto")
        selected_gpu = self.settings_manager.get_setting(SettingsKey.SELECTED_GPU_IDENTIFIER.value, "auto")
        resolved_selection = self.hardware_manager.apply_hardware_selection(selected_cpu, selected_gpu)

        if resolved_selection.cpu_identifier != selected_cpu:
            self.settings_manager.set_setting(
                SettingsKey.SELECTED_CPU_IDENTIFIER.value,
                resolved_selection.cpu_identifier,
            )
        if resolved_selection.gpu_identifier != selected_gpu:
            self.settings_manager.set_setting(
                SettingsKey.SELECTED_GPU_IDENTIFIER.value,
                resolved_selection.gpu_identifier,
            )

    def _on_setting_changed(self, key: str, value):
        """Reagiert auf spezifische Einstellungsänderungen."""
        if key == SettingsKey.LANGUAGE.value:
            self.translator.set_language(value)
            self.language_changed.emit(value)
            logging.info(f"Sprache über Signal auf '{value}' geändert.")
        elif key in [
            SettingsKey.LOG_MAX_SIZE_MB.value,
            SettingsKey.LOG_BACKUP_COUNT.value,
            SettingsKey.LOG_LEVEL.value,
        ]:
            reconfigure_logging(self.settings_manager.get_all_settings())

    def get_settings(self) -> dict:
        """Gibt eine Kopie der aktuellen Einstellungen zurück."""
        return self.settings_manager.get_all_settings()

    def set_latest_monitor_data(self, data: dict):
        """Speichert den zuletzt empfangenen Snapshot aus dem Monitoring-Worker."""
        self._latest_monitor_data = data or {}

    def get_latest_monitor_data(self) -> dict:
        """Gibt einen Snapshot der zuletzt empfangenen Monitoring-Daten zurÃ¼ck."""
        return deepcopy(self._latest_monitor_data)

    def get_pending_startup_actions(self) -> list[StartupAction]:
        """Ermittelt UI-relevante Startup-Aktionen aus dem aktuellen Manager-Zustand."""
        actions: list[StartupAction] = []
        if self.history_manager.has_pending_database_recovery():
            actions.append(StartupAction.DATABASE_RECOVERY)
        return actions
