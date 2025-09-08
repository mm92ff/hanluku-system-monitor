# system_data_collector.py
"""
System Data Collector für Basis-Systemmetriken.
Sammelt CPU, RAM und Festplatten-Auslastung über psutil.
"""

import os
import logging
from typing import Dict

from utils.system_utils import psutil, PSUTIL_AVAILABLE

# Konstante für die Umrechnung von Bytes in Gigabytes
BYTES_TO_GB = 1024**3


class SystemDataCollector:
    """
    Sammelt grundlegende Systemmetriken wie CPU, RAM und Festplatten-Auslastung.
    Behandelt Fehler robust und liefert sinnvolle Fallback-Werte.
    """
    
    def __init__(self, settings: dict):
        self.settings = settings
        self._cpu_initialized = False
        if PSUTIL_AVAILABLE:
            self._initialize_cpu_monitoring()
        logging.debug("SystemDataCollector initialisiert")
    
    def _initialize_cpu_monitoring(self):
        """Initialisiert CPU-Monitoring für korrekte Prozentberechnung."""
        try:
            psutil.cpu_percent(interval=None)
            self._cpu_initialized = True
            logging.debug("CPU Monitoring initialisiert")
        except Exception as e:
            logging.error(f"CPU Monitoring Initialisierung fehlgeschlagen: {e}")
            self._cpu_initialized = False
    
    def update_settings(self, key: str, value):
        """Aktualisiert eine einzelne Einstellung."""
        self.settings[key] = value
        logging.debug(f"SystemDataCollector Einstellung aktualisiert: {key} = {value}")
    
    def collect_cpu_data(self) -> Dict[str, float]:
        """Sammelt CPU-Auslastungsdaten."""
        if not PSUTIL_AVAILABLE:
            return {'cpu_percent': 0.0}

        try:
            if not self._cpu_initialized:
                self._initialize_cpu_monitoring()
            
            cpu_percent = psutil.cpu_percent(interval=None)
            return {'cpu_percent': max(0.0, min(100.0, cpu_percent))}
        except Exception as e:
            logging.error(f"CPU-Datensammlung fehlgeschlagen: {e}")
            return {'cpu_percent': 0.0}
    
    def collect_ram_data(self) -> Dict[str, float]:
        """Sammelt RAM-Auslastungsdaten."""
        if not PSUTIL_AVAILABLE:
            return self._get_zero_ram_data()
            
        try:
            ram_info = psutil.virtual_memory()
            if ram_info is None or ram_info.total <= 0:
                return self._get_zero_ram_data()
            
            used_gb = ram_info.used / BYTES_TO_GB
            total_gb = ram_info.total / BYTES_TO_GB
            
            # Sanity-Check: 'used' kann nicht größer als 'total' sein.
            percent = min(100.0, ram_info.percent)
            if used_gb > total_gb:
                used_gb = total_gb
            
            return {
                'ram_used_gb': used_gb,
                'ram_total_gb': total_gb,
                'ram_percent': percent
            }
        except Exception as e:
            logging.error(f"RAM-Datensammlung fehlgeschlagen: {e}")
            return self._get_zero_ram_data()
    
    def collect_disk_data(self) -> Dict[str, float]:
        """Sammelt Festplatten-Auslastungsdaten."""
        if not PSUTIL_AVAILABLE:
            return {'disk_percent': -1.0}

        selected_disk = self.settings.get("selected_disk_partition")
        if not selected_disk:
            logging.debug("Keine Festplatte ausgewählt")
            return {'disk_percent': -1.0}
        
        try:
            if not os.path.exists(selected_disk):
                logging.warning(f"Festplatten-Pfad existiert nicht: {selected_disk}")
                return {'disk_percent': -1.0}
            
            disk_usage = psutil.disk_usage(selected_disk)
            percent = max(0.0, min(100.0, disk_usage.percent))
            return {'disk_percent': percent}
        except (PermissionError, FileNotFoundError, OSError) as e:
            logging.warning(f"Zugriff auf Festplatte '{selected_disk}' fehlgeschlagen: {e}")
            return {'disk_percent': -1.0}
        except Exception as e:
            logging.error(f"Allgemeiner Fehler bei Festplatten-Datensammlung: {e}")
            return {'disk_percent': -1.0}
    
    def collect_all(self) -> Dict[str, float]:
        """Sammelt alle verfügbaren Systemdaten."""
        data = {}
        data.update(self.collect_cpu_data())
        data.update(self.collect_ram_data())
        data.update(self.collect_disk_data())
        return data
    
    def _get_zero_ram_data(self) -> Dict[str, float]:
        """Gibt Null-Werte für RAM-Daten zurück."""
        return {'ram_used_gb': 0.0, 'ram_total_gb': 0.0, 'ram_percent': 0.0}