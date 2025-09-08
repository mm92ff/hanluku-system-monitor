# monitoring/history_manager.py
import sqlite3
import time
import logging
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional, TYPE_CHECKING

from PySide6.QtCore import QObject, QTimer, Slot, Signal

from config.constants import SettingsKey

if TYPE_CHECKING:
    from utils.settings_manager import SettingsManager
    from core.app_context import AppContext

GRAPHABLE_METRICS_MAP = {
    'cpu': 'cpu_percent',
    'cpu_temp': 'cpu_temp',
    'ram': 'ram_percent',
    'disk': 'disk_percent',
    'gpu': 'gpu_core_temp',
    'gpu_hotspot': 'gpu_hotspot_temp',
    'gpu_memory_temp': 'gpu_memory_temp',
    'gpu_vram': 'vram_percent',
    'gpu_core_clock': 'gpu_core_clock',
    'gpu_memory_clock': 'gpu_memory_clock',
    'gpu_power': 'gpu_power',
    'disk_read': 'disk_read_mbps',
    'disk_write': 'disk_write_mbps',
    'net_upload': 'net_up_mbps',
    'net_download': 'net_down_mbps'
}

class HistoryManager(QObject):
    DB_NAME = "monitoring_history.db"
    database_corrupt = Signal() # NEUES SIGNAL

    def __init__(self, settings_manager: "SettingsManager", config_dir: Path, context: "AppContext"):
        super().__init__()
        self.settings_manager = settings_manager
        self.context = context
        self.db_path = config_dir / self.DB_NAME
        self.conn: Optional[sqlite3.Connection] = None
        
        self._load_settings()
        self._setup_database()
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._collect_data_point)

        if self.monitoring_enabled:
            self.start_monitoring()

    def _load_settings(self):
        self.monitoring_enabled = self.settings_manager.get_setting(SettingsKey.MONITORING_ENABLED.value, False)
        self.interval_sec = self.settings_manager.get_setting(SettingsKey.MONITORING_INTERVAL_SEC.value, 60)
        self.max_duration_hours = self.settings_manager.get_setting(SettingsKey.MONITORING_MAX_DURATION_HOURS.value, 24)
        self.max_file_size_mb = self.settings_manager.get_setting(SettingsKey.MONITORING_MAX_FILE_SIZE_MB.value, 100)

    def _setup_database(self):
        """Stellt die Verbindung zur DB her und erstellt die Tabelle, falls nötig."""
        try:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            cursor = self.conn.cursor()
            cursor.execute("PRAGMA integrity_check;")
            if cursor.fetchone()[0] != 'ok':
                raise sqlite3.DatabaseError("Database integrity check failed.")
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS history (
                    timestamp REAL,
                    metric_key TEXT,
                    value REAL,
                    PRIMARY KEY (timestamp, metric_key)
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_metric_key_timestamp ON history (metric_key, timestamp);")
            self.conn.commit()
            logging.info(f"Datenbank für Monitoring unter '{self.db_path}' erfolgreich verbunden.")
        except sqlite3.DatabaseError as e:
            logging.error(f"Fehler bei der Initialisierung der Monitoring-DB: {e}")
            if self.conn:
                self.conn.close()
            self.conn = None
            self.database_corrupt.emit() # Signal bei Fehler senden
        except sqlite3.Error as e:
            logging.error(f"Unerwarteter SQLite-Fehler: {e}")
            self.conn = None

    def recreate_database(self) -> bool:
        """Löscht die alte DB-Datei und erstellt eine neue, leere."""
        logging.warning(f"Erstelle Monitoring-Datenbank neu: {self.db_path}")
        if self.conn:
            self.conn.close()
            self.conn = None
        
        try:
            self.db_path.unlink(missing_ok=True)
            self._setup_database()
            # Prüfen, ob die neue Verbindung erfolgreich war
            return self.conn is not None
        except OSError as e:
            logging.error(f"Konnte defekte DB-Datei nicht löschen: {e}")
            return False

    def start_monitoring(self):
        if not self.conn or self.timer.isActive(): return
        self.monitoring_enabled = True
        self.timer.start(self.interval_sec * 1000)
        logging.info(f"Monitoring-Datensammlung gestartet (Intervall: {self.interval_sec}s).")

    def stop_monitoring(self):
        self.monitoring_enabled = False
        self.timer.stop()
        logging.info("Monitoring-Datensammlung gestoppt.")
    
    def set_interval(self, seconds: int):
        self.interval_sec = max(1, seconds)
        if self.timer.isActive(): self.timer.setInterval(self.interval_sec * 1000)
        logging.info(f"Monitoring-Intervall auf {self.interval_sec}s gesetzt.")

    def set_max_duration(self, hours: int):
        self.max_duration_hours = hours
        logging.info(f"Maximale Speicherdauer auf {hours}h gesetzt.")

    def set_max_file_size(self, mb: int):
        self.max_file_size_mb = mb
        logging.info(f"Maximale Dateigröße auf {mb}MB gesetzt.")

    @Slot()
    def _collect_data_point(self):
        if not self.conn or not hasattr(self.context, 'main_win'): return
        last_data = self.context.main_win.last_data
        if not last_data: return

        timestamp = time.time()
        records = []

        for metric_key, raw_key in GRAPHABLE_METRICS_MAP.items():
            if raw_key in last_data and last_data[raw_key] is not None:
                records.append((timestamp, metric_key, float(last_data[raw_key])))

        if 'storage_temps' in last_data:
            for item in last_data.get('storage_temps', []):
                records.append((timestamp, f"storage_temp_{item['key']}", item['temp']))

        if 'custom_sensors' in last_data:
            id_to_key_map = {
                config['identifier']: f"custom_{sensor_id}"
                for sensor_id, config in self.settings_manager.get_setting(SettingsKey.CUSTOM_SENSORS.value, {}).items()
                if config.get('enabled', True)
            }
            for identifier, value in last_data.get('custom_sensors', {}).items():
                if metric_key := id_to_key_map.get(identifier):
                    records.append((timestamp, metric_key, float(value)))
        
        if not records: return
        try:
            cursor = self.conn.cursor()
            cursor.executemany("INSERT OR IGNORE INTO history (timestamp, metric_key, value) VALUES (?, ?, ?)", records)
            self.conn.commit()
            self._prune_database()
        except sqlite3.Error as e:
            logging.error(f"Fehler beim Schreiben in die Monitoring-DB: {e}")

    def _prune_database(self):
        if not self.conn: return
        try:
            cursor = self.conn.cursor()
            cutoff_time = time.time() - (self.max_duration_hours * 3600)
            cursor.execute("DELETE FROM history WHERE timestamp < ?", (cutoff_time,))
            self.conn.commit()
            
            file_size_mb = self.db_path.stat().st_size / (1024 * 1024)
            if file_size_mb > self.max_file_size_mb:
                logging.info(f"DB-Größe ({file_size_mb:.1f}MB) überschreitet Limit ({self.max_file_size_mb}MB), bereinige...")
                cursor.execute("DELETE FROM history WHERE timestamp IN (SELECT timestamp FROM history ORDER BY timestamp ASC LIMIT (SELECT CAST(COUNT(*) * 0.1 AS INTEGER) FROM history))")
                self.conn.commit()
                self.conn.execute("VACUUM")
        except (sqlite3.Error, FileNotFoundError) as e:
            logging.error(f"Fehler bei der DB-Bereinigung: {e}")

    def get_data_for_metrics(self, metric_keys: List[str], hours_ago: Optional[int] = 1) -> Dict[str, List[Tuple[float, float]]]:
        if not self.conn or not metric_keys: return {}
        data = {key: [] for key in metric_keys}
        try:
            cursor = self.conn.cursor()
            placeholders = ','.join('?' for _ in metric_keys)
            query = f"SELECT timestamp, metric_key, value FROM history WHERE metric_key IN ({placeholders})"
            params = metric_keys
            if hours_ago is not None:
                cutoff_time = time.time() - (hours_ago * 3600)
                query += " AND timestamp >= ?"
                params.append(cutoff_time)
            query += " ORDER BY timestamp ASC"
            cursor.execute(query, params)
            for timestamp, key, value in cursor.fetchall():
                data[key].append((timestamp, value))
            return data
        except sqlite3.Error as e:
            logging.error(f"Fehler beim Abrufen der Verlaufsdaten: {e}")
            return {}

    def get_session_stats(self, metric_key: str) -> Dict[str, Optional[float]]:
        if not self.conn: return {'min': None, 'max': None, 'avg': None}
        try:
            cursor = self.conn.cursor()
            query = "SELECT MIN(value), MAX(value), AVG(value) FROM history WHERE metric_key = ?"
            cursor.execute(query, (metric_key,))
            result = cursor.fetchone()
            return {'min': result[0], 'max': result[1], 'avg': result[2]}
        except sqlite3.Error:
            return {'min': None, 'max': None, 'avg': None}