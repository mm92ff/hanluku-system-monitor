# core/main_window.py
from __future__ import annotations
import sys
import logging
import subprocess
from typing import Dict, Any, Optional, TYPE_CHECKING

from PySide6.QtCore import QThread, Slot
from PySide6.QtWidgets import QMainWindow, QApplication, QMessageBox

from config.constants import SettingsKey
from monitoring.hardware_monitor import HardwareMonitorWorker
from ui.ui_manager import UIManager
from tray.action_handler import ActionHandler
from tray.tray_icon_manager import TrayIconManager
from detachable.detachable_manager import DetachableManager

if TYPE_CHECKING:
    from core.app_context import AppContext


class SystemMonitor(QMainWindow):
    """
    Hauptfenster-Klasse, die als Orchestrator für die UI und den Worker-Thread dient.
    Erhält alle Abhängigkeiten über den AppContext.
    """
    THREAD_TERMINATION_TIMEOUT_MS = 5000

    def __init__(self, context: AppContext):
        super().__init__()
        self.context = context
        self.context.main_win = self
        self.settings_manager = context.settings_manager
        self.translator = context.translator
        self.hw_manager = context.hardware_manager
        self.history_manager = context.history_manager
        
        self.last_data: Dict[str, Any] = {}
        self.thread: Optional[QThread] = None
        self.worker: Optional[HardwareMonitorWorker] = None

        logging.info("=== SystemMonitor UI wird initialisiert ===")

        self.action_handler = ActionHandler(self)
        self.ui_manager = UIManager(self)
        self.detachable_manager = DetachableManager(self, context.monitor_manager)
        self.tray_icon_manager = TrayIconManager(self)

        # Signale verbinden
        self.context.data_handler.metric_updated.connect(self.detachable_manager.update_widget_display)
        self.context.data_handler.alarm_state_changed.connect(self.tray_icon_manager.update_alarm_state)
        self.settings_manager.setting_changed.connect(self.on_setting_changed)
        self.history_manager.database_corrupt.connect(self.handle_corrupt_database) # NEU

        self.detachable_manager.start_detached_mode()
        self.init_worker_thread()
        logging.info("=== SystemMonitor ist bereit ===")

    @Slot()
    def handle_corrupt_database(self):
        """Zeigt einen Dialog an, wenn die Monitoring-DB korrupt ist."""
        msg_box = QMessageBox(self)
        msg_box.setIcon(QMessageBox.Icon.Warning)
        msg_box.setWindowTitle(self.translator.translate("dlg_db_corrupt_title"))
        msg_box.setText(self.translator.translate("dlg_db_corrupt_text"))
        msg_box.setInformativeText(self.translator.translate("dlg_db_corrupt_info"))
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        msg_box.setDefaultButton(QMessageBox.StandardButton.Yes)
        
        if msg_box.exec() == QMessageBox.StandardButton.Yes:
            if self.history_manager.recreate_database():
                QMessageBox.information(self, self.translator.translate("dlg_db_recreated_title"),
                                        self.translator.translate("dlg_db_recreated_text"))
            else:
                QMessageBox.critical(self, self.translator.translate("shared_error_title"),
                                     self.translator.translate("dlg_db_recreate_failed_text"))

    @Slot(dict)
    def on_data_updated(self, data: dict):
        """Empfängt Daten vom Worker, speichert sie und leitet sie weiter."""
        self.last_data = data
        self.context.data_handler.process_new_data(data)
        
    def on_setting_changed(self, key: str, value: Any):
        """Reagiert auf globale Einstellungsänderungen."""
        if self.worker:
            self.worker.update_setting(key, value)
        
        if key == SettingsKey.UPDATE_INTERVAL_MS.value:
            self.restart_worker_thread()
            
    def init_worker_thread(self):
        """Initialisiert und startet den Worker-Thread."""
        if self.thread and self.thread.isRunning():
            self._stop_worker_thread()

        interval = self.settings_manager.get_setting(SettingsKey.UPDATE_INTERVAL_MS.value, 2000)

        self.thread = QThread()
        self.worker = HardwareMonitorWorker(self.context, interval)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.worker.data_updated.connect(self.on_data_updated)
        self.worker.sensor_error.connect(self.handle_sensor_error)
        self.worker.memory_warning.connect(self.handle_memory_warning)

        self.thread.start()
        logging.info(f"Worker-Thread gestartet (Intervall: {interval}ms)")

    def restart_worker_thread(self):
        """Startet den Worker-Thread sicher neu."""
        logging.info("Worker-Thread wird neugestartet...")
        self._stop_worker_thread()
        self.init_worker_thread()

    def _stop_worker_thread(self):
        """Stoppt den Worker-Thread sicher."""
        if not self.thread or not self.worker: return
        
        try:
            self.worker.stop()
            self.thread.quit()
            if not self.thread.wait(self.THREAD_TERMINATION_TIMEOUT_MS):
                logging.warning("Thread-Timeout erreicht, forciere Beendigung")
                self.thread.terminate()
                self.thread.wait(1000)
            logging.debug("Worker-Thread erfolgreich gestoppt")
        except Exception:
            logging.exception("Fehler beim Stoppen des Worker-Threads.")
        finally:
            self.thread, self.worker = None, None

    def handle_sensor_error(self, sensor_type: str, message: str):
        """Zeigt eine Sensor-Fehlermeldung im Tray an."""
        title = self.translator.translate("lhm_error_title")
        self.tray_icon_manager.tray_icon.showMessage(title, message, self.tray_icon_manager.tray_icon.MessageIcon.Warning, 5000)
        logging.warning(f"Sensor-Fehler ({sensor_type}): {message}")

    def handle_memory_warning(self, warning_data: dict, current_memory_mb: float):
        """Zeigt eine Speicher-Warnung im Tray an."""
        key = warning_data.get("key", "perf_warning_unknown")
        kwargs = warning_data.get("kwargs", {})
        
        warning_message = self.translator.translate(key, **kwargs)
        
        details = self.translator.translate("tray_warning_memory_details", mem_mb=f"{current_memory_mb:.1f}")
        full_message = f"{warning_message}\n{details}"
        
        logging.warning(f"{self.translator.translate('tray_warning_memory_title')}: {full_message}")
        
        if not self.settings_manager.get_setting(SettingsKey.PERF_SHOW_WARNINGS.value, True):
            return

        self.tray_icon_manager.tray_icon.showMessage(
            self.translator.translate("tray_warning_memory_title"), 
            full_message,
            self.tray_icon_manager.tray_icon.MessageIcon.Critical, 10000
        )
        
    def restart_app(self):
        """Startet die Anwendung sauber neu."""
        try:
            self.quit_app(is_restarting=True)
            subprocess.Popen([sys.executable] + sys.argv)
            sys.exit(0)
        except Exception:
            logging.critical("Fehler beim Neustart der Anwendung.", exc_info=True)
            sys.exit(1)

    def quit_app(self, is_restarting: bool = False):
        """Beendet die Anwendung sauber."""
        logging.info("=== SystemMonitor wird beendet ===")
        try:
            if hasattr(self, 'detachable_manager'):
                self.detachable_manager.save_layout_as("_last_session")
        except Exception:
            logging.exception("Fehler beim Speichern der letzten Session.")

        self._stop_worker_thread()

        if self.hw_manager.lhm_support and self.hw_manager.computer:
            try:
                self.hw_manager.computer.Close()
            except Exception:
                logging.exception("Fehler beim Schließen von LibreHardwareMonitor.")

        if hasattr(self, 'tray_icon_manager'):
            self.tray_icon_manager.tray_icon.hide()
        self.close()

        if not is_restarting:
            if (app := QApplication.instance()):
                app.quit()
        logging.info("SystemMonitor erfolgreich beendet")