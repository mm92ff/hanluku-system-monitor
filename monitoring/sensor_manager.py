# monitoring/sensor_manager.py
"""
Sensor Manager for LibreHardwareMonitor sensors.
Manages CPU, GPU and Storage sensors with health tracking.
"""
import logging
import time
from typing import Dict, List, Optional, Any, Set, TYPE_CHECKING

from config.constants import SettingsKey

if TYPE_CHECKING:
    from core.hardware_manager import HardwareManager

class SensorManager:
    """
    Manages LibreHardwareMonitor sensors with health tracking and error handling.
    Receives the HardwareManager as a dependency.
    """

    def __init__(self, hw_manager: "HardwareManager", settings: dict):
        self.hw_manager = hw_manager
        self.settings = settings

        self._sensor_health: Dict[str, Dict[str, Any]] = {}
        self._max_consecutive_failures = 3

        # Neu: Konfiguration für den Backoff-Mechanismus
        self.initial_backoff_sec = 15  # Erste Wartezeit: 15 Sekunden
        self.max_backoff_sec = 300     # Maximale Wartezeit: 5 Minuten

        self._sensor_read_count = 0
        self._successful_reads = 0
        self._failed_reads = 0

        self.custom_sensors_config = self.settings.get(SettingsKey.CUSTOM_SENSORS.value, {})
        self.custom_sensor_objects: Dict[str, Any] = {}
        self._map_custom_sensors()

        logging.debug(f"SensorManager initialisiert - Greift direkt auf HardwareManager zu.")

    def update_settings(self, key: str, value: Any):
        """Aktualisiert Einstellungen und führt bei Bedarf Aktionen aus."""
        self.settings[key] = value
        if key == SettingsKey.CUSTOM_SENSORS.value:
            logging.info("Custom-Sensor-Konfiguration geändert, mape Sensoren neu.")
            self.custom_sensors_config = value
            self._map_custom_sensors()

    def _map_custom_sensors(self):
        """Sucht die LHM-Sensor-Objekte rekursiv basierend auf den Identifiern in der Konfiguration."""
        self.custom_sensor_objects.clear()
        computer = self.hw_manager.computer
        if not computer or not self.custom_sensors_config:
            return

        # Erstelle ein Lookup-Dictionary aller zu findenden Sensoren für eine effizientere Suche
        identifiers_to_find = {}
        for config_id, sensor_data in self.custom_sensors_config.items():
            identifier = sensor_data.get('identifier')
            if identifier and sensor_data.get('enabled', True):
                metric_key = f"custom_{config_id}"
                display_name = sensor_data.get('display_name', 'Unbekannter Sensor')
                identifiers_to_find[identifier.strip()] = (metric_key, display_name)

        def find_sensors_recursively(hardware_item):
            """Eine interne Hilfsfunktion, die Hardware und deren Sub-Hardware durchsucht."""
            # Durchsuche Sensoren des aktuellen Hardware-Elements
            for sensor in hardware_item.Sensors:
                sensor_id = str(sensor.Identifier).strip()
                if sensor_id in identifiers_to_find:
                    metric_key, display_name = identifiers_to_find.pop(sensor_id)
                    self.custom_sensor_objects[metric_key] = sensor
                    logging.debug(f"Custom Sensor '{display_name}' auf LHM-Sensor '{sensor.Name}' gemappt.")

            # Rekursiver Aufruf für alle Unter-Geräte
            for sub_hw in hardware_item.SubHardware:
                sub_hw.Update()  # Wichtig: Stelle sicher, dass Sub-Hardware aktuell ist
                find_sensors_recursively(sub_hw)

        # Starte die rekursive Suche für alle Top-Level-Hardware-Elemente
        for hw in computer.Hardware:
            find_sensors_recursively(hw)
            if not identifiers_to_find:  # Breche ab, wenn alle Sensoren gefunden wurden
                break
        
        # Logge alle Sensoren, die nach der vollständigen Suche nicht gefunden werden konnten
        if identifiers_to_find:
            for identifier, (_, display_name) in identifiers_to_find.items():
                logging.warning(f"Custom Sensor '{display_name}' mit Identifier '{identifier}' konnte nicht gefunden werden.")

    def _safe_hardware_update(self) -> bool:
        """Performs a safe hardware update for all components."""
        computer = self.hw_manager.computer
        if not computer:
            return False
        try:
            for hardware in computer.Hardware:
                hardware.Update()
            return True
        except Exception:
            logging.exception("Hardware Update komplett fehlgeschlagen.")
            return False

    def _safe_sensor_read(self, sensor: Any, sensor_key: str) -> Optional[float]:
        """Safely reads a sensor's value with health tracking."""
        self._sensor_read_count += 1
        
        health = self._sensor_health.get(sensor_key)
        if health:
            disabled_until = health.get("disabled_until")
            if disabled_until and time.time() < disabled_until:
                return None  # Überspringe das Auslesen, wenn die Strafzeit noch aktiv ist

        try:
            if not hasattr(sensor, 'Value') or sensor.Value is None:
                self._track_sensor_health(sensor_key, False, "Sensor hat kein Value-Attribut oder ist None")
                return None
            
            value = float(sensor.Value)
            self._track_sensor_health(sensor_key, True)
            self._successful_reads += 1
            return value
        except Exception as e:
            error_msg = f"Sensor Read Fehler: {e}"
            self._track_sensor_health(sensor_key, False, error_msg)
            self._failed_reads += 1
            logging.warning(f"Fehler bei Sensor '{sensor_key}': {error_msg}")
            return None

    def _track_sensor_health(self, sensor_key: str, success: bool, error_msg: Optional[str] = None):
        """Tracks sensor health and applies an exponential backoff on repeated failures."""
        if sensor_key not in self._sensor_health:
            self._sensor_health[sensor_key] = {'consecutive_failures': 0, 'backoff_level': 0}

        health = self._sensor_health[sensor_key]

        if success:
            if health['consecutive_failures'] > 0 or 'disabled_until' in health:
                logging.info(f"Sensor '{sensor_key}' hat sich erholt und funktioniert wieder.")
            health['consecutive_failures'] = 0
            health['backoff_level'] = 0
            health.pop('disabled_until', None)
        else:
            health['consecutive_failures'] += 1
            if health['consecutive_failures'] >= self._max_consecutive_failures:
                health['consecutive_failures'] = 0
                
                backoff_level = health.get('backoff_level', 0)
                delay = min(self.max_backoff_sec, self.initial_backoff_sec * (2 ** backoff_level))
                
                health['disabled_until'] = time.time() + delay
                health['backoff_level'] = backoff_level + 1
                
                logging.warning(
                    f"Sensor '{sensor_key}' ist {self._max_consecutive_failures} Mal fehlgeschlagen. "
                    f"Wird temporär für {delay:.0f} Sekunden deaktiviert. Fehler: {error_msg}"
                )

    def read_cpu_temperature(self) -> Optional[float]:
        cpu_sensor = self.hw_manager.cpu_sensor
        return self._safe_sensor_read(cpu_sensor, "cpu_temp") if cpu_sensor else None

    def read_gpu_data(self) -> Dict[str, float]:
        gpu_sensors = self.hw_manager.gpu_sensors
        if not gpu_sensors: return {}
            
        gpu_data = {}
        sensor_map = {
            "gpu_core_temp": "gpu_core_temp", "gpu_hotspot_temp": "gpu_hotspot_temp",
            "gpu_memory_temp": "gpu_memory_temp", "gpu_core_clock": "core_clock",
            "gpu_memory_clock": "memory_clock", "gpu_power": "power",
        }
        for data_key, sensor_name in sensor_map.items():
            if sensor := gpu_sensors.get(sensor_name):
                if (value := self._safe_sensor_read(sensor, f"gpu_{sensor_name}")) is not None:
                    gpu_data[data_key] = value

        used_sensor, total_sensor = gpu_sensors.get('vram_used'), gpu_sensors.get('vram_total')
        if used_sensor and total_sensor:
            used_val = self._safe_sensor_read(used_sensor, "gpu_vram_used")
            total_val = self._safe_sensor_read(total_sensor, "gpu_vram_total")
            if used_val is not None and total_val is not None and total_val > 0:
                gpu_data['vram_used_gb'] = used_val / 1024
                gpu_data['vram_total_gb'] = total_val / 1024
                gpu_data['vram_percent'] = min(100.0, (used_val / total_val) * 100)
        
        return gpu_data

    def read_storage_temperatures(self) -> List[Dict[str, Any]]:
        storage_sensors = self.hw_manager.storage_sensors
        if not storage_sensors: return []
            
        temps = []
        for key, sensor in storage_sensors.items():
            if (temp := self._safe_sensor_read(sensor, f"storage_{key}")) is not None:
                display_name = self.hw_manager.storage_display_names.get(key, key.split('_')[0])
                temps.append({'key': key, 'name': display_name, 'temp': temp})
        return temps

    def read_custom_sensor_data(self) -> Dict[str, Any]:
        """Liest die Werte aller gemappten Custom Sensors."""
        if not self.custom_sensor_objects:
            return {}

        custom_sensor_values = {}
        for metric_key, sensor_obj in self.custom_sensor_objects.items():
            config_id = metric_key.replace("custom_", "", 1)
            config = self.custom_sensors_config.get(config_id, {})
            identifier = config.get("identifier")
            
            if identifier:
                value = self._safe_sensor_read(sensor_obj, metric_key)
                if value is not None:
                    custom_sensor_values[identifier] = value
        
        return {'custom_sensors': custom_sensor_values} if custom_sensor_values else {}

    def read_all_sensors(self) -> Dict[str, Any]:
        """Liest alle Sensoren, inklusive der Custom Sensors."""
        if not self._safe_hardware_update():
            logging.warning("Hardware Update fehlgeschlagen - Sensor-Daten könnten veraltet sein")
        
        data = {}
        if (cpu_temp := self.read_cpu_temperature()) is not None: data['cpu_temp'] = cpu_temp
        data.update(self.read_gpu_data())
        
        if storage_temps := self.read_storage_temperatures(): 
            data['storage_temps'] = storage_temps
            logging.debug(f"Storage-Temperaturen gelesen: {len(storage_temps)} Sensoren")

        data.update(self.read_custom_sensor_data())

        return data

    def get_sensor_health_report(self) -> Dict[str, Any]:
        success_rate = (self._successful_reads / self._sensor_read_count * 100) if self._sensor_read_count > 0 else 100
        
        disabled_sensors = [
            key for key, health in self._sensor_health.items()
            if health.get("disabled_until", 0) > time.time()
        ]
        
        return {
            'total_sensors_tracked': len(self._sensor_health),
            'temporarily_disabled_sensors': disabled_sensors,
            'sensor_read_attempts': self._sensor_read_count,
            'successful_reads': self._successful_reads,
            'failed_reads': self._failed_reads,
            'success_rate_percent': success_rate,
        }

    def _reset_sensor_health(self):
        self._sensor_health.clear()