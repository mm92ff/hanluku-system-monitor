# core/main_window.py
from __future__ import annotations
from copy import deepcopy
import sys
import logging
import subprocess
from typing import Callable, Dict, Any, Optional, TYPE_CHECKING, TypeVar

from PySide6.QtCore import QThread, QTimer, Slot
from PySide6.QtWidgets import (
    QMainWindow,
    QApplication,
    QMessageBox,
    QWidget,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
)

from config.constants import SettingsKey
from core.app_context import StartupAction
from monitoring.hardware_monitor import HardwareMonitorWorker
from ui.ui_manager import UIManager
from tray.action_handler import ActionHandler
from tray.tray_icon_manager import TrayIconManager
from detachable.detachable_manager import DetachableManager
from ui.widgets.base_window import configure_dialog_layout, style_dialog_button, style_info_label

if TYPE_CHECKING:
    from core.app_context import AppContext

T = TypeVar("T")


class SystemMonitor(QMainWindow):
    """
    Hauptfenster-Klasse, die als Orchestrator für die UI und den Worker-Thread dient.
    Erhält alle Abhängigkeiten über den AppContext.
    """
    THREAD_TERMINATION_TIMEOUT_MS = 5000

    def __init__(self, context: AppContext):
        super().__init__()
        self.context = context
        self.settings_manager = context.settings_manager
        self.translator = context.translator
        self.hw_manager = context.hardware_manager
        self.history_manager = context.history_manager
        
        self.last_data: Dict[str, Any] = {}
        self.latest_health_report: Dict[str, Any] = {}
        self.thread: Optional[QThread] = None
        self.worker: Optional[HardwareMonitorWorker] = None
        self.no_tray_fallback_active = False
        self._is_shutting_down = False
        self._no_tray_info_label: Optional[QLabel] = None
        self._no_tray_toggle_button: Optional[QPushButton] = None
        self._no_tray_help_button: Optional[QPushButton] = None
        self._no_tray_exit_button: Optional[QPushButton] = None

        logging.info("=== SystemMonitor UI wird initialisiert ===")

        self.action_handler = ActionHandler(self)
        self.ui_manager = UIManager(self)
        self.detachable_manager = DetachableManager(self, context.monitor_manager)
        self.tray_icon_manager = TrayIconManager(self)
        if not self.tray_icon_manager.system_tray_available:
            self._setup_no_tray_fallback_window()

        # Signale verbinden
        self.context.data_handler.metric_updated.connect(self.detachable_manager.update_widget_display)
        self.context.data_handler.alarm_state_changed.connect(self.tray_icon_manager.update_alarm_state)
        self.settings_manager.setting_changed.connect(self.on_setting_changed)
        self.context.language_changed.connect(self.refresh_language_ui)
        self.history_manager.database_corrupt.connect(self.handle_corrupt_database) # NEU
        self._schedule_startup_actions()

        self.detachable_manager.start_detached_mode()
        self.init_worker_thread()
        logging.info("=== SystemMonitor ist bereit ===")

    def _schedule_startup_actions(self):
        """Plant UI-bezogene Startup-Aktionen nach dem Signal-Hooking ein."""
        for action in self.context.get_pending_startup_actions():
            if action == StartupAction.DATABASE_RECOVERY:
                QTimer.singleShot(0, self.handle_corrupt_database)

    @Slot()
    def handle_corrupt_database(self):
        """Zeigt einen Dialog an, wenn die Monitoring-DB korrupt ist."""
        self.history_manager.consume_database_recovery_request()
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
        self.context.set_latest_monitor_data(data)
        self.context.data_handler.process_new_data(data)

    @Slot(dict)
    def on_health_report_updated(self, report: dict):
        """Speichert den zuletzt vom Worker gelieferten Health-Report thread-sicher."""
        self.latest_health_report = deepcopy(report or {})

    def get_latest_health_report(self) -> Dict[str, Any]:
        return deepcopy(self.latest_health_report)
        
    def on_setting_changed(self, key: str, value: Any):
        """Reagiert auf globale Einstellungsänderungen."""
        if key == SettingsKey.UPDATE_INTERVAL_MS.value:
            self.restart_worker_thread()
            return

        if self.worker:
            self.worker.queue_setting_update(key, value)

    @Slot(str)
    def refresh_language_ui(self, _language_name: str = ""):
        """Aktualisiert alle UI-Komponenten nach einem Sprachwechsel."""
        self.ui_manager.refresh_metric_definitions()
        self.tray_icon_manager.refresh_language()
        self.action_handler.refresh_open_windows_for_language_change()
        self._refresh_no_tray_fallback_texts()

        if self.last_data:
            self.context.data_handler.process_new_data(self.last_data)

    def _setup_no_tray_fallback_window(self):
        """Zeigt ein sichtbares Steuerfenster, wenn kein System-Tray verfügbar ist."""
        self.no_tray_fallback_active = True
        self.setMinimumSize(460, 220)
        self.resize(520, 240)

        container = QWidget(self)
        layout = QVBoxLayout(container)
        configure_dialog_layout(layout)

        self._no_tray_info_label = QLabel(container)
        style_info_label(self._no_tray_info_label, "subtle")
        layout.addWidget(self._no_tray_info_label)

        button_row = QHBoxLayout()
        button_row.setSpacing(10)

        self._no_tray_toggle_button = QPushButton(container)
        style_dialog_button(self._no_tray_toggle_button, "accent")
        self._no_tray_toggle_button.clicked.connect(self.action_handler.toggle_all_widgets)
        button_row.addWidget(self._no_tray_toggle_button)

        self._no_tray_help_button = QPushButton(container)
        style_dialog_button(self._no_tray_help_button, "secondary")
        self._no_tray_help_button.clicked.connect(self.action_handler.show_help_window)
        button_row.addWidget(self._no_tray_help_button)

        self._no_tray_exit_button = QPushButton(container)
        style_dialog_button(self._no_tray_exit_button, "danger")
        self._no_tray_exit_button.clicked.connect(self.quit_app)
        button_row.addWidget(self._no_tray_exit_button)

        layout.addLayout(button_row)
        layout.addStretch(1)
        self.setCentralWidget(container)
        self._refresh_no_tray_fallback_texts()
        self.show()
        self.raise_()
        self.activateWindow()

    def _refresh_no_tray_fallback_texts(self):
        """Aktualisiert sprachabhängige Texte des No-Tray-Fallback-Fensters."""
        if not self.no_tray_fallback_active:
            return

        self.setWindowTitle(self.translator.translate("no_tray_window_title"))
        if self._no_tray_info_label:
            self._no_tray_info_label.setText(self.translator.translate("no_tray_window_info"))
        if self._no_tray_toggle_button:
            self._no_tray_toggle_button.setText(self.translator.translate("no_tray_button_toggle_widgets"))
        if self._no_tray_help_button:
            self._no_tray_help_button.setText(self.translator.translate("menu_help"))
        if self._no_tray_exit_button:
            self._no_tray_exit_button.setText(self.translator.translate("menu_quit"))
             
    def init_worker_thread(self):
        """Initialisiert und startet den Worker-Thread."""
        if self.thread and self.thread.isRunning():
            self._stop_worker_thread()

        interval = self.settings_manager.get_setting(SettingsKey.UPDATE_INTERVAL_MS.value, 2000)

        self.thread = QThread()
        self.worker = HardwareMonitorWorker(self.context, interval)
        self.worker.moveToThread(self.thread)

        self.thread.started.connect(self.worker.run)
        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.worker.data_updated.connect(self.on_data_updated)
        self.worker.health_report_updated.connect(self.on_health_report_updated)
        self.worker.sensor_error.connect(self.handle_sensor_error)
        self.worker.memory_warning.connect(self.handle_memory_warning)

        self.thread.start()
        logging.info(f"Worker-Thread gestartet (Intervall: {interval}ms)")

    def restart_worker_thread(self):
        """Startet den Worker-Thread sicher neu."""
        logging.info("Worker-Thread wird neugestartet...")
        self._stop_worker_thread()
        self.init_worker_thread()

    def pause_worker(self) -> bool:
        """Pausiert den Worker-Thread und gibt zurÃ¼ck, ob er vorher aktiv war."""
        was_running = bool(self.thread and self.thread.isRunning())
        if was_running:
            self._stop_worker_thread()
        return was_running

    def resume_worker(self, was_running: bool):
        """Startet den Worker-Thread erneut, wenn er zuvor aktiv war."""
        if was_running and not (self.thread and self.thread.isRunning()):
            self.init_worker_thread()

    def run_with_paused_worker(self, operation: Callable[[], T], should_pause: bool = True) -> T:
        """FÃ¼hrt eine Operation mit optional pausiertem Worker aus."""
        worker_was_running = self.pause_worker() if should_pause else False
        try:
            return operation()
        finally:
            self.resume_worker(worker_was_running)

    def _stop_worker_thread(self):
        """Stoppt den Worker-Thread sicher."""
        if not self.thread or not self.worker: return
        
        try:
            self.worker.stop()
            self.thread.quit()
            if not self.thread.wait(self.THREAD_TERMINATION_TIMEOUT_MS):
                logging.critical("Worker-Thread hat nicht innerhalb des Timeouts beendet.")
            logging.debug("Worker-Thread erfolgreich gestoppt")
        except Exception:
            logging.exception("Fehler beim Stoppen des Worker-Threads.")
        finally:
            self.latest_health_report = {}
            self.thread, self.worker = None, None

    def handle_sensor_error(self, sensor_type: str, message: str):
        """Zeigt eine Sensor-Fehlermeldung im Tray an."""
        title = self.translator.translate("lhm_error_title")
        self.tray_icon_manager.show_message(
            title,
            message,
            self.tray_icon_manager.tray_icon.MessageIcon.Warning,
            5000,
        )
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

        self.tray_icon_manager.show_message(
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
        self._is_shutting_down = True
        try:
            if hasattr(self, 'detachable_manager'):
                self.detachable_manager.save_layout_as("_last_session")
        except Exception:
            logging.exception("Fehler beim Speichern der letzten Session.")

        self._stop_worker_thread()

        if hasattr(self, "history_manager"):
            try:
                self.history_manager.shutdown()
            except Exception:
                logging.exception("Fehler beim Beenden des Monitoring-History-Managers.")

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

    def closeEvent(self, event):
        """Verhindert einen versteckten Zombie-Zustand, wenn kein Tray vorhanden ist."""
        if self._is_shutting_down:
            event.accept()
            return

        if self.no_tray_fallback_active:
            event.ignore()
            QTimer.singleShot(0, self.quit_app)
            return

        self.hide()
        event.ignore()
