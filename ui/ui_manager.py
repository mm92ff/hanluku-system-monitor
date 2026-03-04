from __future__ import annotations
import logging
from typing import TYPE_CHECKING, Dict, Any

from PySide6.QtCore import Qt, QTimer

from config.constants import SettingsKey

if TYPE_CHECKING:
    from core.main_window import SystemMonitor


class UIManager:
    """Verwaltet UI-Komponenten und deren Stile."""

    def __init__(self, main_window: SystemMonitor):
        self.main_win = main_window
        self.settings_manager = main_window.settings_manager
        self.translator = main_window.translator
        self.metric_widgets: Dict[str, Dict[str, Any]] = {}

        # Diese Methode muss aufgerufen werden, *nachdem* der hw_manager initialisiert ist,
        # aber *bevor* die UI-Manager initialisiert werden.
        self.update_dynamic_metric_order()
        self._create_metric_rows()

    def update_dynamic_metric_order(self):
        """
        Aktualisiert die Metrik-Reihenfolge mit dynamisch erkannten Sensoren
        und speichert sie bei Bedarf zurueck in die Einstellungen.
        Diese Logik lebt hier, da sie eine UI-Darstellungsangelegenheit ist.
        """
        metric_order = self.settings_manager.get_setting(SettingsKey.METRIC_ORDER.value, [])
        order_changed = False

        if "storage_temp" in metric_order:
            metric_order.remove("storage_temp")
            order_changed = True

        storage_metric_keys = [f"storage_temp_{key}" for key in self.main_win.hw_manager.storage_sensors]
        stale_storage_keys = [
            key for key in metric_order
            if key.startswith("storage_temp_") and key not in storage_metric_keys
        ]
        if stale_storage_keys:
            metric_order = [key for key in metric_order if key not in stale_storage_keys]
            order_changed = True
        new_storage_keys = [key for key in storage_metric_keys if key not in metric_order]

        custom_sensors = self.settings_manager.get_setting(SettingsKey.CUSTOM_SENSORS.value, {})
        enabled_custom_sensors = [
            f"custom_{sensor_id}"
            for sensor_id, data in custom_sensors.items()
            if data.get("enabled", True)
        ]
        stale_custom_keys = [
            key for key in metric_order
            if key.startswith("custom_") and key not in enabled_custom_sensors
        ]
        if stale_custom_keys:
            metric_order = [key for key in metric_order if key not in stale_custom_keys]
            order_changed = True
        new_custom_keys = [key for key in enabled_custom_sensors if key not in metric_order]

        if new_storage_keys:
            try:
                insert_index = metric_order.index("disk") + 1
            except ValueError:
                insert_index = len(metric_order)

            metric_order[insert_index:insert_index] = new_storage_keys
            order_changed = True
            logging.info(f"{len(new_storage_keys)} neue Storage-Metriken zur Reihenfolge hinzugefuegt.")

            for key in new_storage_keys:
                show_key = f"show_{key}"
                if not self.settings_manager.get_setting(show_key, False):
                    self.settings_manager.set_setting(show_key, True)
                    logging.debug(f"Storage-Widget '{key}' auf sichtbar gesetzt")

        if new_custom_keys:
            metric_order.extend(new_custom_keys)
            order_changed = True
            logging.info(f"{len(new_custom_keys)} neue Custom Sensor-Metriken zur Reihenfolge hinzugefuegt.")

            for key in new_custom_keys:
                show_key = f"show_{key}"
                if not self.settings_manager.get_setting(show_key, False):
                    self.settings_manager.set_setting(show_key, True)
                    logging.debug(f"Custom Sensor-Widget '{key}' auf sichtbar gesetzt")

        if order_changed:
            self.settings_manager.set_setting(SettingsKey.METRIC_ORDER.value, metric_order)

    def _get_static_metric_definitions(self):
        """Liefert die sprachabhaengigen Standard-Widgets."""
        metrics = [
            ("cpu", "widget_metric_cpu"),
            ("cpu_temp", "widget_metric_cpu_temp"),
            ("ram", "widget_metric_ram"),
            ("disk", "widget_metric_disk"),
            ("disk_io", "widget_metric_disk_io"),
            ("net", "widget_metric_network"),
        ]

        if self.main_win.hw_manager.lhm_support:
            metrics.extend([
                ("gpu", "widget_metric_gpu_core_temp"),
                ("gpu_hotspot", "widget_metric_gpu_hotspot"),
                ("gpu_memory_temp", "widget_metric_gpu_memory_temp"),
                ("gpu_vram", "widget_metric_vram"),
                ("gpu_core_clock", "widget_metric_gpu_core_clock"),
                ("gpu_memory_clock", "widget_metric_gpu_memory_clock"),
                ("gpu_power", "widget_metric_gpu_power"),
            ])

        return [
            (metric_key, f"{self.translator.translate(label_key)}:")
            for metric_key, label_key in metrics
        ]

    def _create_metric_rows(self):
        """Erstellt die In-Memory-Definitionen fuer alle Metrik-Widgets."""
        self.metric_widgets.clear()

        metrics_to_create = list(self._get_static_metric_definitions())

        for key, name in self.main_win.hw_manager.storage_display_names.items():
            metrics_to_create.append((f"storage_temp_{key}", f"{name}:"))

        custom_sensors = self.settings_manager.get_setting(SettingsKey.CUSTOM_SENSORS.value, {})
        for sensor_id, sensor_data in custom_sensors.items():
            if sensor_data.get("enabled", True):
                metric_key = f"custom_{sensor_id}"
                display_name = sensor_data.get("display_name", f"Custom {sensor_id}")
                metrics_to_create.append((metric_key, f"{display_name}:"))

        for key, label_text in metrics_to_create:
            self.add_metric_row_definition(key, label_text)

        self.apply_custom_labels()

    def add_metric_row_definition(self, key: str, default_label_text: str):
        """Fuegt eine Widget-Definition zum internen Dictionary hinzu."""
        custom_labels = self.settings_manager.get_setting(SettingsKey.CUSTOM_LABELS.value, {})
        display_text = custom_labels.get(key, default_label_text)

        has_bar = key in ["cpu", "ram", "disk", "gpu_vram"]

        self.metric_widgets[key] = {
            "default_text": default_label_text,
            "full_text": display_text,
            "has_bar": has_bar,
        }

    def apply_custom_labels(self):
        """
        Aktualisiert die Label-Texte in den internen Definitionen und
        wendet die globale Kuerzungslogik an.
        """
        custom_labels = self.settings_manager.get_setting(SettingsKey.CUSTOM_LABELS.value, {})
        truncate = self.settings_manager.get_setting(SettingsKey.LABEL_TRUNCATE_ENABLED.value, False)
        limit = self.settings_manager.get_setting(SettingsKey.LABEL_TRUNCATE_LENGTH.value, 15)

        for key, item in self.metric_widgets.items():
            default_text = item.get("default_text", "")
            display_text = custom_labels.get(key, default_text)

            if truncate and len(display_text) > limit:
                display_text = display_text[: limit - 2] + ".." if limit >= 3 else display_text[:limit]

            item["full_text"] = display_text

        if hasattr(self.main_win, "detachable_manager"):
            self.main_win.detachable_manager.update_all_widget_labels()

    def apply_styles(self):
        """Wendet alle Stilaenderungen auf die aktiven Widgets an."""
        if not hasattr(self.main_win, "detachable_manager"):
            return

        self.main_win.detachable_manager.apply_styles_to_all_active_widgets()
        self.apply_custom_labels()

        latest_data = self.main_win.context.get_latest_monitor_data()
        if latest_data:
            self.main_win.context.data_handler.process_new_data(latest_data)

        QTimer.singleShot(0, self._refresh_all_widget_layouts)

    def _refresh_all_widget_layouts(self):
        """Aktualisiert alle Widget-Layouts nach Stilaenderungen."""
        if hasattr(self.main_win, "detachable_manager"):
            manager = self.main_win.detachable_manager
            manager._check_and_resolve_overlaps()
            manager._synchronize_group_layout()

    def refresh_metric_definitions(self):
        """Erneuert die Metrik-Definitionen nach Hardware-Aenderungen oder Custom-Sensor-Updates."""
        if hasattr(self.main_win.context, "data_handler"):
            self.main_win.context.data_handler.refresh_custom_sensors()

        self.update_dynamic_metric_order()
        self._create_metric_rows()

        if hasattr(self.main_win, "detachable_manager"):
            self.main_win.detachable_manager.sync_widgets_with_definitions()

    def get_metric_color(self, metric_key: str, is_alarm: bool = False) -> str:
        """Gibt die aktuelle Farbe fuer eine Metrik zurueck."""
        if metric_key.startswith("custom_"):
            if hasattr(self.main_win.context, "data_handler"):
                custom_sensors = self.main_win.context.data_handler.custom_sensors
                if metric_key in custom_sensors:
                    if is_alarm:
                        return "#FF4500"
                    return custom_sensors[metric_key].get("color", "#FFFFFF")
            return "#FFFFFF"

        if not hasattr(self.main_win.context, "data_handler"):
            return "#FFFFFF"

        data_handler = self.main_win.context.data_handler
        config = data_handler.METRIC_CONFIG.get(metric_key, {})

        if is_alarm:
            color_key_enum = config.get("color_key")
            if color_key_enum:
                color_key = color_key_enum.value.replace("_color", "_alarm_color")
                default_color = "#FF4500"
            else:
                color_key = "cpu_alarm_color"
                default_color = "#FF4500"
        else:
            color_key_enum = config.get("color_key")
            color_key = color_key_enum.value if color_key_enum else "cpu_color"
            default_color = "#FFFFFF"

        return self.settings_manager.get_setting(color_key, default_color)
