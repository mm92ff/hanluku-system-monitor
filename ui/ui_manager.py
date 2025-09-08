# ui/ui_manager.py
from __future__ import annotations
import logging
from typing import TYPE_CHECKING, Dict, Any

from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt, QTimer

from config.constants import SettingsKey

if TYPE_CHECKING:
    from core.main_window import SystemMonitor


class UIManager:
    """Verwaltet UI-Komponenten und deren Stile."""

    def __init__(self, main_window: SystemMonitor):
        self.main_win = main_window
        self.settings_manager = main_window.settings_manager
        self.metric_widgets: Dict[str, Dict[str, Any]] = {}
        
        # Diese Methode muss aufgerufen werden, *nachdem* der hw_manager initialisiert ist,
        # aber *bevor* die UI-Manager initialisiert werden.
        self.update_dynamic_metric_order()
        self._create_metric_rows()

    def update_dynamic_metric_order(self):
        """
        Aktualisiert die Metrik-Reihenfolge mit dynamisch erkannten Sensoren
        und speichert sie bei Bedarf zurück in die Einstellungen.
        Diese Logik lebt hier, da sie eine UI-Darstellungsangelegenheit ist.
        """
        metric_order = self.settings_manager.get_setting(SettingsKey.METRIC_ORDER.value, [])
        
        # Bereinige veralteten generischen Schlüssel, falls vorhanden
        if 'storage_temp' in metric_order:
            metric_order.remove('storage_temp')

        # Finde neue, noch nicht in der Reihenfolge enthaltene Storage-Sensoren
        storage_metric_keys = [f"storage_temp_{key}" for key in self.main_win.hw_manager.storage_sensors]
        new_storage_keys = [key for key in storage_metric_keys if key not in metric_order]

        # Finde neue Custom Sensors
        custom_sensors = self.settings_manager.get_setting(SettingsKey.CUSTOM_SENSORS.value, {})
        enabled_custom_sensors = [f"custom_{sensor_id}" for sensor_id, data in custom_sensors.items() if data.get('enabled', True)]
        new_custom_keys = [key for key in enabled_custom_sensors if key not in metric_order]

        # Füge neue Storage-Sensoren hinzu
        if new_storage_keys:
            try:
                # Füge die neuen Sensoren nach der allgemeinen Festplatten-Auslastung ein
                insert_index = metric_order.index('disk') + 1
            except ValueError:
                # Fallback: am Ende einfügen, falls 'disk' nicht gefunden wird
                insert_index = len(metric_order)
            
            metric_order[insert_index:insert_index] = new_storage_keys
            logging.info(f"{len(new_storage_keys)} neue Storage-Metriken zur Reihenfolge hinzugefügt.")
            
            # FIX: Stelle sicher, dass neue Storage-Widgets standardmäßig sichtbar sind
            for key in new_storage_keys:
                show_key = f"show_{key}"
                if not self.settings_manager.get_setting(show_key, False):
                    self.settings_manager.set_setting(show_key, True)
                    logging.debug(f"Storage-Widget '{key}' auf sichtbar gesetzt")

        # Füge neue Custom Sensors hinzu
        if new_custom_keys:
            # Custom Sensors am Ende hinzufügen
            metric_order.extend(new_custom_keys)
            logging.info(f"{len(new_custom_keys)} neue Custom Sensor-Metriken zur Reihenfolge hinzugefügt.")
            
            # Custom Sensors standardmäßig sichtbar setzen
            for key in new_custom_keys:
                show_key = f"show_{key}"
                if not self.settings_manager.get_setting(show_key, False):
                    self.settings_manager.set_setting(show_key, True)
                    logging.debug(f"Custom Sensor-Widget '{key}' auf sichtbar gesetzt")

        # Speichere aktualisierte Reihenfolge, falls Änderungen vorgenommen wurden
        if new_storage_keys or new_custom_keys:
            self.settings_manager.set_setting(SettingsKey.METRIC_ORDER.value, metric_order)

    def _create_metric_rows(self):
        """Erstellt die In-Memory-Definitionen für alle Metrik-Widgets."""
        self.metric_widgets.clear()

        # Basis-Metriken
        metrics_to_create = [
            ("cpu", "CPU:"), ("cpu_temp", "CPU Temp:"), ("ram", "RAM:"),
            ("disk", "Festplatte:"), ("disk_io", "Disk I/O:"), ("net", "Netzwerk:")
        ]

        # Dynamische Festplatten-Temperaturen
        for key, name in self.main_win.hw_manager.storage_display_names.items():
            metrics_to_create.append((f"storage_temp_{key}", f"{name}:"))

        # GPU-Metriken, falls unterstützt
        if self.main_win.hw_manager.lhm_support:
            gpu_metrics = [
                ("gpu", "GPU Core Temp:"), ("gpu_hotspot", "GPU Hotspot:"),
                ("gpu_memory_temp", "GPU Memory Temp:"), ("gpu_vram", "VRAM:"),
                ("gpu_core_clock", "GPU Core Clock:"), ("gpu_memory_clock", "GPU Memory Clock:"),
                ("gpu_power", "GPU Power:")
            ]
            metrics_to_create.extend(gpu_metrics)

        # Custom Sensors hinzufügen
        custom_sensors = self.settings_manager.get_setting(SettingsKey.CUSTOM_SENSORS.value, {})
        for sensor_id, sensor_data in custom_sensors.items():
            if sensor_data.get('enabled', True):
                metric_key = f"custom_{sensor_id}"
                display_name = sensor_data.get('display_name', f"Custom {sensor_id}")
                metrics_to_create.append((metric_key, f"{display_name}:"))

        for key, label_text in metrics_to_create:
            self.add_metric_row_definition(key, label_text)

        self.apply_custom_labels()

    def add_metric_row_definition(self, key: str, default_label_text: str):
        """Fügt eine Widget-Definition zum internen Dictionary hinzu."""
        custom_labels = self.settings_manager.get_setting(SettingsKey.CUSTOM_LABELS.value, {})
        display_text = custom_labels.get(key, default_label_text)
        
        # Custom Sensors haben standardmäßig keine Balken
        has_bar = key in ["cpu", "ram", "disk", "gpu_vram"]

        self.metric_widgets[key] = {
            'default_text': default_label_text,
            'full_text': display_text,
            'has_bar': has_bar
        }

    def apply_custom_labels(self):
        """
        Aktualisiert die Label-Texte in den internen Definitionen und
        wendet die globale Kürzungslogik an.
        """
        custom_labels = self.settings_manager.get_setting(SettingsKey.CUSTOM_LABELS.value, {})
        truncate = self.settings_manager.get_setting(SettingsKey.LABEL_TRUNCATE_ENABLED.value, False)
        limit = self.settings_manager.get_setting(SettingsKey.LABEL_TRUNCATE_LENGTH.value, 15)

        for key, item in self.metric_widgets.items():
            default_text = item.get('default_text', '')
            display_text = custom_labels.get(key, default_text)

            # Kürzungslogik
            if truncate and len(display_text) > limit:
                display_text = display_text[:limit - 2] + ".." if limit >= 3 else display_text[:limit]

            item['full_text'] = display_text

        if hasattr(self.main_win, 'detachable_manager'):
            self.main_win.detachable_manager.update_all_widget_labels()

    def apply_styles(self):
        """Wendet alle Stiländerungen auf die aktiven Widgets an."""
        if not hasattr(self.main_win, 'detachable_manager'):
            return

        self.main_win.detachable_manager.apply_styles_to_all_active_widgets()
        self.apply_custom_labels()

        # Triggere ein Daten-Update, um Farbänderungen zu übernehmen
        if hasattr(self.main_win, 'last_data') and self.main_win.last_data:
            self.main_win.context.data_handler.process_new_data(self.main_win.last_data)

        # Geändert: Feste Verzögerung durch robustere, sofortige Ausführung im nächsten Event-Loop ersetzt.
        QTimer.singleShot(0, self._refresh_all_widget_layouts)

    def _refresh_all_widget_layouts(self):
        """Aktualisiert alle Widget-Layouts nach Stil-Änderungen."""
        if hasattr(self.main_win, 'detachable_manager'):
            manager = self.main_win.detachable_manager
            manager._check_and_resolve_overlaps()
            # Geändert: Direkter Aufruf, da dieser Call bereits verzögert ist.
            manager._synchronize_group_layout()

    def refresh_metric_definitions(self):
        """Erneuert die Metrik-Definitionen nach Hardware-Änderungen oder Custom Sensor Updates."""
        # Custom Sensors in DataHandler neu laden
        if hasattr(self.main_win.context, 'data_handler'):
            self.main_win.context.data_handler.refresh_custom_sensors()
        
        # Dynamische Reihenfolge aktualisieren
        self.update_dynamic_metric_order()
        
        # Metrik-Definitionen neu erstellen
        self._create_metric_rows()
        
        # Widgets mit neuen Definitionen synchronisieren
        if hasattr(self.main_win, 'detachable_manager'):
            self.main_win.detachable_manager.sync_widgets_with_definitions()

    def get_metric_color(self, metric_key: str, is_alarm: bool = False) -> str:
        """Gibt die aktuelle Farbe für eine Metrik zurück."""
        # Custom Sensor Farbbehandlung
        if metric_key.startswith('custom_'):
            if hasattr(self.main_win.context, 'data_handler'):
                custom_sensors = self.main_win.context.data_handler.custom_sensors
                if metric_key in custom_sensors:
                    if is_alarm:
                        return "#FF4500"  # Standard Alarmfarbe für Custom Sensors
                    else:
                        return custom_sensors[metric_key].get('color', '#FFFFFF')
            return "#FFFFFF"
            
        if not hasattr(self.main_win.context, 'data_handler'):
            return "#FFFFFF"
            
        data_handler = self.main_win.context.data_handler
        config = data_handler.METRIC_CONFIG.get(metric_key, {})

        if is_alarm:
            color_key_enum = config.get("color_key")
            if color_key_enum:
                color_key = color_key_enum.value.replace("_color", "_alarm_color")
                default_color = "#FF4500"
            else: # Fallback für Metriken ohne direkte Farb-Enum (z.B. disk_io)
                color_key = "cpu_alarm_color"
                default_color = "#FF4500"
        else:
            color_key_enum = config.get("color_key")
            color_key = color_key_enum.value if color_key_enum else "cpu_color"
            default_color = "#FFFFFF"

        return self.settings_manager.get_setting(color_key, default_color)