# ui/widgets/performance_settings_window.py
import logging
import psutil
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QGridLayout,
    QPushButton, QSpinBox, QDoubleSpinBox, QWidget,
    QCheckBox, QGroupBox, QMessageBox, QFrame
)
from PySide6.QtGui import QIcon, QFont
from PySide6.QtCore import QTimer
from config import default_values
from .base_window import SafeWindow
from config.constants import SettingsKey

class PerformanceSettingsWindow(SafeWindow):
    """Fenster zum Bearbeiten der Performance Tracker Schwellenwerte."""
    def __init__(self, main_app):
        super().__init__(main_app)
        self.main_app = main_app
        self.translator = main_app.translator
        self.settings_manager = main_app.settings_manager
        self.setWindowTitle(self.translator.translate("win_title_perf"))

        try:
            self.setWindowIcon(self.main_app.tray_icon_manager.tray_icon.icon())
        except AttributeError:
            self.setWindowIcon(QIcon())

        self.setGeometry(400, 400, 500, 500)
        self.input_widgets = {}
        self.current_memory_mb = 0
        self.baseline_memory_mb = 0
        self.init_ui()
        self.load_settings()
        self.update_memory_display()
        self.load_baseline_info()

    def init_ui(self):
        main_widget = QWidget(self)
        layout = QVBoxLayout(main_widget)

        thresholds_group = QGroupBox(self.translator.translate("win_perf_thresholds_group"))
        grid_layout = QGridLayout(thresholds_group)

        settings_map = {
            SettingsKey.PERF_MEM_THRESHOLD_MB: {"label": self.translator.translate("win_perf_mem_threshold"), "widget": QSpinBox, "range": (10, 1000)},
            SettingsKey.PERF_MEM_CHECK_INTERVAL_SEC: {"label": self.translator.translate("win_perf_mem_interval"), "widget": QSpinBox, "range": (5, 600)},
            SettingsKey.PERF_MEM_TREND_THRESHOLD_MB: {"label": self.translator.translate("win_perf_trend_threshold"), "widget": QSpinBox, "range": (1, 100)},
            SettingsKey.PERF_SLOW_UPDATE_THRESHOLD_SEC: {"label": self.translator.translate("win_perf_slow_update"), "widget": QDoubleSpinBox, "range": (0.5, 60.0)},
            SettingsKey.PERF_GC_THRESHOLD_UPDATES: {"label": self.translator.translate("win_perf_gc_threshold"), "widget": QSpinBox, "range": (10, 1000)}
        }

        row_count = 0
        for row, (key_enum, config) in enumerate(settings_map.items()):
            key = key_enum.value
            widget = config["widget"]()
            widget.setRange(*config["range"])
            if isinstance(widget, QDoubleSpinBox):
                widget.setSingleStep(0.5)
            grid_layout.addWidget(QLabel(config["label"]), row, 0)
            grid_layout.addWidget(widget, row, 1)
            self.input_widgets[key] = widget
            row_count = row

        # NEUE CHECKBOX HINZUGEFÜGT
        self.show_warnings_checkbox = QCheckBox(self.translator.translate("win_perf_show_warnings"))
        grid_layout.addWidget(self.show_warnings_checkbox, row_count + 1, 0, 1, 2)


        layout.addWidget(thresholds_group)

        baseline_group = QGroupBox(self.translator.translate("win_perf_baseline_group"))
        baseline_layout = QVBoxLayout(baseline_group)

        self.memory_info_layout = QHBoxLayout()
        self.memory_label = QLabel(f'{self.translator.translate("win_perf_current_memory")}: {self.translator.translate("win_perf_loading")}')
        self.refresh_button = QPushButton("🔄")
        self.refresh_button.setMaximumWidth(30)
        self.refresh_button.setToolTip(self.translator.translate("win_perf_refresh_tooltip"))
        self.refresh_button.clicked.connect(self.update_memory_display)

        self.memory_info_layout.addWidget(self.memory_label)
        self.memory_info_layout.addWidget(self.refresh_button)
        self.memory_info_layout.addStretch()
        baseline_layout.addLayout(self.memory_info_layout)

        separator = QFrame()
        separator.setFrameStyle(QFrame.Shape.HLine | QFrame.Shadow.Sunken)
        baseline_layout.addWidget(separator)

        self.baseline_info_layout = QHBoxLayout()
        self.baseline_label = QLabel(f'{self.translator.translate("win_perf_current_baseline")}: {self.translator.translate("win_perf_loading")}')
        self.baseline_label.setFont(QFont("", 9))
        self.baseline_label.setStyleSheet("color: #666; padding: 5px;")
        self.baseline_info_layout.addWidget(self.baseline_label)
        self.baseline_info_layout.addStretch()
        baseline_layout.addLayout(self.baseline_info_layout)

        self.reset_baseline_checkbox = QCheckBox(self.translator.translate("win_perf_reset_baseline_checkbox"))
        self.reset_baseline_checkbox.setToolTip(self.translator.translate("win_perf_reset_baseline_tooltip"))
        baseline_layout.addWidget(self.reset_baseline_checkbox)

        info_label = QLabel(self.translator.translate("win_perf_baseline_info_label"))
        info_label.setStyleSheet("color: #666; font-size: 11px; margin: 5px;")
        info_label.setWordWrap(True)
        baseline_layout.addWidget(info_label)

        layout.addWidget(baseline_group)
        layout.addStretch()

        button_layout = QHBoxLayout()
        reset_button = QPushButton(self.translator.translate("win_shared_button_reset"))
        reset_button.clicked.connect(self.reset_settings)
        save_button = QPushButton(self.translator.translate("win_shared_button_save_close"))
        save_button.clicked.connect(self.save_and_close)

        button_layout.addWidget(reset_button)
        button_layout.addStretch()
        button_layout.addWidget(save_button)
        layout.addLayout(button_layout)

        central_layout = QVBoxLayout(self)
        central_layout.addWidget(main_widget)

    def get_current_memory_usage(self) -> float:
        try:
            import os
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            return memory_info.rss / (1024 * 1024)
        except Exception as e:
            logging.error(f"Fehler beim Ermitteln des Speicherverbrauchs: {e}")
            return 0.0

    def update_memory_display(self):
        self.current_memory_mb = self.get_current_memory_usage()
        prefix = self.translator.translate("win_perf_current_memory")
        if self.current_memory_mb > 0:
            self.memory_label.setText(f"{prefix}: {self.current_memory_mb:.1f} MB")
        else:
            self.memory_label.setText(f'{prefix}: {self.translator.translate("shared_unavailable")}')
        self.load_baseline_info()

    def load_baseline_info(self):
        prefix = self.translator.translate("win_perf_current_baseline")
        try:
            if (hasattr(self.main_app, 'worker') and self.main_app.worker and
                hasattr(self.main_app.worker, 'performance_tracker')):
                performance_tracker = self.main_app.worker.performance_tracker

                if hasattr(performance_tracker, '_baseline_memory'):
                    self.baseline_memory_mb = performance_tracker._baseline_memory or 0
                    if self.baseline_memory_mb > 0:
                        diff_str = ""
                        if self.current_memory_mb > 0:
                            diff = self.current_memory_mb - self.baseline_memory_mb
                            if abs(diff) > 0.1:
                                diff_str = self.translator.translate("win_perf_baseline_delta", diff=f"{diff:+.1f}")
                        
                        self.baseline_label.setText(f"{prefix}: {self.baseline_memory_mb:.1f} MB{diff_str}")

                        if self.current_memory_mb > 0:
                            if abs(diff) < 10: color = "#4CAF50"
                            elif abs(diff) < 30: color = "#FF9800"
                            else: color = "#F44336"
                            self.baseline_label.setStyleSheet(f"color: {color}; padding: 5px;")
                        else:
                            self.baseline_label.setStyleSheet("color: #666; padding: 5px;")
                    else:
                        self.baseline_label.setText(f'{prefix}: {self.translator.translate("shared_unavailable")}')
                        self.baseline_label.setStyleSheet("color: #666; padding: 5px;")
                else:
                    self.baseline_label.setText(f'{prefix}: {self.translator.translate("win_perf_tracker_unavailable")}')
                    self.baseline_label.setStyleSheet("color: #666; padding: 5px;")
            else:
                self.baseline_label.setText(f'{prefix}: {self.translator.translate("win_perf_worker_unavailable")}')
                self.baseline_label.setStyleSheet("color: #666; padding: 5px;")
        except Exception as e:
            logging.error(f"Fehler beim Laden der Baseline-Info: {e}")
            self.baseline_label.setText(f'{prefix}: {self.translator.translate("shared_error_loading")}')
            self.baseline_label.setStyleSheet("color: #F44336; padding: 5px;")

    def load_settings(self):
        for key, widget in self.input_widgets.items():
            default_val = default_values.DEFAULT_SETTINGS_BASE.get(key, 0)
            value = self.settings_manager.get_setting(key, default_val)
            widget.setValue(float(value))
        
        # LADEZUSTAND FÜR NEUE CHECKBOX
        self.show_warnings_checkbox.setChecked(self.settings_manager.get_setting(SettingsKey.PERF_SHOW_WARNINGS.value, True))

    def reset_settings(self):
        for key, widget in self.input_widgets.items():
            default_val = default_values.DEFAULT_SETTINGS_BASE.get(key, 0)
            widget.setValue(float(default_val))
        self.reset_baseline_checkbox.setChecked(False)
        self.show_warnings_checkbox.setChecked(True) # ZURÜCKSETZEN FÜR NEUE CHECKBOX

    def _reset_memory_baseline(self) -> bool:
        try:
            if (hasattr(self.main_app, 'worker') and self.main_app.worker and
                hasattr(self.main_app.worker, 'performance_tracker')):
                performance_tracker = self.main_app.worker.performance_tracker
                success = performance_tracker.reset_memory_baseline(self.current_memory_mb)
                if success:
                    logging.info(f"Memory Baseline erfolgreich auf {self.current_memory_mb:.1f} MB gesetzt")
                    return True
                else:
                    logging.error("reset_memory_baseline() Methode schlug fehl")
                    return False
            else:
                logging.error("Performance Tracker nicht verfügbar")
                return False
        except Exception as e:
            logging.error(f"Fehler beim Zurücksetzen der Memory Baseline: {e}")
            return False

    def save_and_close(self):
        updates = {key: widget.value() for key, widget in self.input_widgets.items()}
        # SPEICHERN FÜR NEUE CHECKBOX
        updates[SettingsKey.PERF_SHOW_WARNINGS.value] = self.show_warnings_checkbox.isChecked()

        self.settings_manager.update_settings(updates)

        if self.reset_baseline_checkbox.isChecked():
            if self.current_memory_mb > 0:
                success = self._reset_memory_baseline()
                if success:
                    QMessageBox.information(
                        self,
                        self.translator.translate("dlg_baseline_reset_title"),
                        self.translator.translate("dlg_baseline_reset_success_text", value=f"{self.current_memory_mb:.1f}")
                    )
                else:
                    QMessageBox.warning(
                        self,
                        self.translator.translate("dlg_baseline_reset_error_title"),
                        self.translator.translate("dlg_baseline_reset_error_text")
                    )
            else:
                QMessageBox.warning(
                    self,
                    self.translator.translate("dlg_baseline_reset_unknown_mem_title"),
                    self.translator.translate("dlg_baseline_reset_unknown_mem_text")
                )
        self.close_safely()