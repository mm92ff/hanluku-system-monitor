# core/hardware_manager.py
import logging
import os
import sys
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Dict, Optional, Tuple

from utils.system_utils import psutil, PSUTIL_AVAILABLE
from config.config import CONFIG_DIR
from config.constants import AppInfo
from .sensor_cache import load_sensor_cache, save_sensor_cache
from .sensor_mapping import find_sensor, diagnose_sensor_matching, get_available_sensors_for_hardware

try:
    import clr
    LHM_SUPPORT = True
except ImportError:
    LHM_SUPPORT = False


@dataclass(frozen=True)
class HardwareOperationResult:
    success: bool
    message: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class HardwareSelectionState:
    cpu_identifier: str
    gpu_identifier: str


class HardwareManager:
    """Verwaltet LibreHardwareMonitor-Integration und grundlegende Hardware-Abfragen."""
    REQUIRED_DLLS = ("HidSharp.dll", "LibreHardwareMonitorLib.dll")

    def __init__(self):
        self.pythonnet_available = LHM_SUPPORT
        self.lhm_support = False
        self.computer = None
        self.lhm_error: str | None = None
        self._dll_directory_handle = None

        # Sensor-Zuordnungen
        self.cpus: List[Any] = []  # GEÄNDERT: Liste für mehrere CPUs
        self.cpu_sensor = None      # Hält den AKTIVEN CPU-Sensor
        self.gpus: List[Any] = []
        self.gpu_sensors: Dict[str, Any] = {}
        self.storage_sensors: Dict[str, Any] = {}
        self.storage_display_names: Dict[str, str] = {}
        self.selected_cpu_id = "auto"
        self.selected_gpu_id = "auto"

        # Cache-System
        self.sensor_cache = load_sensor_cache()
        self.cache_updated = False
        self.hardware_fingerprint = ""

        # Diagnose-Informationen
        self.initialization_log = []
        self.failed_sensors: Dict[str, Any] = {}
        self.hardware_detected: Dict[str, int] = {}
        self.last_operation_result = HardwareOperationResult(True, "Hardware manager bereit.")

        if self.pythonnet_available:
            self._initialize_lhm()
        else:
            self.lhm_error = "pythonnet/clr konnte nicht importiert werden."
            logging.error(self.lhm_error)
            self.initialization_log.append(f"FEHLER: {self.lhm_error}")

    @property
    def gpu_supported(self) -> bool:
        """Prüft dynamisch, ob GPU-Monitoring aktiv ist."""
        return bool(self.gpus and self.gpu_sensors)

    @classmethod
    def _get_dll_search_directories(cls) -> List[Path]:
        """Ermittelt mögliche Suchpfade für die benötigten .NET-DLLs."""
        directories: List[Path] = []

        if env_dir := os.environ.get(AppInfo.DLL_DIRECTORY_ENV_VAR):
            directories.append(Path(env_dir))

        if getattr(sys, "frozen", False):
            executable_dir = Path(sys.executable).resolve().parent
            directories.extend([executable_dir / "libs", executable_dir])

            if meipass := getattr(sys, "_MEIPASS", None):
                meipass_dir = Path(meipass)
                directories.extend([meipass_dir / "libs", meipass_dir])

        project_root = Path(__file__).resolve().parent.parent
        directories.extend([project_root / "libs", project_root])

        unique_directories: List[Path] = []
        seen = set()
        for directory in directories:
            normalized = str(directory.resolve(strict=False))
            if normalized in seen:
                continue
            seen.add(normalized)
            unique_directories.append(directory)
        return unique_directories

    @classmethod
    def _resolve_required_dll_paths(
        cls,
        search_directories: Optional[List[Path]] = None,
    ) -> Tuple[Optional[Dict[str, Path]], List[Path]]:
        """Liefert die Pfade aller benötigten DLLs aus einem gemeinsamen Verzeichnis."""
        candidate_directories = search_directories or cls._get_dll_search_directories()
        for directory in candidate_directories:
            dll_paths = {
                dll_name: directory / dll_name
                for dll_name in cls.REQUIRED_DLLS
            }
            if all(path.exists() for path in dll_paths.values()):
                return dll_paths, candidate_directories
        return None, candidate_directories

    def _add_windows_dll_directory(self, dll_directory: Path):
        """Registriert unter Windows einen DLL-Suchpfad für Abhängigkeiten."""
        if sys.platform != "win32" or not hasattr(os, "add_dll_directory"):
            return None
        try:
            return os.add_dll_directory(str(dll_directory))
        except OSError:
            logging.debug("Konnte DLL-Suchpfad nicht registrieren: %s", dll_directory, exc_info=True)
            return None

    def _initialize_lhm(self):
        """Initialisiert LHM mit verbesserter Fehlerbehandlung und Diagnose."""
        try:
            dll_paths, searched_directories = self._resolve_required_dll_paths()

            if not dll_paths:
                searched = ", ".join(str(path) for path in searched_directories)
                self.lhm_error = (
                    "Erforderliche LHM-DLLs nicht gefunden. "
                    f"Benötigt: {', '.join(self.REQUIRED_DLLS)} | Gesucht in: {searched}"
                )
                logging.error(self.lhm_error)
                self.initialization_log.append(f"FEHLER: {self.lhm_error}")
                return

            dll_directory = next(iter(dll_paths.values())).parent
            self._dll_directory_handle = self._add_windows_dll_directory(dll_directory)

            clr.AddReference(str(dll_paths["HidSharp.dll"]))
            clr.AddReference(str(dll_paths["LibreHardwareMonitorLib.dll"]))
            from LibreHardwareMonitor.Hardware import Computer

            self.computer = Computer()
            self.computer.IsCpuEnabled = True
            self.computer.IsGpuEnabled = True
            self.computer.IsStorageEnabled = True
            self.computer.IsMotherboardEnabled = True
            self.computer.IsControllerEnabled = True
            self.computer.IsNetworkEnabled = True
            self.computer.IsPsuEnabled = True
            self.computer.Open()

            self._create_hardware_fingerprint()

            cached_fingerprint = self.sensor_cache.get('_hardware_fingerprint', '')
            if cached_fingerprint != self.hardware_fingerprint:
                logging.info("Hardware-Konfiguration geändert - Cache wird zurückgesetzt")
                self.sensor_cache = {'_hardware_fingerprint': self.hardware_fingerprint}
                self.cache_updated = True

            self._detect_hardware_with_diagnostics()

            if self.cache_updated:
                save_sensor_cache(self.sensor_cache)
                
            self._log_final_status()
            self.lhm_error = None
            self.lhm_support = True

        except Exception as e:
            self.computer = None
            self.lhm_support = False
            self.lhm_error = f"Fehler bei LHM-Initialisierung: {e}"
            logging.error(f"{self.lhm_error}\n{traceback.format_exc()}")
            self.initialization_log.append(f"FEHLER: {self.lhm_error}")

    def _create_hardware_fingerprint(self):
        """Erstellt einen Fingerprint der aktuellen Hardware-Konfiguration."""
        fingerprint_parts = []
        
        for hw in self.computer.Hardware:
            hw_info = f"{hw.HardwareType}:{hw.Name}:{hw.Identifier}"
            fingerprint_parts.append(hw_info)
        
        self.hardware_fingerprint = "|".join(sorted(fingerprint_parts))
        logging.debug(f"Hardware-Fingerprint erstellt: {len(fingerprint_parts)} Geräte")

    def _detect_hardware_with_diagnostics(self):
        """Erkennt Hardware mit detaillierter Diagnose-Ausgabe."""
        self.initialization_log.append("=== HARDWARE-ERKENNUNG GESTARTET ===")
        
        hardware_count = {'CPU': 0, 'GPU': 0, 'Storage': 0, 'Motherboard': 0, 'Other': 0}
        
        for hw in self.computer.Hardware:
            hw.Update()
            hw_type_str = str(hw.HardwareType)
            hw_type_lower = hw_type_str.lower()
            
            self.initialization_log.append(f"Gefunden: {hw.Name} ({hw_type_str})")
            
            if self._is_cpu_hardware(hw_type_lower):
                hardware_count['CPU'] += 1
                self.cpus.append(hw) # GEÄNDERT: CPU zur Liste hinzufügen
                self.initialization_log.append(f"  CPU erkannt: {hw.Name}")
            elif self._is_gpu_hardware(hw_type_lower):
                hardware_count['GPU'] += 1
                self.gpus.append(hw)
                self.initialization_log.append(f"  GPU erkannt: {hw.Name}")
            elif self._is_storage_hardware(hw_type_lower):
                hardware_count['Storage'] += 1
                self._process_storage_with_diagnostics(hw)
            elif self._is_motherboard_hardware(hw_type_lower):
                hardware_count['Motherboard'] += 1
                self._process_motherboard_with_diagnostics(hw)
            else:
                hardware_count['Other'] += 1
                self.initialization_log.append(f"  Andere Hardware (wird für Explorer bereitgestellt): {hw_type_str}")

        self.hardware_detected = hardware_count
        self.initialization_log.append(f"Hardware-Zusammenfassung: {hardware_count}")

    def _is_cpu_hardware(self, hw_type_lower: str) -> bool:
        """Erweiterte CPU-Erkennung für verschiedene LibreHardwareMonitor-Versionen."""
        cpu_indicators = ['cpu', 'processor', 'amd', 'intel']
        return any(indicator in hw_type_lower for indicator in cpu_indicators)

    def _is_gpu_hardware(self, hw_type_lower: str) -> bool:
        """Erweiterte GPU-Erkennung für verschiedene Hardware-Typen."""
        gpu_indicators = ['gpu', 'graphics', 'nvidia', 'amd', 'radeon', 'geforce', 'quadro']
        return any(indicator in hw_type_lower for indicator in gpu_indicators)

    def _is_storage_hardware(self, hw_type_lower: str) -> bool:
        """Erweiterte Storage-Erkennung."""
        storage_indicators = ['storage', 'hdd', 'ssd', 'nvme', 'm2', 'disk']
        return any(indicator in hw_type_lower for indicator in storage_indicators)
        
    def _is_motherboard_hardware(self, hw_type_lower: str) -> bool:
        """Prüft, ob es sich um ein Mainboard oder einen relevanten Controller handelt."""
        return any(indicator in hw_type_lower for indicator in ['motherboard', 'mainboard', 'controller', 'superio'])

    def _process_motherboard_with_diagnostics(self, mobo_hw):
        """Verarbeitet Mainboard-Hardware, um deren Sensoren für den Explorer verfügbar zu machen."""
        self.initialization_log.append(f"  Mainboard/Controller-Sensoren werden analysiert: {mobo_hw.Name}")
        
        sensor_count = len(get_available_sensors_for_hardware(mobo_hw))
        self.initialization_log.append(f"    {sensor_count} Sensoren gefunden (verfügbar im Explorer).")

    def _process_gpu_with_diagnostics(self, gpu_hw):
        """GPU-Verarbeitung mit detaillierter Diagnose."""
        self.initialization_log.append(f"  GPU-Sensoren suchen für: {gpu_hw.Name}")
        
        available_sensors = get_available_sensors_for_hardware(gpu_hw)
        sensor_types = {}
        for sensor in available_sensors:
            sensor_type = sensor['type']
            if sensor_type not in sensor_types:
                sensor_types[sensor_type] = 0
            sensor_types[sensor_type] += 1
        
        self.initialization_log.append(f"    Verfügbare Sensor-Typen: {sensor_types}")
        
        gpu_sensor_map = {
            'gpu_core_temp': 'GPU_CORE_TEMP', 'gpu_hotspot_temp': 'GPU_HOTSPOT_TEMP', 
            'gpu_memory_temp': 'GPU_MEMORY_TEMP', 'core_clock': 'GPU_CORE_CLOCK',
            'memory_clock': 'GPU_MEMORY_CLOCK', 'power': 'GPU_POWER',
            'vram_used': 'VRAM_USED', 'vram_total': 'VRAM_TOTAL'
        }
        
        temp_gpu_sensors = {}
        found_sensors = []
        failed_sensors = []
        
        for key, canonical_name in gpu_sensor_map.items():
            debug_info = []
            sensor = self._find_or_discover_sensor(
                canonical_name, gpu_hw, 
                hw_id=str(gpu_hw.Identifier),
                debug_info=debug_info
            )
            
            if sensor:
                temp_gpu_sensors[key] = sensor
                found_sensors.append(f"{key}: {sensor.Name}")
            else:
                failed_sensors.append(key)
                self.failed_sensors[f"{gpu_hw.Name}_{canonical_name}"] = {'hardware': gpu_hw.Name, 'sensor_type': canonical_name, 'debug_info': debug_info}
        
        self.initialization_log.append(f"    Gefundene Sensoren: {found_sensors}")
        if failed_sensors:
            self.initialization_log.append(f"    Fehlgeschlagene Sensoren: {failed_sensors}")
        
        if temp_gpu_sensors:
            self.gpu_sensors = temp_gpu_sensors
            self.initialization_log.append(f"  GPU-Sensoren für '{gpu_hw.Name}' aktiviert")

    def _process_storage_with_diagnostics(self, storage_hw):
        """Storage-Verarbeitung mit detaillierter Diagnose."""
        temp_sensors_found = 0
        
        for sensor in storage_hw.Sensors:
            if str(sensor.SensorType) == 'Temperature':
                unique_key = f"{storage_hw.Name.replace(' ', '_')}_{str(sensor.Identifier)}"
                self.storage_sensors[unique_key] = sensor
                self.storage_display_names[unique_key] = f"{storage_hw.Name} ({sensor.Name})"
                temp_sensors_found += 1
        
        self.initialization_log.append(f"  Storage: {storage_hw.Name} - {temp_sensors_found} Temperatur-Sensoren")

    def _find_or_discover_sensor(self, canonical_name, hardware_item, hw_id=None, debug_info=None):
        """Verbesserte Sensor-Suche mit Cache und Fallback."""
        if debug_info is None:
            debug_info = []
            
        cache_key = f"{hw_id}_{canonical_name}" if hw_id else canonical_name
        
        if cached_id := self.sensor_cache.get(cache_key):
            for sensor in hardware_item.Sensors:
                if str(sensor.Identifier) == cached_id:
                    debug_info.append(f"Aus Cache gefunden: {sensor.Name}")
                    return sensor
            debug_info.append(f"Cache-Eintrag ungültig, führe neue Suche durch")
        
        sensor = find_sensor(canonical_name, hardware_item, debug_info)
        
        if sensor:
            self.sensor_cache[cache_key] = str(sensor.Identifier)
            self.cache_updated = True
            debug_info.append("In Cache gespeichert")
            return sensor
        
        return None
    
    # NEUE METHODE
    def update_selected_cpu_sensors(self, selected_cpu_id: str) -> str:
        """Findet die ausgewählte CPU und setzt ihren Temperatur-Sensor als aktiv."""
        self.selected_cpu_id = selected_cpu_id
        target_cpu = None

        if selected_cpu_id == "auto":
            if self.cpus:
                target_cpu = self.cpus[0]
                logging.info(f"Automatische CPU-Auswahl: '{target_cpu.Name}' ausgewählt.")
            else:
                logging.warning("Automatische CPU-Auswahl fehlgeschlagen: Keine CPUs gefunden.")
                self.cpu_sensor = None
                return selected_cpu_id
        else:
            target_cpu = next((cpu for cpu in self.cpus if str(cpu.Identifier) == selected_cpu_id), None)

        if not target_cpu and selected_cpu_id != "auto" and self.cpus:
            logging.warning(f"CPU mit ID '{selected_cpu_id}' nicht gefunden. Fallback auf automatische Auswahl.")
            return self.update_selected_cpu_sensors("auto")

        if not target_cpu:
            logging.warning(f"CPU mit ID '{selected_cpu_id}' nicht gefunden.")
            self.cpu_sensor = None
            return selected_cpu_id

        logging.info(f"Lade Temperatursensor für ausgewählte CPU: {target_cpu.Name}")
        debug_info = []
        self.cpu_sensor = self._find_or_discover_sensor(
            'CPU_PACKAGE_TEMP', target_cpu,
            hw_id=str(target_cpu.Identifier),
            debug_info=debug_info
        )

        if self.cpu_sensor:
            logging.info(f"Aktiver CPU-Temperatursensor gesetzt auf: {self.cpu_sensor.Name}")
        else:
            logging.warning(f"Konnte keinen Temperatur-Sensor für CPU '{target_cpu.Name}' finden.")
            self.failed_sensors['CPU_PACKAGE_TEMP'] = {'hardware': target_cpu.Name, 'debug_info': debug_info}

        if self.cache_updated:
            save_sensor_cache(self.sensor_cache)

        return str(target_cpu.Identifier)

    def update_selected_gpu_sensors(self, selected_gpu_id: str) -> str:
        """Aktualisiert die aktiven GPU-Sensoren für eine spezifische GPU."""
        self.selected_gpu_id = selected_gpu_id
        self.gpu_sensors.clear()
        target_gpu = None
        
        if selected_gpu_id == "auto":
            if self.gpus:
                target_gpu = self.gpus[0]
                logging.info(f"Automatische GPU-Auswahl: '{target_gpu.Name}' ausgewählt.")
            else:
                logging.warning("Automatische GPU-Auswahl fehlgeschlagen: Keine GPUs gefunden.")
                return selected_gpu_id
        else:
            target_gpu = next((gpu for gpu in self.gpus if str(gpu.Identifier) == selected_gpu_id), None)

        if not target_gpu and selected_gpu_id != "auto" and self.gpus:
            logging.warning(f"GPU mit ID '{selected_gpu_id}' nicht gefunden. Fallback auf automatische Auswahl.")
            return self.update_selected_gpu_sensors("auto")

        if not target_gpu:
            logging.warning(f"GPU mit ID '{selected_gpu_id}' nicht gefunden")
            return selected_gpu_id

        logging.info(f"Lade Sensoren für ausgewählte GPU: {target_gpu.Name}")
        self._process_gpu_with_diagnostics(target_gpu)
        
        if self.cache_updated:
            save_sensor_cache(self.sensor_cache)
            
        return str(target_gpu.Identifier)

    def apply_hardware_selection(self, selected_cpu_id: str, selected_gpu_id: str) -> HardwareSelectionState:
        """Aktiviert CPU- und GPU-Auswahl in einem konsistenten Schritt."""
        resolved_cpu_id = self.update_selected_cpu_sensors(selected_cpu_id)
        resolved_gpu_id = self.update_selected_gpu_sensors(selected_gpu_id)
        return HardwareSelectionState(
            cpu_identifier=resolved_cpu_id,
            gpu_identifier=resolved_gpu_id,
        )

    def _set_operation_result(self, success: bool, message: str, **details: Any) -> HardwareOperationResult:
        """Speichert das Ergebnis der letzten Hardware-Lifecycle-Operation."""
        self.last_operation_result = HardwareOperationResult(
            success=success,
            message=message,
            details=details,
        )
        return self.last_operation_result

    def _clear_detected_state(self):
        """Setzt erkannte Hardware und Diagnosezustand zurÃ¼ck."""
        self.cpus.clear()
        self.cpu_sensor = None
        self.gpus.clear()
        self.gpu_sensors.clear()
        self.storage_sensors.clear()
        self.storage_display_names.clear()
        self.initialization_log.clear()
        self.failed_sensors.clear()
        self.hardware_detected.clear()

    def _restore_selected_sensors(self):
        """Aktiviert die zuletzt ausgewÃ¤hlten CPU- und GPU-Sensoren erneut."""
        self.update_selected_cpu_sensors(self.selected_cpu_id)
        self.update_selected_gpu_sensors(self.selected_gpu_id)

    def _log_final_status(self):
        """Erweiterte Status-Ausgabe mit Diagnose-Informationen."""
        logging.info("=" * 60)
        logging.info("HARDWARE MANAGER - INITIALISIERUNG ABGESCHLOSSEN")
        logging.info(f"Hardware erkannt: {self.hardware_detected}")
        logging.info(f"Anzahl CPUs gefunden: {len(self.cpus)}") # GEÄNDERT
        logging.info(f"Aktiver CPU-Sensor geladen: {bool(self.cpu_sensor)}") # GEÄNDERT
        logging.info(f"Anzahl GPUs gefunden: {len(self.gpus)}")
        logging.info(f"Anzahl aktiver GPU-Sensoren: {len(self.gpu_sensors)}")
        logging.info(f"GPU-Unterstützung aktiv: {self.gpu_supported}")
        logging.info(f"Anzahl Storage-Temperatursensoren: {len(self.storage_sensors)}")
        
        if self.failed_sensors:
            logging.warning(f"Anzahl fehlgeschlagener Sensoren: {len(self.failed_sensors)}")
            
        logging.info("=" * 60)

    def _add_hardware_to_report_recursively(self, hw, parts_list, indent_level=0):
        """Hilfsfunktion, die rekursiv Hardware und Sub-Hardware zum Diagnosebericht hinzufügt."""
        indent = "  " * indent_level
        hw.Update()
        parts_list.append(f"\n{indent}=== {hw.Name} ({hw.HardwareType}) ===")
        parts_list.append(f"{indent}Identifier: {hw.Identifier}")
        
        sensors_by_type = {}
        for sensor in hw.Sensors:
            sensor_type = str(sensor.SensorType)
            if sensor_type not in sensors_by_type:
                sensors_by_type[sensor_type] = []
            
            value_str = f"{sensor.Value:.2f}" if sensor.Value is not None else "N/A"
            sensors_by_type[sensor_type].append({'name': sensor.Name, 'value': value_str, 'id': str(sensor.Identifier)})
        
        for sensor_type, sensors in sensors_by_type.items():
            parts_list.append(f"\n{indent}{sensor_type} ({len(sensors)}):")
            for sensor in sensors:
                parts_list.append(f"{indent}  - {sensor['name']}: {sensor['value']} | ID: {sensor['id']}")
        
        # Rekursiver Aufruf für Sub-Hardware
        for sub_hw in hw.SubHardware:
            self._add_hardware_to_report_recursively(sub_hw, parts_list, indent_level + 1)

    def run_sensor_diagnosis(self) -> str:
        """Umfassende Sensor-Diagnose mit detaillierten Informationen, jetzt rekursiv."""
        if not self.computer:
            return "LibreHardwareMonitor ist nicht initialisiert."
        
        diagnosis_parts = [
            "=== ERWEITERTE SENSOR-DIAGNOSE ===",
            f"Hardware-Fingerprint: {self.hardware_fingerprint[:50]}...",
            f"Cache-Einträge: {len(self.sensor_cache)}", ""
        ]
        
        if self.initialization_log:
            diagnosis_parts.append("=== INITIALISIERUNGS-LOG ===")
            diagnosis_parts.extend(self.initialization_log)
            diagnosis_parts.append("")
        
        if self.failed_sensors:
            diagnosis_parts.append("=== FEHLGESCHLAGENE SENSOREN ===")
            for sensor_key, info in self.failed_sensors.items():
                diagnosis_parts.append(f"Sensor: {sensor_key}")
                diagnosis_parts.append(f"Hardware: {info['hardware']}")
                if 'debug_info' in info and info['debug_info']:
                    diagnosis_parts.append("Debug-Informationen:")
                    for debug_line in info['debug_info']:
                        diagnosis_parts.append(f"  {debug_line}")
                diagnosis_parts.append("")
        
        diagnosis_parts.append("=== VOLLSTÄNDIGE HARDWARE-ÜBERSICHT ===")
        for hw in self.computer.Hardware:
            self._add_hardware_to_report_recursively(hw, diagnosis_parts)

        diagnosis_parts.append("\n\n=== CACHE-INFORMATIONEN ===")
        for key, value in self.sensor_cache.items():
            if not key.startswith('_'):
                diagnosis_parts.append(f"{key}: {value}")
        
        return "\n".join(diagnosis_parts)

    def get_available_disks(self) -> list[str]:
        if not PSUTIL_AVAILABLE: 
            return []
        try:
            return sorted(list(psutil.disk_io_counters(perdisk=True).keys()))
        except Exception as e:
            logging.error(f"Fehler beim Abrufen verfügbarer Festplatten: {e}")
            return []

    def get_available_network_interfaces(self) -> list[str]:
        if not PSUTIL_AVAILABLE: 
            return ["all"]
        try:
            return ["all"] + sorted(psutil.net_io_counters(pernic=True).keys())
        except Exception as e:
            logging.error(f"Fehler beim Abrufen verfügbarer Netzwerk-Interfaces: {e}")
            return ["all"]

    def get_available_disk_partitions(self) -> list[str]:
        if not PSUTIL_AVAILABLE: 
            return []
        
        partitions = []
        try:
            for part in psutil.disk_partitions(all=False):
                if 'fixed' in part.opts or part.fstype:
                    try:
                        psutil.disk_usage(part.mountpoint)
                        partitions.append(part.mountpoint)
                    except (PermissionError, OSError):
                        continue
            return sorted(partitions)
        except Exception as e:
            logging.error(f"Fehler beim Abrufen der Festplatten-Partitionen: {e}")
            return []

    def get_detailed_sensor_info(self, hardware_name: str) -> Dict:
        """Detaillierte Sensor-Informationen für spezifische Hardware."""
        if not self.computer:
            return {}
            
        for hw in self.computer.Hardware:
            if hw.Name == hardware_name:
                hw.Update()
                return {
                    'hardware_name': hw.Name,
                    'hardware_type': str(hw.HardwareType),
                    'identifier': str(hw.Identifier),
                    'sensors': get_available_sensors_for_hardware(hw),
                    'sensor_count': len(list(hw.Sensors))
                }
        return {}

    def test_sensor_recognition(self, canonical_name: str, hardware_name: str) -> str:
        """Testet die Sensor-Erkennung für spezifische Hardware."""
        if not self.computer:
            return "LibreHardwareMonitor nicht verfügbar"
            
        for hw in self.computer.Hardware:
            if hw.Name == hardware_name:
                return diagnose_sensor_matching(canonical_name, hw)
                
        return f"Hardware '{hardware_name}' nicht gefunden"

    def redetect_hardware(self, reset_cache: bool = False) -> HardwareOperationResult:
        """FÃ¼hrt eine neue Hardware-Erkennung aus und liefert ein strukturiertes Ergebnis."""
        if not self.computer:
            message = "Aktualisierung nicht mÃ¶glich, LHM Computer nicht initialisiert."
            logging.error(message)
            return self._set_operation_result(False, message, reset_cache=reset_cache)

        try:
            if reset_cache:
                old_fingerprint = self.sensor_cache.get('_hardware_fingerprint', '')
                self.sensor_cache = {'_hardware_fingerprint': old_fingerprint}
                self.cache_updated = False
                logging.info("Sensor-Cache wird zurÃ¼ckgesetzt und Hardware neu erkannt.")
            else:
                logging.info("Aktualisiere Hardware- und Sensor-Erkennung...")

            self._clear_detected_state()
            self._detect_hardware_with_diagnostics()
            self._restore_selected_sensors()

            if reset_cache or self.cache_updated:
                save_sensor_cache(self.sensor_cache)
                self.cache_updated = False

            self._log_final_status()
            message = (
                "Sensor-Cache zurÃ¼ckgesetzt und Hardware neu erkannt."
                if reset_cache else
                "Hardware-Konfiguration wurde aktualisiert."
            )
            return self._set_operation_result(
                True,
                message,
                reset_cache=reset_cache,
                hardware_detected=dict(self.hardware_detected),
            )
        except Exception as e:
            message = (
                f"Fehler beim ZurÃ¼cksetzen des Sensor-Cache: {e}"
                if reset_cache else
                f"Fehler bei der Hardware-Aktualisierung: {e}"
            )
            logging.exception(message)
            return self._set_operation_result(False, message, reset_cache=reset_cache)

    def reset_sensor_cache(self) -> bool:
        """Setzt den Sensor-Cache zur?ck und f?hrt neue Erkennung durch."""
        return self.redetect_hardware(reset_cache=True).success

    def refresh_hardware_detection(self):
        """F?hrt eine neue Hardware-Erkennung durch, ohne den Cache zu l?schen."""
        return self.redetect_hardware(reset_cache=False).success

    def test_custom_sensor(self, identifier: str) -> Optional[float]:
        """Testet einen einzelnen Sensor anhand seines Identifiers und gibt den Wert zurück."""
        if not self.computer:
            return None
        
        try:
            for hw in self.computer.Hardware:
                hw.Update()
                for sensor in hw.Sensors:
                    if str(sensor.Identifier) == identifier:
                        if hasattr(sensor, 'Value') and sensor.Value is not None:
                            return float(sensor.Value)
                        else:
                            return None
            return None
        except Exception as e:
            logging.error(f"Fehler beim Testen des Custom Sensors '{identifier}': {e}")
            return None
