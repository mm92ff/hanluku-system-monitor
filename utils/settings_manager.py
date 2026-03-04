# utils/settings_manager.py
import json
import logging
import shutil
from typing import Dict, Any, Optional, Union, List
from pathlib import Path
from datetime import datetime
from copy import deepcopy

from PySide6.QtCore import QObject, Signal
from config.config import save_atomic

class SettingsManager(QObject):
    """
    Manages application settings with automatic repair, backups, and Qt signal integration.
    """
    setting_changed = Signal(str, object)  # Emits: key, new_value

    def __init__(self, settings_file_path: Union[str, Path], default_settings: Optional[Dict[str, Any]] = None):
        super().__init__()
        self.settings_file_path = Path(settings_file_path)
        self.default_settings = deepcopy(default_settings or {})
        self.current_settings = {}

        self.settings_file_path.parent.mkdir(parents=True, exist_ok=True)
        self.load_settings()

    def load_settings(self) -> Dict[str, Any]:
        """
        Loads settings from the file. Creates default settings if the file is
        missing or corrupt.
        """
        try:
            if not self.settings_file_path.exists() or self.settings_file_path.stat().st_size == 0:
                logging.info("Settings file missing or empty. Creating with defaults.")
                self._create_default_settings()
            else:
                with open(self.settings_file_path, 'r', encoding='utf-8') as f:
                    loaded_settings = json.load(f)
                
                if not isinstance(loaded_settings, dict):
                    raise ValueError("Settings file does not contain a valid dictionary.")

                # Merge loaded settings with defaults to add new keys
                self.current_settings = deepcopy(self.default_settings)
                self.current_settings.update(deepcopy(loaded_settings))
                logging.info(f"Loaded {len(loaded_settings)} settings.")

        except (json.JSONDecodeError, ValueError) as e:
            logging.error(f"Error loading settings: {e}. Handling corrupt file.")
            self._handle_corrupt_settings()
        except Exception:
            logging.exception("An unexpected error occurred while loading settings.")
            self._create_default_settings()
        
        return deepcopy(self.current_settings)

    def save_settings(self) -> bool:
        """Saves the current settings to the file atomically."""
        try:
            temp_file = self.settings_file_path.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self.current_settings, f, indent=4, ensure_ascii=False)
            
            # Atomic move/replace
            temp_file.replace(self.settings_file_path)
            logging.debug(f"Settings saved to: {self.settings_file_path}")
            return True
        except Exception:
            logging.exception("Failed to save settings.")
            return False

    def get_setting(self, key: str, default: Any = None) -> Any:
        """Retrieves a single setting's value. Returns a deep copy for mutable types."""
        value = self.current_settings.get(key, default)
        if isinstance(value, (dict, list)):
            return deepcopy(value)
        return value

    def set_setting(self, key: str, value: Any, save_immediately: bool = True):
        """
        Sets a single setting's value and emits a signal.
        """
        old_value = self.current_settings.get(key)
        if old_value != value:
            stored_value = deepcopy(value) if isinstance(value, (dict, list)) else value
            emitted_value = deepcopy(stored_value) if isinstance(stored_value, (dict, list)) else stored_value
            self.current_settings[key] = stored_value
            logging.debug(f"Setting changed: {key} = {value} (was: {old_value})")
            self.setting_changed.emit(key, emitted_value)
            if save_immediately:
                self.save_settings()

    def update_settings(self, updates: Dict[str, Any], save_immediately: bool = True):
        """
        Updates multiple settings at once and emits signals for each change.
        """
        for key, value in updates.items():
            old_value = self.current_settings.get(key)
            if old_value != value:
                stored_value = deepcopy(value) if isinstance(value, (dict, list)) else value
                emitted_value = deepcopy(stored_value) if isinstance(stored_value, (dict, list)) else stored_value
                self.current_settings[key] = stored_value
                logging.debug(f"Setting changed: {key} = {value} (was: {old_value})")
                self.setting_changed.emit(key, emitted_value)
        
        if save_immediately:
            self.save_settings()

    def get_all_settings(self) -> Dict[str, Any]:
        """Returns a copy of all current settings."""
        return deepcopy(self.current_settings)

    # ERWEITERT: Gruppierte Einstellungen für das Layout-System
    def get_settings_by_keys(self, keys: List[str]) -> Dict[str, Any]:
        """
        Gibt eine Gruppe von Einstellungen basierend auf einer Liste von Schlüsseln zurück.
        """
        return {key: self.get_setting(key) for key in keys if key in self.current_settings}

    def get_font_settings(self) -> Dict[str, Any]:
        """Gibt alle schriftbezogenen Einstellungen zurück."""
        from config.constants import FONT_SETTING_KEYS
        return self.get_settings_by_keys(FONT_SETTING_KEYS)

    def get_color_settings(self) -> Dict[str, Any]:
        """Gibt alle farbbezogenen Einstellungen zurück."""
        from config.constants import COLOR_SETTING_KEYS
        return self.get_settings_by_keys(COLOR_SETTING_KEYS)

    def get_tray_settings(self) -> Dict[str, Any]:
        """Gibt alle tray-bezogenen Einstellungen zurück."""
        from config.constants import TRAY_SETTING_KEYS
        return self.get_settings_by_keys(TRAY_SETTING_KEYS)

    def get_widget_settings(self) -> Dict[str, Any]:
        """Gibt alle widget-darstellungsbezogenen Einstellungen zurück."""
        from config.constants import WIDGET_SETTING_KEYS
        return self.get_settings_by_keys(WIDGET_SETTING_KEYS)

    def get_opacity_settings(self) -> Dict[str, Any]:
        """Gibt alle transparenz-bezogenen Einstellungen zurück."""
        from config.constants import OPACITY_SETTING_KEYS
        return self.get_settings_by_keys(OPACITY_SETTING_KEYS)

    # NEU: Zusätzliche Einstellungsgruppen für vollständige Layout-Unterstützung
    def get_label_settings(self) -> Dict[str, Any]:
        """Gibt alle label-bezogenen Einstellungen zurück."""
        from config.constants import LABEL_SETTING_KEYS
        return self.get_settings_by_keys(LABEL_SETTING_KEYS)

    def get_visibility_settings(self) -> Dict[str, Any]:
        """Gibt alle sichtbarkeits-bezogenen Einstellungen zurück."""
        from config.constants import VISIBILITY_SETTING_KEYS
        return self.get_settings_by_keys(VISIBILITY_SETTING_KEYS)

    def get_hardware_settings(self) -> Dict[str, Any]:
        """Gibt alle hardware-auswahl-bezogenen Einstellungen zurück."""
        from config.constants import HARDWARE_SETTING_KEYS
        return self.get_settings_by_keys(HARDWARE_SETTING_KEYS)

    def get_unit_settings(self) -> Dict[str, Any]:
        """Gibt alle einheiten-bezogenen Einstellungen zurück."""
        from config.constants import UNIT_SETTING_KEYS
        return self.get_settings_by_keys(UNIT_SETTING_KEYS)

    def get_threshold_settings(self) -> Dict[str, Any]:
        """Gibt alle schwellenwert-bezogenen Einstellungen zurück."""
        from config.constants import THRESHOLD_SETTING_KEYS
        return self.get_settings_by_keys(THRESHOLD_SETTING_KEYS)

    def get_system_settings(self) -> Dict[str, Any]:
        """Gibt alle system-bezogenen Einstellungen zurück."""
        from config.constants import SYSTEM_SETTING_KEYS
        return self.get_settings_by_keys(SYSTEM_SETTING_KEYS)

    def get_window_settings(self) -> Dict[str, Any]:
        """Gibt alle fenster-bezogenen Einstellungen zurück."""
        from config.constants import WINDOW_SETTING_KEYS
        return self.get_settings_by_keys(WINDOW_SETTING_KEYS)

    def get_visual_settings(self) -> Dict[str, Dict[str, Any]]:
        """
        Gibt alle visuellen Einstellungen gruppiert zurück.
        ERWEITERT: Jetzt mit allen Layout-Kategorien für vollständige Unterstützung.
        """
        return {
            'font_settings': self.get_font_settings(),
            'color_settings': self.get_color_settings(),
            'tray_settings': self.get_tray_settings(),
            'widget_settings': self.get_widget_settings(),
            'opacity_settings': self.get_opacity_settings()
        }

    def get_complete_layout_settings(self) -> Dict[str, Dict[str, Any]]:
        """
        Gibt ALLE layout-relevanten Einstellungen gruppiert zurück.
        NEU: Umfasst auch Label-Texte, Sichtbarkeit, Hardware-Auswahl, etc.
        """
        from config.constants import CUSTOM_SENSOR_SETTING_KEYS # Import hinzugefügt für Vollständigkeit
        return {
            'font_settings': self.get_font_settings(),
            'color_settings': self.get_color_settings(),
            'tray_settings': self.get_tray_settings(),
            'widget_settings': self.get_widget_settings(),
            'opacity_settings': self.get_opacity_settings(),
            'label_settings': self.get_label_settings(),
            'visibility_settings': self.get_visibility_settings(),
            'hardware_settings': self.get_hardware_settings(),
            'custom_sensor_settings': self.get_settings_by_keys(CUSTOM_SENSOR_SETTING_KEYS),
            'unit_settings': self.get_unit_settings(),
            'threshold_settings': self.get_threshold_settings(),
            'system_settings': self.get_system_settings(),
            'window_settings': self.get_window_settings()
        }

    def apply_settings_group(self, group_settings: Dict[str, Any], save_immediately: bool = True):
        """
        Wendet eine Gruppe von Einstellungen an. Ignoriert None-Werte.
        Optimiert für das Layout-System.
        """
        updates = {key: value for key, value in group_settings.items() if value is not None}
        if updates:
            self.update_settings(updates, save_immediately)

    def apply_complete_layout_settings(self, layout_settings: Dict[str, Dict[str, Any]], save_immediately: bool = True):
        """
        Wendet alle Layout-Einstellungen aus einem Layout an.
        NEU: Unterstützt alle Kategorien für vollständige Layout-Wiederherstellung.
        """
        all_updates = {}
        
        # Sammle alle Einstellungen aus allen Kategorien
        for category_name, category_settings in layout_settings.items():
            if isinstance(category_settings, dict):
                all_updates.update({key: value for key, value in category_settings.items() if value is not None})
        
        if all_updates:
            self.update_settings(all_updates, save_immediately)

    def reset_settings_to_defaults_by_keys(self, keys: List[str], save_immediately: bool = True):
        """
        Setzt eine Gruppe von Einstellungen auf ihre Standardwerte zurück.
        """
        updates = {}
        for key in keys:
            if key in self.default_settings:
                updates[key] = deepcopy(self.default_settings[key])
        
        if updates:
            self.update_settings(updates, save_immediately)

    def reset_visual_settings_to_defaults(self, save_immediately: bool = True):
        """
        Setzt alle visuellen Einstellungen auf ihre Standardwerte zurück.
        Perfekt für die "Zurücksetzen"-Funktion.
        """
        from config.constants import (FONT_SETTING_KEYS, COLOR_SETTING_KEYS, 
                                     TRAY_SETTING_KEYS, WIDGET_SETTING_KEYS, 
                                     OPACITY_SETTING_KEYS)
        
        all_visual_keys = (FONT_SETTING_KEYS + COLOR_SETTING_KEYS + 
                          TRAY_SETTING_KEYS + WIDGET_SETTING_KEYS + 
                          OPACITY_SETTING_KEYS)
        
        self.reset_settings_to_defaults_by_keys(all_visual_keys, save_immediately)

    def reset_complete_layout_settings_to_defaults(self, save_immediately: bool = True):
        """
        Setzt ALLE layout-relevanten Einstellungen auf ihre Standardwerte zurück.
        NEU: Umfasst auch Label-Texte, Sichtbarkeit, Hardware-Auswahl, etc.
        """
        from config.constants import (FONT_SETTING_KEYS, COLOR_SETTING_KEYS, 
                                     TRAY_SETTING_KEYS, WIDGET_SETTING_KEYS, 
                                     OPACITY_SETTING_KEYS, LABEL_SETTING_KEYS,
                                     VISIBILITY_SETTING_KEYS, HARDWARE_SETTING_KEYS,
                                     UNIT_SETTING_KEYS, THRESHOLD_SETTING_KEYS,
                                     SYSTEM_SETTING_KEYS, WINDOW_SETTING_KEYS,
                                     CUSTOM_SENSOR_SETTING_KEYS)
        
        all_layout_keys = (FONT_SETTING_KEYS + COLOR_SETTING_KEYS + 
                          TRAY_SETTING_KEYS + WIDGET_SETTING_KEYS + 
                          OPACITY_SETTING_KEYS + LABEL_SETTING_KEYS +
                          VISIBILITY_SETTING_KEYS + HARDWARE_SETTING_KEYS +
                          UNIT_SETTING_KEYS + THRESHOLD_SETTING_KEYS +
                          SYSTEM_SETTING_KEYS + WINDOW_SETTING_KEYS +
                          CUSTOM_SENSOR_SETTING_KEYS)
        
        self.reset_settings_to_defaults_by_keys(all_layout_keys, save_immediately)

    def export_settings(self, file_path: Union[str, Path]) -> bool:
        """Exports settings to a specified file."""
        try:
            export_path = Path(file_path)
            if not save_atomic(self.current_settings, export_path):
                logging.error(f"Failed to export settings to: {export_path}")
                return False
            logging.info(f"Settings exported to: {export_path}")
            return True
        except Exception:
            logging.exception(f"Failed to export settings to: {file_path}")
            return False

    def import_settings(self, file_path: Union[str, Path]) -> bool:
        """Imports settings from a specified file."""
        try:
            import_path = Path(file_path)
            if not import_path.exists():
                logging.error(f"Import file does not exist: {import_path}")
                return False

            with open(import_path, 'r', encoding='utf-8') as f:
                imported_settings = json.load(f)
            
            if not isinstance(imported_settings, dict):
                raise ValueError("Import file does not contain a valid settings dictionary.")

            sanitized_settings = self._sanitize_imported_settings(imported_settings)
            new_settings = deepcopy(self.default_settings)
            new_settings.update(sanitized_settings)

            backup_path = self._backup_current_settings("backup")
            if self.settings_file_path.exists() and backup_path is None:
                return False

            old_settings = deepcopy(self.current_settings)
            self.current_settings = new_settings
            if not self.save_settings():
                self.current_settings = old_settings
                return False

            self._emit_changed_signals(old_settings, self.current_settings)
            logging.info(f"Settings imported from: {import_path}")
            return True
        except Exception:
            logging.exception(f"Failed to import settings from: {file_path}")
            return False

    def reset_to_defaults(self) -> bool:
        """Resets all settings to their default values."""
        try:
            backup_path = self._backup_current_settings("reset_backup")
            if self.settings_file_path.exists() and backup_path is None:
                return False

            old_settings = deepcopy(self.current_settings)
            self.current_settings = deepcopy(self.default_settings)
            if not self.save_settings():
                self.current_settings = old_settings
                return False

            logging.info("Settings reset to defaults.")
            return True
        except Exception:
            logging.exception("Failed to reset settings to defaults.")
            return False

    def _create_default_settings(self):
        """Creates a new settings file with default values."""
        self.current_settings = deepcopy(self.default_settings)
        self.save_settings()
        logging.info("Default settings created and saved.")

    def _handle_corrupt_settings(self):
        """Backs up a corrupt settings file and creates a new one with defaults."""
        logging.warning("Settings file is corrupt. Creating backup and new settings.")
        try:
            corrupt_backup_path = self.settings_file_path.with_name(
                f"{self.settings_file_path.stem}_corrupt_{datetime.now():%Y%m%d%H%M%S}.json"
            )
            if self.settings_file_path.exists():
                shutil.copy2(self.settings_file_path, corrupt_backup_path)
                logging.info(f"Backup of corrupt file saved to: {corrupt_backup_path}")
        except Exception:
            logging.exception("Failed to create backup of corrupt settings file.")
        
        self._create_default_settings()

    def _backup_current_settings(self, suffix: str) -> Optional[Path]:
        """Creates a timestamped backup of the current settings file."""
        if not self.settings_file_path.exists():
            return None

        backup_path = self.settings_file_path.with_name(
            f"{self.settings_file_path.stem}_{suffix}_{datetime.now():%Y%m%d%H%M%S}.json"
        )
        try:
            shutil.copy2(self.settings_file_path, backup_path)
            logging.info(f"Current settings backed up to: {backup_path}")
            return backup_path
        except Exception:
            logging.exception("Failed to back up current settings before import/reset.")
            return None

    def _emit_changed_signals(self, old_settings: Dict[str, Any], new_settings: Dict[str, Any]):
        """Emits setting_changed for every key whose effective value changed."""
        all_keys = set(old_settings) | set(new_settings)
        for key in all_keys:
            old_value = old_settings.get(key)
            new_value = new_settings.get(key)
            if old_value != new_value:
                emitted_value = deepcopy(new_value) if isinstance(new_value, (dict, list)) else new_value
                self.setting_changed.emit(key, emitted_value)

    def _sanitize_imported_settings(self, imported_settings: Dict[str, Any]) -> Dict[str, Any]:
        """Filters unknown keys and rejects values that are incompatible with the known schema."""
        sanitized: Dict[str, Any] = {}
        known_keys = set(self.default_settings) | set(self.current_settings)

        for key, value in imported_settings.items():
            if not self._is_importable_setting_key(key, known_keys):
                logging.warning("Ignoring unknown imported setting key: %s", key)
                continue

            if key in self.default_settings and not self._is_compatible_with_default(
                self.default_settings[key],
                value,
            ):
                logging.warning("Ignoring imported setting with incompatible type: %s", key)
                continue

            sanitized[key] = deepcopy(value)

        return sanitized

    def _is_importable_setting_key(self, key: str, known_keys: set[str]) -> bool:
        """Returns True for keys that are part of the schema or valid dynamic settings."""
        return key in known_keys or key.startswith("show_")

    def _is_compatible_with_default(self, default_value: Any, imported_value: Any) -> bool:
        """Checks whether an imported value fits the schema implied by the default value."""
        if default_value is None:
            return True
        if isinstance(default_value, bool):
            return isinstance(imported_value, bool)
        if isinstance(default_value, int):
            return isinstance(imported_value, int) and not isinstance(imported_value, bool)
        if isinstance(default_value, float):
            return isinstance(imported_value, (int, float)) and not isinstance(imported_value, bool)
        if isinstance(default_value, str):
            return isinstance(imported_value, str)
        if isinstance(default_value, dict):
            return isinstance(imported_value, dict)
        if isinstance(default_value, list):
            return isinstance(imported_value, list)
        return isinstance(imported_value, type(default_value))
