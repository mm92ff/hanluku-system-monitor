# monitoring/hardware_monitor.py
import time
import logging
from typing import Dict, Any, TYPE_CHECKING

from PySide6.QtCore import QObject, Signal, Slot

from monitoring.io_calculator import IOCalculator
from monitoring.system_data_collector import SystemDataCollector
from monitoring.sensor_manager import SensorManager
from monitoring.performance_tracker import PerformanceTracker

if TYPE_CHECKING:
    from core.app_context import AppContext


class HardwareMonitorWorker(QObject):
    """
    Worker-Klasse, die in einem separaten Thread läuft, um Hardware-Daten
    zu sammeln, ohne die UI zu blockieren.
    """
    data_updated = Signal(dict)
    sensor_error = Signal(str, str)
    memory_warning = Signal(dict, float)

    def __init__(self, context: "AppContext", interval_ms: int):
        super().__init__()
        self.context = context
        self.settings = context.get_settings()
        
        self._is_running = True
        self.sleep_duration_sec = interval_ms / 1000.0
        
        # Manager-Instanzen aus dem Kontext holen
        self.lhm_support = context.hardware_manager.lhm_support
        self.sensor_manager = SensorManager(context.hardware_manager, self.settings)
        self.system_collector = SystemDataCollector(self.settings)
        self.io_calculator = IOCalculator(self.settings)
        # KORREKTUR: Übergibt den SettingsManager, damit der Tracker speichern kann
        self.performance_tracker = PerformanceTracker(context.settings_manager)
        
        self.consecutive_errors = 0
        self.max_consecutive_errors = 5
        self.performance_log_interval = 100
        
        logging.info(f"HardwareMonitorWorker initialisiert - LHM: {self.lhm_support}, Intervall: {self.sleep_duration_sec}s")

    @Slot(str, object)
    def update_setting(self, key: str, value: Any):
        """Aktualisiert Einstellungen in allen relevanten Managern."""
        self.settings[key] = value
        
        # Propagiere die Einstellung an alle Manager
        self.sensor_manager.update_settings(key, value)
        self.system_collector.update_settings(key, value)
        self.io_calculator.update_settings(key, value)
        self.performance_tracker.update_settings(key, value)
        
        if key == 'update_interval_ms':
            self.sleep_duration_sec = value / 1000.0

    def run(self):
        """Die Hauptschleife des Worker-Threads."""
        logging.info("Hardware Monitor Worker startet...")
        
        prev_time = time.time()

        while self._is_running:
            start_time = time.time()
            try:
                current_time = time.time()
                elapsed = max(0.1, current_time - prev_time)
                prev_time = current_time

                all_data = {}

                all_data.update(self.system_collector.collect_all())
                all_data.update(self.io_calculator.calculate_all(elapsed))
                
                if self.lhm_support:
                    all_data.update(self.sensor_manager.read_all_sensors())
                
                self.data_updated.emit(all_data)
                self.consecutive_errors = 0
                
                # Performance und Speicher überwachen
                self.performance_tracker.track_update_performance(time.time() - start_time)
                if memory_mb := self.performance_tracker.check_memory_usage():
                    for warning in self.performance_tracker.get_recent_memory_warnings(5):
                        self.memory_warning.emit(warning, memory_mb)
                
                stats = self.performance_tracker.get_performance_stats()
                if stats['update_count'] > 0 and stats['update_count'] % self.performance_log_interval == 0:
                    logging.info(f"Performance: Avg={stats['avg_update_time_ms']:.1f}ms, Max={stats['max_update_time_ms']:.1f}ms")
                    
                time.sleep(max(0, self.sleep_duration_sec - (time.time() - start_time)))

            except Exception:
                self.consecutive_errors += 1
                logging.exception(f"Fehler in Worker-Schleife (Fehler #{self.consecutive_errors})")
                if self.consecutive_errors >= self.max_consecutive_errors:
                    logging.critical("Maximale Anzahl aufeinanderfolgender Fehler erreicht. Worker wird gestoppt.")
                    self.sensor_error.emit("Kritisch", "Worker wegen wiederholter Fehler gestoppt.")
                    self._is_running = False
                time.sleep(2.0)
        
        logging.info("Hardware Monitor Worker beendet.")

    def stop(self):
        """Stoppt den Worker sicher."""
        self._is_running = False

    def get_health_report(self) -> Dict[str, Any]:
        """Sammelt Gesundheitsberichte von allen Managern."""
        return {
            'worker_status': {
                'is_running': self._is_running,
                'consecutive_errors': self.consecutive_errors,
            },
            'performance_tracker': self.performance_tracker.get_health_report(),
            'sensor_manager': self.sensor_manager.get_sensor_health_report(),
        }