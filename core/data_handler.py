# core/data_handler.py
from __future__ import annotations
import logging
from typing import TYPE_CHECKING, Dict, Any, Optional, Callable

from PySide6.QtCore import QObject, Signal, Slot
from config.constants import SettingsKey, TemperatureUnit, DisplayMode, ValueFormat

if TYPE_CHECKING:
    from core.app_context import AppContext


class DataHandler(QObject):
    """
    Verarbeitet Rohdaten, konvertiert Einheiten und stellt sie zur Anzeige bereit.
    Sendet ein Signal mit den aufbereiteten Daten, anstatt die UI direkt zu manipulieren.
    """
    metric_updated = Signal(str, dict)
    alarm_state_changed = Signal(bool)

    def __init__(self, context: "AppContext", parent: QObject | None = None):
        super().__init__(parent)
        self.context = context
        self.translator = context.translator
        self.settings_manager = context.settings_manager
        self.custom_sensors = {}  # Cache für Custom Sensors
        self._define_metric_configs()
        self._load_custom_sensors()

    # NEU: Slot, der auf Änderungen in den Einstellungen reagiert
    @Slot(str, object)
    def on_setting_changed(self, key: str, value: Any):
        """Aktualisiert den internen Cache, wenn sich relevante Einstellungen ändern."""
        if key == SettingsKey.CUSTOM_SENSORS.value:
            logging.debug("DataHandler hat eine Änderung an den Custom Sensors erkannt und aktualisiert den Cache.")
            self.refresh_custom_sensors()

    def _define_metric_configs(self):
        """Definiert eine zentrale Konfiguration für alle Metriken."""
        self.METRIC_CONFIG = {
            "cpu": {"data_key": "cpu_percent", "percent_key": "cpu_percent", "format": "{value:.1f}%", "color_key": SettingsKey.CPU_COLOR, "threshold_key": SettingsKey.CPU_THRESHOLD},
            "cpu_temp": {"data_key": "cpu_temp", "format": "{value:.0f}{unit}", "unit_setting": SettingsKey.TEMPERATURE_UNIT, "color_key": SettingsKey.CPU_TEMP_COLOR, "threshold_key": SettingsKey.CPU_TEMP_THRESHOLD},
            "ram": {"format": "{used:.1f}/{total:.1f} GB", "percent_key": "ram_percent", "value_func": lambda d: {"used": d.get("ram_used_gb", 0), "total": d.get("ram_total_gb", 0)}, "color_key": SettingsKey.RAM_COLOR, "threshold_key": SettingsKey.RAM_THRESHOLD},
            "disk": {"data_key": "disk_percent", "percent_key": "disk_percent", "format": "{value:.1f}%", "na_value": -1.0, "color_key": SettingsKey.DISK_COLOR, "threshold_key": SettingsKey.DISK_THRESHOLD},
            "disk_io": {"format_func": self._format_disk_io, "alarm_func": self._is_disk_io_alarm, "color_key": SettingsKey.DISK_IO_COLOR},
            "net": {"format_func": self._format_network, "alarm_func": self._is_net_alarm, "color_key": SettingsKey.NET_COLOR},
            "gpu": {"data_key": "gpu_core_temp", "format": "{value:.0f}{unit}", "unit_setting": SettingsKey.TEMPERATURE_UNIT, "color_key": SettingsKey.GPU_CORE_TEMP_COLOR, "threshold_key": SettingsKey.GPU_CORE_TEMP_THRESHOLD},
            "gpu_hotspot": {"data_key": "gpu_hotspot_temp", "format": "{value:.0f}{unit}", "unit_setting": SettingsKey.TEMPERATURE_UNIT, "color_key": SettingsKey.GPU_HOTSPOT_COLOR, "threshold_key": SettingsKey.GPU_HOTSPOT_THRESHOLD},
            "gpu_memory_temp": {"data_key": "gpu_memory_temp", "format": "{value:.0f}{unit}", "unit_setting": SettingsKey.TEMPERATURE_UNIT, "color_key": SettingsKey.GPU_MEMORY_TEMP_COLOR, "threshold_key": SettingsKey.GPU_MEMORY_TEMP_THRESHOLD},
            "gpu_vram": {"format": "{used:.1f}/{total:.1f} GB", "percent_key": "vram_percent", "value_func": lambda d: {"used": d.get("vram_used_gb", 0), "total": d.get("vram_total_gb", 0)}, "color_key": SettingsKey.GPU_VRAM_COLOR, "threshold_key": SettingsKey.VRAM_THRESHOLD},
            "gpu_core_clock": {"data_key": "gpu_core_clock", "format": "{value:.0f} MHz", "color_key": SettingsKey.GPU_CORE_CLOCK_COLOR, "threshold_key": SettingsKey.GPU_CORE_CLOCK_THRESHOLD},
            "gpu_memory_clock": {"data_key": "gpu_memory_clock", "format": "{value:.0f} MHz", "color_key": SettingsKey.GPU_MEMORY_CLOCK_COLOR, "threshold_key": SettingsKey.GPU_MEMORY_CLOCK_THRESHOLD},
            "gpu_power": {"data_key": "gpu_power", "format": "{value:.1f} W", "color_key": SettingsKey.GPU_POWER_COLOR, "threshold_key": SettingsKey.GPU_POWER_THRESHOLD},
        }
        self._add_storage_configs()

    def _load_custom_sensors(self):
        """Lädt Custom Sensors aus den Einstellungen und fügt sie zur METRIC_CONFIG hinzu."""
        custom_sensors = self.settings_manager.get_setting(SettingsKey.CUSTOM_SENSORS.value, {})
        
        for sensor_id, sensor_data in custom_sensors.items():
            if not sensor_data.get('enabled', True):
                continue
                
            metric_key = f"custom_{sensor_id}"
            
            # Custom Sensor zu Cache hinzufügen
            self.custom_sensors[metric_key] = {
                'identifier': sensor_data.get('identifier', ''),
                'display_name': sensor_data.get('display_name', ''),
                'unit': sensor_data.get('unit', ''),
                'color': sensor_data.get('color', '#FFFFFF'),
                'sensor_type': sensor_data.get('sensor_type', '')
            }
            
            # Custom Sensor zur METRIC_CONFIG hinzufügen
            self.METRIC_CONFIG[metric_key] = {
                "value_func": self._create_custom_sensor_value_func(metric_key),
                "format": "{value:.1f}{unit}",
                "unit_setting": None,
                "color_key": None,
                "threshold_key": None,
                "custom_sensor": True
            }
            
        logging.info(f"Loaded {len(self.custom_sensors)} custom sensors")

    def _create_custom_sensor_value_func(self, metric_key: str) -> Callable[[Dict[str, Any]], Optional[float]]:
        """Erstellt eine Funktion zum Lesen von Custom Sensor Werten."""
        def value_func(data: Dict[str, Any]) -> Optional[float]:
            return self._read_custom_sensor(data, metric_key)
        return value_func

    def _read_custom_sensor(self, data: Dict[str, Any], metric_key: str) -> Optional[float]:
        """Liest den Wert eines Custom Sensors aus den Hardware-Daten."""
        if metric_key not in self.custom_sensors:
            return None
            
        identifier = self.custom_sensors[metric_key]['identifier']
        
        custom_sensor_data = data.get('custom_sensors', {})
        value = custom_sensor_data.get(identifier)
        
        if value is not None:
            logging.debug(f"Custom Sensor {metric_key} ({identifier}): {value}")
            return float(value)
        else:
            logging.debug(f"Custom Sensor {metric_key} ({identifier}): Kein Wert verfügbar")
            return None

    def refresh_custom_sensors(self):
        """Lädt Custom Sensors neu und aktualisiert die METRIC_CONFIG."""
        keys_to_remove = [key for key in self.METRIC_CONFIG.keys() if key.startswith('custom_')]
        for key in keys_to_remove:
            del self.METRIC_CONFIG[key]
        
        self.custom_sensors.clear()
        self._load_custom_sensors()
        
        logging.info("Custom Sensors im DataHandler aktualisiert.")

    def _create_value_func(self, storage_key: str) -> Callable[[Dict[str, Any]], Optional[float]]:
        """Erstellt eine Funktion, die den Wert für einen bestimmten Storage-Key extrahiert."""
        def value_func(data: Dict[str, Any]) -> Optional[float]:
            return self._get_storage_temp_value(data, storage_key)
        return value_func

    def _add_storage_configs(self):
        """Fügt dynamische Storage-Konfigurationen hinzu."""
        for key in self.context.hardware_manager.storage_sensors:
            metric_key = f"storage_temp_{key}"
            self.METRIC_CONFIG[metric_key] = {
                "format": "{value:.0f}{unit}",
                "unit_setting": SettingsKey.TEMPERATURE_UNIT,
                "value_func": self._create_value_func(key),
                "color_key": SettingsKey.STORAGE_TEMP_COLOR,
                "threshold_key": SettingsKey.STORAGE_TEMP_THRESHOLD
            }

    def _get_storage_temp_value(self, data: Dict[str, Any], storage_key: str) -> Optional[float]:
        """Extrahiert eine spezifische Storage-Temperatur aus den Rohdaten."""
        storage_temps = data.get('storage_temps', [])
        if not storage_temps:
            logging.debug(f"Keine Storage-Temperaturen in den Daten gefunden für Key: {storage_key}")
            return None
            
        for drive in storage_temps:
            if drive.get('key') == storage_key:
                temp_value = drive.get('temp')
                logging.debug(f"Storage-Temperatur gefunden für {storage_key}: {temp_value}°C")
                return temp_value
                
        logging.debug(f"Storage-Key '{storage_key}' nicht in den verfügbaren Daten gefunden: {[d.get('key') for d in storage_temps]}")
        return None

    def _is_metric_visible(self, metric_key: str) -> bool:
        """Prüft, ob eine Metrik in der UI angezeigt wird."""
        visibility_key = f"show_{metric_key}"
        return self.settings_manager.get_setting(visibility_key, True)

    def process_new_data(self, data: Dict[str, Any]):
        """Verarbeitet neue Rohdaten und sendet Signale mit aufbereiteten Informationen."""
        any_alarm = False
        
        if 'storage_temps' in data:
            logging.debug(f"Verarbeite Storage-Temperaturen: {len(data['storage_temps'])} Sensoren")
            for temp_data in data['storage_temps']:
                logging.debug(f"  Storage: {temp_data.get('key')} = {temp_data.get('temp')}°C")
        
        if 'custom_sensors' in data:
            logging.debug(f"Verarbeite Custom Sensors: {len(data['custom_sensors'])} Sensoren")
            for identifier, value in data['custom_sensors'].items():
                logging.debug(f"  Custom: {identifier} = {value}")
        
        for key, config in self.METRIC_CONFIG.items():
            is_alarm = self._process_single_metric(key, config, data)
            if is_alarm:
                any_alarm = True
        self.alarm_state_changed.emit(any_alarm)

    def _process_single_metric(self, key: str, config: Dict[str, Any], data: Dict[str, Any]) -> bool:
        """Verarbeitet eine einzelne Metrik, sendet ein Signal und gibt den Alarmstatus zurück."""
        is_visible = self._is_metric_visible(key)
        
        raw_value = self._extract_raw_value(config, data)
        display_value = self._convert_value_unit(raw_value, config)
        
        is_alarm = False
        if is_visible:
            is_alarm = config.get("alarm_func", self._is_alarm)(config, data, raw_value)

        if config.get("custom_sensor"):
            normal_color = self.custom_sensors.get(key, {}).get('color', '#FFFFFF')
            alarm_color = "#FF4500"
        else:
            color_key_enum = config.get("color_key")
            normal_color, alarm_color = "#FFFFFF", "#FF4500"
            if color_key_enum:
                color_key = color_key_enum.value
                alarm_key = color_key.replace('_color', '_alarm_color')
                normal_color = self.settings_manager.get_setting(color_key)
                alarm_color = self.settings_manager.get_setting(alarm_key)

        if display_value is None:
            value_text, percent_value = self.translator.translate("na"), None
        else:
            value_text = self._format_value(config, display_value, key)
            percent_value = data.get(config.get("percent_key"))

        payload = {
            "value_text": value_text, "percent_value": percent_value,
            "is_alarm": is_alarm, "normal_color": normal_color, "alarm_color": alarm_color
        }
        
        if key.startswith('storage_temp_') or key.startswith('custom_'):
            logging.debug(f"Sende Metrik-Update für {key}: {value_text}")
        
        self.metric_updated.emit(key, payload)
        return is_alarm

    def _extract_raw_value(self, config: Dict[str, Any], data: Dict[str, Any]) -> Optional[Any]:
        if (value_func := config.get("value_func")): return value_func(data)
        if (data_key := config.get("data_key")): 
            value = data.get(data_key)
            return None if value == config.get("na_value") else value
        return data

    def _convert_value_unit(self, value: Any, config: Dict[str, Any]) -> Any:
        if value is None: return None
        if (unit_setting := config.get("unit_setting")) == SettingsKey.TEMPERATURE_UNIT:
            if self.settings_manager.get_setting(unit_setting.value) == TemperatureUnit.KELVIN.value:
                return float(value) + 273.15
        return value

    def _format_value(self, config: Dict[str, Any], value: Any, metric_key: str = None) -> str:
        if (format_func := config.get("format_func")): return format_func(value)[0]

        format_string = config.get("format", "")
        if self.settings_manager.get_setting(SettingsKey.VALUE_FORMAT.value) == ValueFormat.INTEGER.value:
            format_string = format_string.replace(":.1f", ":.0f").replace(":.2f", ":.0f")

        unit_symbol = ""
        
        if config.get("custom_sensor") and metric_key:
            unit_symbol = self.custom_sensors.get(metric_key, {}).get('unit', '')
        elif (unit_setting := config.get("unit_setting")):
            unit = self.settings_manager.get_setting(unit_setting.value, "")
            unit_symbol = "°C" if unit == "C" else (" K" if unit == "K" else unit)

        format_values = {"unit": unit_symbol}
        if isinstance(value, dict): format_values.update(value)
        else: format_values["value"] = value
        return format_string.format(**format_values)

    def _is_alarm(self, config: Dict[str, Any], data: Dict[str, Any], raw_value: Optional[float]) -> bool:
        if not (threshold_key_enum := config.get("threshold_key")): return False
        threshold = self.settings_manager.get_setting(threshold_key_enum.value)
        if threshold is None: return False
        
        value_to_check = data.get(config.get("percent_key")) if config.get("percent_key") else raw_value
        return value_to_check is not None and float(value_to_check) > float(threshold)

    def _is_disk_io_alarm(self, config, data, raw_value) -> bool:
        read_thresh = self.settings_manager.get_setting(SettingsKey.DISK_READ_THRESHOLD.value, float('inf'))
        write_thresh = self.settings_manager.get_setting(SettingsKey.DISK_WRITE_THRESHOLD.value, float('inf'))
        read_alarm = data.get('disk_read_mbps', 0) > read_thresh
        write_alarm = data.get('disk_write_mbps', 0) > write_thresh
        mode = self.settings_manager.get_setting(SettingsKey.DISK_IO_DISPLAY_MODE.value)
        if mode == DisplayMode.READ.value: return read_alarm
        if mode == DisplayMode.WRITE.value: return write_alarm
        return read_alarm or write_alarm

    def _is_net_alarm(self, config, data, raw_value) -> bool:
        up_thresh = self.settings_manager.get_setting(SettingsKey.NET_UP_THRESHOLD.value, float('inf'))
        down_thresh = self.settings_manager.get_setting(SettingsKey.NET_DOWN_THRESHOLD.value, float('inf'))
        up_alarm = data.get('net_up_mbps', 0) > up_thresh
        down_alarm = data.get('net_down_mbps', 0) > down_thresh
        mode = self.settings_manager.get_setting(SettingsKey.NETWORK_DISPLAY_MODE.value)
        if mode == DisplayMode.UP.value: return up_alarm
        if mode == DisplayMode.DOWN.value: return down_alarm
        return up_alarm or down_alarm

    def _format_disk_io(self, data: Dict[str, Any]) -> tuple[str, tuple[float, float]]:
        s = self.settings_manager
        unit = s.get_setting(SettingsKey.DISK_IO_UNIT.value, "MB/s")
        mode = s.get_setting(SettingsKey.DISK_IO_DISPLAY_MODE.value)
        read, write = data.get('disk_read_mbps', 0), data.get('disk_write_mbps', 0)
        fmt = ".0f" if s.get_setting(SettingsKey.VALUE_FORMAT.value) == ValueFormat.INTEGER.value else ".1f"
        
        r_str, w_str = f"R:{read:{fmt}}", f"W:{write:{fmt}}"
        if mode == DisplayMode.READ.value: text = f"{r_str} {unit}"
        elif mode == DisplayMode.WRITE.value: text = f"{w_str} {unit}"
        else: text = f"{r_str} {w_str} {unit}"
        return text, (read, write)

    def _format_network(self, data: Dict[str, Any]) -> tuple[str, tuple[float, float]]:
        s = self.settings_manager
        unit = s.get_setting(SettingsKey.NETWORK_UNIT.value, "MBit/s")
        mode = s.get_setting(SettingsKey.NETWORK_DISPLAY_MODE.value)
        up, down = data.get('net_up_mbps', 0), data.get('net_down_mbps', 0)
        fmt = ".0f" if s.get_setting(SettingsKey.VALUE_FORMAT.value) == ValueFormat.INTEGER.value else ".1f"

        if unit == "GBit/s": up /= 1000; down /= 1000
        up_str, down_str = f"▲{up:{fmt}}", f"▼{down:{fmt}}"
        
        if mode == DisplayMode.UP.value: text = f"{up_str} {unit}"
        elif mode == DisplayMode.DOWN.value: text = f"{down_str} {unit}"
        else: text = f"{up_str} {down_str} {unit}"
        return text, (up, down)