# monitoring/history_manager.py
import gc
import logging
import sqlite3
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from config.constants import SettingsKey

if TYPE_CHECKING:
    from core.app_context import AppContext
    from utils.settings_manager import SettingsManager


GRAPHABLE_METRICS_MAP = {
    "cpu": "cpu_percent",
    "cpu_temp": "cpu_temp",
    "ram": "ram_percent",
    "disk": "disk_percent",
    "gpu": "gpu_core_temp",
    "gpu_hotspot": "gpu_hotspot_temp",
    "gpu_memory_temp": "gpu_memory_temp",
    "gpu_vram": "vram_percent",
    "gpu_core_clock": "gpu_core_clock",
    "gpu_memory_clock": "gpu_memory_clock",
    "gpu_power": "gpu_power",
    "disk_read": "disk_read_mbps",
    "disk_write": "disk_write_mbps",
    "net_upload": "net_up_mbps",
    "net_download": "net_down_mbps",
}


class HistoryManager(QObject):
    DB_NAME = "monitoring_history.db"
    PRUNE_INTERVAL_SEC = 300
    MAIN_CONNECTION_BUSY_TIMEOUT_MS = 250
    PRUNE_CONNECTION_BUSY_TIMEOUT_MS = 3000
    database_corrupt = Signal()

    def __init__(
        self,
        settings_manager: "SettingsManager",
        config_dir: Path,
        context: "AppContext",
    ):
        super().__init__()
        self.settings_manager = settings_manager
        self.context = context
        self.db_path = config_dir / self.DB_NAME
        self.conn: Optional[sqlite3.Connection] = None
        self.pending_database_recovery = False
        self._last_prune_time = 0.0
        self._prune_lock = threading.Lock()
        self._prune_executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="HistoryPrune",
        )
        self._prune_task_running = False
        self._queued_prune_request: Optional[Dict[str, object]] = None
        self._prune_idle_event = threading.Event()
        self._prune_idle_event.set()
        self._is_shutting_down = False

        self._load_settings()
        self._setup_database()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._collect_data_point)

        if self.monitoring_enabled:
            self.start_monitoring()

    def has_pending_database_recovery(self) -> bool:
        """Returns whether the DB needs user-confirmed recovery."""
        return self.pending_database_recovery

    def consume_database_recovery_request(self) -> bool:
        """Marks a pending recovery request as processed."""
        was_pending = self.pending_database_recovery
        self.pending_database_recovery = False
        return was_pending

    def _load_settings(self):
        self.monitoring_enabled = self.settings_manager.get_setting(
            SettingsKey.MONITORING_ENABLED.value, False
        )
        self.interval_sec = self.settings_manager.get_setting(
            SettingsKey.MONITORING_INTERVAL_SEC.value, 60
        )
        self.max_duration_hours = self.settings_manager.get_setting(
            SettingsKey.MONITORING_MAX_DURATION_HOURS.value, 24
        )
        self.max_file_size_mb = self.settings_manager.get_setting(
            SettingsKey.MONITORING_MAX_FILE_SIZE_MB.value, 100
        )

    def _setup_database(self):
        """Connects to the DB and creates the schema when needed."""
        try:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.execute(
                f"PRAGMA busy_timeout = {self.MAIN_CONNECTION_BUSY_TIMEOUT_MS};"
            )
            self.conn.execute("PRAGMA journal_mode = WAL;")
            cursor = self.conn.cursor()
            cursor.execute("PRAGMA integrity_check;")
            if cursor.fetchone()[0] != "ok":
                raise sqlite3.DatabaseError("Database integrity check failed.")

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS history (
                    timestamp REAL,
                    metric_key TEXT,
                    value REAL,
                    PRIMARY KEY (timestamp, metric_key)
                )
                """
            )
            cursor.execute(
                "CREATE INDEX IF NOT EXISTS idx_metric_key_timestamp "
                "ON history (metric_key, timestamp);"
            )
            self.conn.commit()
            self.pending_database_recovery = False
            logging.info(f"Monitoring DB connected: '{self.db_path}'.")
        except sqlite3.DatabaseError as e:
            logging.error(f"Failed to initialize monitoring DB: {e}")
            if self.conn:
                self.conn.close()
            self.conn = None
            self.pending_database_recovery = True
            self.database_corrupt.emit()
        except sqlite3.Error as e:
            logging.error(f"Unexpected SQLite error: {e}")
            self.conn = None

    def recreate_database(self) -> bool:
        """Deletes the old DB file and creates a fresh one."""
        logging.warning(f"Recreating monitoring DB: {self.db_path}")
        self._wait_for_prune_completion()
        with self._prune_lock:
            self._queued_prune_request = None
            self._last_prune_time = 0.0

        self._close_connection()

        try:
            self.db_path.unlink(missing_ok=True)
            self._setup_database()
            self.pending_database_recovery = self.conn is None
            self._last_prune_time = 0.0
            return self.conn is not None
        except OSError as e:
            logging.error(f"Could not delete corrupt DB file: {e}")
            return False

    def start_monitoring(self):
        if not self.conn or self.timer.isActive():
            return
        self.monitoring_enabled = True
        self.timer.start(self.interval_sec * 1000)
        logging.info(f"Monitoring history started (interval: {self.interval_sec}s).")

    def stop_monitoring(self):
        self.monitoring_enabled = False
        self.timer.stop()
        logging.info("Monitoring history stopped.")

    def set_interval(self, seconds: int):
        self.interval_sec = max(1, seconds)
        if self.timer.isActive():
            self.timer.setInterval(self.interval_sec * 1000)
        logging.info(f"Monitoring interval set to {self.interval_sec}s.")

    def set_max_duration(self, hours: int):
        self.max_duration_hours = max(1, hours)
        self._request_prune(force=True)
        logging.info(f"Maximum history duration set to {self.max_duration_hours}h.")

    def set_max_file_size(self, mb: int):
        self.max_file_size_mb = max(1, mb)
        self._request_prune(force=True)
        logging.info(f"Maximum history file size set to {self.max_file_size_mb}MB.")

    def _append_numeric_record(
        self,
        records: List[Tuple[float, str, float]],
        timestamp: float,
        metric_key: Optional[str],
        value,
    ):
        if not metric_key or value is None:
            return
        try:
            records.append((timestamp, metric_key, float(value)))
        except (TypeError, ValueError):
            logging.debug(
                "Skipping invalid monitoring history value for %s: %r",
                metric_key,
                value,
            )

    @Slot()
    def _collect_data_point(self):
        if not self.conn:
            return

        last_data = self.context.get_latest_monitor_data()
        if not last_data:
            return

        timestamp = time.time()
        records: List[Tuple[float, str, float]] = []

        for metric_key, raw_key in GRAPHABLE_METRICS_MAP.items():
            self._append_numeric_record(records, timestamp, metric_key, last_data.get(raw_key))

        for item in last_data.get("storage_temps", []):
            if not isinstance(item, dict):
                continue
            storage_key = item.get("key")
            self._append_numeric_record(
                records,
                timestamp,
                f"storage_temp_{storage_key}" if storage_key else None,
                item.get("temp"),
            )

        custom_sensor_configs = self.settings_manager.get_setting(
            SettingsKey.CUSTOM_SENSORS.value, {}
        )
        id_to_key_map: Dict[str, str] = {}
        for sensor_id, config in custom_sensor_configs.items():
            if not isinstance(config, dict) or not config.get("enabled", True):
                continue
            identifier = config.get("identifier")
            if identifier:
                id_to_key_map[identifier] = f"custom_{sensor_id}"

        for identifier, value in last_data.get("custom_sensors", {}).items():
            self._append_numeric_record(
                records,
                timestamp,
                id_to_key_map.get(identifier),
                value,
            )

        if not records:
            return

        try:
            cursor = self.conn.cursor()
            cursor.executemany(
                "INSERT OR IGNORE INTO history (timestamp, metric_key, value) "
                "VALUES (?, ?, ?)",
                records,
            )
            self.conn.commit()
            self._request_prune(now=timestamp)
        except sqlite3.Error as e:
            logging.error(f"Failed to write monitoring history data: {e}")

    def _request_prune(self, now: Optional[float] = None, force: bool = False):
        if not self.conn:
            return

        prune_time = now if now is not None else time.time()
        request = {
            "prune_time": prune_time,
            "max_duration_hours": self.max_duration_hours,
            "max_file_size_mb": self.max_file_size_mb,
            "force": force,
        }

        with self._prune_lock:
            if self._is_shutting_down:
                return
            if (
                not self._prune_task_running
                and not force
                and (prune_time - self._last_prune_time) < self.PRUNE_INTERVAL_SEC
            ):
                return

            queued_request = self._queued_prune_request
            if queued_request is None:
                self._queued_prune_request = request
            else:
                self._queued_prune_request = {
                    "prune_time": max(
                        prune_time,
                        float(queued_request["prune_time"]),
                    ),
                    "max_duration_hours": self.max_duration_hours,
                    "max_file_size_mb": self.max_file_size_mb,
                    "force": bool(queued_request["force"]) or force,
                }

            if self._prune_task_running:
                return

            self._prune_task_running = True
            self._prune_idle_event.clear()

        self._prune_executor.submit(self._drain_prune_queue)

    def _drain_prune_queue(self):
        try:
            while True:
                with self._prune_lock:
                    if self._is_shutting_down:
                        self._prune_task_running = False
                        self._prune_idle_event.set()
                        return

                    request = self._queued_prune_request
                    self._queued_prune_request = None
                    if request is None:
                        self._prune_task_running = False
                        self._prune_idle_event.set()
                        return

                self._prune_database_sync(
                    prune_time=float(request["prune_time"]),
                    max_duration_hours=int(request["max_duration_hours"]),
                    max_file_size_mb=int(request["max_file_size_mb"]),
                    force=bool(request["force"]),
                )
        except Exception:
            logging.exception("Unexpected error in monitoring history prune worker.")
            with self._prune_lock:
                self._prune_task_running = False
                self._prune_idle_event.set()

    def _prune_database_sync(
        self,
        prune_time: float,
        max_duration_hours: int,
        max_file_size_mb: int,
        force: bool = False,
    ):
        with self._prune_lock:
            if (
                not force
                and (prune_time - self._last_prune_time) < self.PRUNE_INTERVAL_SEC
            ):
                return

        if not self.db_path.exists():
            return

        prune_conn: Optional[sqlite3.Connection] = None
        try:
            prune_conn = sqlite3.connect(self.db_path)
            prune_conn.execute(
                f"PRAGMA busy_timeout = {self.PRUNE_CONNECTION_BUSY_TIMEOUT_MS};"
            )
            prune_conn.execute("PRAGMA journal_mode = WAL;")
            cursor = prune_conn.cursor()
            cutoff_time = prune_time - (max_duration_hours * 3600)
            cursor.execute("DELETE FROM history WHERE timestamp < ?", (cutoff_time,))
            prune_conn.commit()

            file_size_mb = self.db_path.stat().st_size / (1024 * 1024)
            if file_size_mb > max_file_size_mb:
                logging.info(
                    "Monitoring DB size %.1fMB exceeds limit %.1fMB, pruning oldest rows.",
                    file_size_mb,
                    max_file_size_mb,
                )
                cursor.execute(
                    "DELETE FROM history WHERE timestamp IN ("
                    "SELECT timestamp FROM history ORDER BY timestamp ASC LIMIT ("
                    "SELECT CAST(COUNT(*) * 0.1 AS INTEGER) FROM history"
                    "))"
                )
                prune_conn.commit()
                prune_conn.execute("VACUUM")

            with self._prune_lock:
                self._last_prune_time = prune_time
        except (sqlite3.Error, FileNotFoundError, OSError) as e:
            logging.error(f"Failed to prune monitoring history DB: {e}")
        finally:
            if prune_conn is not None:
                prune_conn.close()

    def _wait_for_prune_completion(self, timeout_sec: float = 5.0) -> bool:
        return self._prune_idle_event.wait(timeout=timeout_sec)

    def shutdown(self, wait: bool = True):
        self.stop_monitoring()
        with self._prune_lock:
            if self._is_shutting_down:
                return
            self._is_shutting_down = True
            self._queued_prune_request = None

        if wait:
            self._wait_for_prune_completion()

        self._prune_executor.shutdown(wait=wait, cancel_futures=not wait)
        self._close_connection()

    def _close_connection(self):
        if not self.conn:
            return

        conn = self.conn
        self.conn = None
        try:
            conn.close()
        finally:
            del conn
            gc.collect()

    def get_data_for_metrics(
        self,
        metric_keys: List[str],
        hours_ago: Optional[int] = 1,
    ) -> Dict[str, List[Tuple[float, float]]]:
        if not self.conn or not metric_keys:
            return {}

        data = {key: [] for key in metric_keys}
        try:
            cursor = self.conn.cursor()
            placeholders = ",".join("?" for _ in metric_keys)
            query = (
                f"SELECT timestamp, metric_key, value FROM history "
                f"WHERE metric_key IN ({placeholders})"
            )
            params = list(metric_keys)
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
            logging.error(f"Failed to read monitoring history data: {e}")
            return {}

    def get_session_stats(
        self,
        metric_key: str,
        hours_ago: Optional[int] = None,
    ) -> Dict[str, Optional[float]]:
        if not self.conn:
            return {"min": None, "max": None, "avg": None}

        try:
            cursor = self.conn.cursor()
            query = "SELECT MIN(value), MAX(value), AVG(value) FROM history WHERE metric_key = ?"
            params: List[object] = [metric_key]
            if hours_ago is not None:
                cutoff_time = time.time() - (hours_ago * 3600)
                query += " AND timestamp >= ?"
                params.append(cutoff_time)
            cursor.execute(query, params)
            result = cursor.fetchone()
            if not result:
                return {"min": None, "max": None, "avg": None}
            return {"min": result[0], "max": result[1], "avg": result[2]}
        except sqlite3.Error:
            return {"min": None, "max": None, "avg": None}
