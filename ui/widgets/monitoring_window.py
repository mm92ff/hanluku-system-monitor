# ui/widgets/monitoring_window.py
from __future__ import annotations
import csv
import logging
from datetime import datetime
from typing import TYPE_CHECKING, Dict, List, Tuple

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QHBoxLayout,
    QCheckBox, QSpinBox, QLabel, QSplitter, QListWidget, QListWidgetItem, QPushButton,
    QFormLayout, QSizePolicy, QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtGui import QFont

from .base_window import SafeWindow
from .graph_widget import GraphWidget
from config.constants import SettingsKey
from monitoring.history_manager import GRAPHABLE_METRICS_MAP

if TYPE_CHECKING:
    from core.main_window import SystemMonitor

class MonitoringWindow(SafeWindow):
    """Fenster zur Anzeige und Steuerung des historischen Monitorings."""

    def __init__(self, main_app: "SystemMonitor"):
        super().__init__(main_app)
        self.main_win = main_app
        self.translator = main_app.translator
        self.settings_manager = main_app.settings_manager
        self.history_manager = main_app.history_manager
        self.ui_manager = main_app.ui_manager

        self.setWindowTitle(self.translator.translate("win_mon_title"))
        self.resize(800, 600)

        self._setup_ui()
        self._populate_sensor_list()
        self._load_settings()
        self._connect_signals()
        
        self.update_timer = QTimer(self)
        self.update_timer.setInterval(5000)
        self.update_timer.timeout.connect(self._update_graph_and_stats)
        if self.monitoring_enabled_checkbox.isChecked():
            self.update_timer.start()

    def _setup_ui(self):
        """Erstellt die Benutzeroberfläche."""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)

        control_group = QGroupBox(self.translator.translate("win_mon_group_control"))
        control_group.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        control_form_layout = QFormLayout(control_group)
        control_form_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        control_form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        self.monitoring_enabled_checkbox = QCheckBox(self.translator.translate("win_mon_chk_enable"))
        
        self.settings_widget = QWidget()
        settings_layout = QHBoxLayout(self.settings_widget)
        settings_layout.setContentsMargins(0,0,0,0)
        
        self.interval_spinbox = QSpinBox()
        self.interval_spinbox.setRange(1, 3600)
        self.interval_spinbox.setSuffix(" s")
        self.duration_spinbox = QSpinBox()
        self.duration_spinbox.setRange(1, 168)
        self.duration_spinbox.setSuffix(" h")
        self.filesize_spinbox = QSpinBox()
        self.filesize_spinbox.setRange(10, 1024)
        self.filesize_spinbox.setSuffix(" MB")
        
        settings_layout.addWidget(QLabel(self.translator.translate("win_mon_lbl_interval")))
        settings_layout.addWidget(self.interval_spinbox)
        settings_layout.addSpacing(20)
        settings_layout.addWidget(QLabel(self.translator.translate("win_mon_lbl_duration")))
        settings_layout.addWidget(self.duration_spinbox)
        settings_layout.addSpacing(20)
        settings_layout.addWidget(QLabel(self.translator.translate("win_mon_lbl_size")))
        settings_layout.addWidget(self.filesize_spinbox)
        settings_layout.addStretch()

        control_form_layout.addRow(self.monitoring_enabled_checkbox)
        control_form_layout.addRow(self.translator.translate("win_mon_lbl_settings"), self.settings_widget)
        
        main_layout.addWidget(control_group)

        data_group = QGroupBox(self.translator.translate("win_mon_group_data"))
        data_layout = QVBoxLayout(data_group)
        main_layout.addWidget(data_group)
        
        splitter = QSplitter(Qt.Orientation.Horizontal)
        data_layout.addWidget(splitter)
        
        self.sensor_list_widget = QListWidget()
        self.sensor_list_widget.setStyleSheet("QListWidget::item { margin: 3px; }")
        splitter.addWidget(self.sensor_list_widget)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        self.graph_widget = GraphWidget(translator=self.translator)
        
        self.stats_label = QLabel(self.translator.translate("win_mon_stats_select_sensor"))
        self.stats_label.setFont(QFont("Segoe UI", 9))
        self.stats_label.setStyleSheet("color: #aaa;")
        
        right_layout.addWidget(self.graph_widget)
        right_layout.addWidget(self.stats_label, 0, Qt.AlignmentFlag.AlignRight)
        splitter.addWidget(right_panel)
        splitter.setSizes([250, 550])

        main_layout.setStretchFactor(data_group, 1)

        button_layout = QHBoxLayout()
        self.export_button = QPushButton(self.translator.translate("win_mon_btn_export"))
        button_layout.addWidget(self.export_button)
        button_layout.addStretch()
        close_button = QPushButton(self.translator.translate("win_shared_button_close"))
        button_layout.addWidget(close_button)
        main_layout.addLayout(button_layout)

    def _populate_sensor_list(self):
        """Füllt die Liste mit allen verfügbaren und aufzeichenbaren Sensoren."""
        self.sensor_list_widget.clear()

        all_metrics = {}
        for key, raw_key in GRAPHABLE_METRICS_MAP.items():
            display_name = key
            if info := self.ui_manager.metric_widgets.get(key):
                display_name = info.get('full_text', key).replace(':', '')
            else:
                if key == 'disk_read': display_name = "Disk Read"
                elif key == 'disk_write': display_name = "Disk Write"
                elif key == 'net_upload': display_name = "Net Upload"
                elif key == 'net_download': display_name = "Net Download"
            all_metrics[key] = display_name
        
        for key, info in self.ui_manager.metric_widgets.items():
            if key.startswith("storage_temp_") or key.startswith("custom_"):
                 all_metrics[key] = info.get('full_text', key).replace(':', '')
        
        sorted_items = sorted(all_metrics.items(), key=lambda item: item[1])

        for key, display_name in sorted_items:
            item = QListWidgetItem(display_name, self.sensor_list_widget)
            item.setData(Qt.ItemDataRole.UserRole, key)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)

    def _load_settings(self):
        enabled = self.settings_manager.get_setting(SettingsKey.MONITORING_ENABLED.value, False)
        self.monitoring_enabled_checkbox.setChecked(enabled)
        self.settings_widget.setEnabled(enabled)
        self.interval_spinbox.setValue(self.settings_manager.get_setting(SettingsKey.MONITORING_INTERVAL_SEC.value, 60))
        self.duration_spinbox.setValue(self.settings_manager.get_setting(SettingsKey.MONITORING_MAX_DURATION_HOURS.value, 24))
        self.filesize_spinbox.setValue(self.settings_manager.get_setting(SettingsKey.MONITORING_MAX_FILE_SIZE_MB.value, 100))

    def _connect_signals(self):
        self.monitoring_enabled_checkbox.toggled.connect(self._on_monitoring_toggled)
        self.interval_spinbox.valueChanged.connect(self._on_interval_changed)
        self.duration_spinbox.valueChanged.connect(self._on_duration_changed)
        self.filesize_spinbox.valueChanged.connect(self._on_filesize_changed)
        self.sensor_list_widget.itemChanged.connect(self._update_graph_and_stats)
        self.export_button.clicked.connect(self._on_export_clicked)

    @Slot()
    def _on_export_clicked(self):
        """Exportiert die Daten der ausgewählten Sensoren in eine CSV-Datei."""
        selected_metrics = self._get_selected_metrics()
        if not selected_metrics:
            QMessageBox.warning(self, self.translator.translate("win_mon_export_no_selection_title"),
                                self.translator.translate("win_mon_export_no_selection_text"))
            return

        data_to_export = self.history_manager.get_data_for_metrics(selected_metrics, hours_ago=None)
        if not any(data_to_export.values()):
            QMessageBox.information(self, self.translator.translate("win_mon_export_no_data_title"),
                                    self.translator.translate("win_mon_export_no_data_text"))
            return

        default_filename = f"monitoring_export_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.csv"
        file_path, _ = QFileDialog.getSaveFileName(self, self.translator.translate("win_mon_export_dialog_title"),
                                                 default_filename, self.translator.translate("shared_file_filter_csv"))

        if not file_path:
            return

        try:
            # KORRIGIERT: Fehlerhafte Dictionary Comprehension durch eine saubere Schleife ersetzt.
            key_to_display_name = {}
            for i in range(self.sensor_list_widget.count()):
                item = self.sensor_list_widget.item(i)
                key_to_display_name[item.data(Qt.ItemDataRole.UserRole)] = item.text()
            
            all_rows = []
            for metric_key, points in data_to_export.items():
                display_name = key_to_display_name.get(metric_key, metric_key)
                for timestamp, value in points:
                    readable_ts = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
                    all_rows.append([readable_ts, display_name, value])
            
            all_rows.sort(key=lambda row: row[0])

            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['timestamp', 'sensor_name', 'value'])
                writer.writerows(all_rows)

            QMessageBox.information(self, self.translator.translate("win_mon_export_success_title"),
                                    self.translator.translate("win_mon_export_success_text", file_path=file_path))

        except Exception as e:
            logging.error(f"Fehler beim CSV-Export: {e}")
            QMessageBox.critical(self, self.translator.translate("win_mon_export_failed_title"),
                                 self.translator.translate("win_mon_export_failed_text", error=e))

    @Slot(bool)
    def _on_monitoring_toggled(self, checked: bool):
        self.settings_manager.set_setting(SettingsKey.MONITORING_ENABLED.value, checked)
        self.settings_widget.setEnabled(checked)
        if checked:
            self.history_manager.start_monitoring()
            self.update_timer.start()
        else:
            self.history_manager.stop_monitoring()
            self.update_timer.stop()
            
    @Slot(int)
    def _on_interval_changed(self, value: int):
        self.settings_manager.set_setting(SettingsKey.MONITORING_INTERVAL_SEC.value, value)
        self.history_manager.set_interval(value)
        
    @Slot(int)
    def _on_duration_changed(self, value: int):
        self.settings_manager.set_setting(SettingsKey.MONITORING_MAX_DURATION_HOURS.value, value)
        self.history_manager.set_max_duration(value)
        
    @Slot(int)
    def _on_filesize_changed(self, value: int):
        self.settings_manager.set_setting(SettingsKey.MONITORING_MAX_FILE_SIZE_MB.value, value)
        self.history_manager.set_max_file_size(value)

    def _get_selected_metrics(self) -> List[str]:
        selected = []
        for i in range(self.sensor_list_widget.count()):
            item = self.sensor_list_widget.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                selected.append(item.data(Qt.ItemDataRole.UserRole))
        return selected

    @Slot()
    def _update_graph_and_stats(self):
        selected_metrics = self._get_selected_metrics()
        
        current_graph_metric_key = selected_metrics[0] if selected_metrics else None

        if not selected_metrics:
            self.graph_widget.set_data({})
            self.stats_label.setText(self.translator.translate("win_mon_stats_select_sensor"))
            return
            
        data = self.history_manager.get_data_for_metrics(selected_metrics)
        self.graph_widget.set_data(data, current_graph_metric_key)
        
        first_metric_key = selected_metrics[0]
        stats = self.history_manager.get_session_stats(first_metric_key)
        min_v, max_v, avg_v = stats.get('min'), stats.get('max'), stats.get('avg')
        
        min_str = f"{min_v:.1f}" if min_v is not None else "-"
        max_str = f"{max_v:.1f}" if max_v is not None else "-"
        avg_str = f"{avg_v:.1f}" if avg_v is not None else "-"
        
        display_name = "N/A"
        for i in range(self.sensor_list_widget.count()):
            item = self.sensor_list_widget.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == first_metric_key:
                display_name = item.text()
                break
        
        self.stats_label.setText(self.translator.translate("win_mon_stats_text", name=display_name, min=min_str, max=max_str, avg=avg_str))