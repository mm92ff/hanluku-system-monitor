# ui/widgets/monitoring_window.py
from __future__ import annotations

import csv
import logging
from datetime import datetime
from typing import TYPE_CHECKING, List

from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from config.constants import SettingsKey
from monitoring.history_manager import GRAPHABLE_METRICS_MAP
from .base_window import (
    SafeWindow,
    configure_dialog_layout,
    configure_dialog_window,
    style_dialog_button,
    style_info_label,
    style_list_widget,
)
from .graph_widget import GraphWidget

if TYPE_CHECKING:
    from core.main_window import SystemMonitor


class MonitoringWindow(SafeWindow):
    """Fenster zur Anzeige und Steuerung des historischen Monitorings."""

    HISTORY_WINDOW_HOURS = 1

    def __init__(self, main_app: "SystemMonitor"):
        super().__init__(main_app)
        self.main_win = main_app
        self.translator = main_app.translator
        self.settings_manager = main_app.settings_manager
        self.history_manager = main_app.history_manager
        self.ui_manager = main_app.ui_manager

        self.setWindowTitle(self.translator.translate("win_mon_title"))
        configure_dialog_window(self, 800, 600)

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
        """Erstellt die Benutzeroberflaeche."""
        main_layout = QVBoxLayout(self)
        configure_dialog_layout(main_layout)
        main_layout.setSpacing(10)

        control_group = QGroupBox(self.translator.translate("win_mon_group_control"))
        control_group.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Fixed,
        )
        control_form_layout = QFormLayout(control_group)
        configure_dialog_layout(control_form_layout, margins=(12, 12, 12, 12))
        control_form_layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        control_form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        self.monitoring_enabled_checkbox = QCheckBox(
            self.translator.translate("win_mon_chk_enable")
        )

        self.settings_widget = QWidget()
        settings_layout = QHBoxLayout(self.settings_widget)
        settings_layout.setContentsMargins(0, 0, 0, 0)

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
        control_form_layout.addRow(
            self.translator.translate("win_mon_lbl_settings"),
            self.settings_widget,
        )
        main_layout.addWidget(control_group)

        data_group = QGroupBox(self.translator.translate("win_mon_group_data"))
        data_layout = QVBoxLayout(data_group)
        main_layout.addWidget(data_group)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        data_layout.addWidget(splitter)

        self.sensor_list_widget = QListWidget()
        style_list_widget(self.sensor_list_widget, item_margin=3)
        splitter.addWidget(self.sensor_list_widget)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        self.graph_widget = GraphWidget(translator=self.translator)

        self.stats_label = QLabel(self.translator.translate("win_mon_stats_select_sensor"))
        self.stats_label.setFont(QFont("Segoe UI", 9))
        style_info_label(self.stats_label, "subtle")
        self.stats_label.setWordWrap(True)

        right_layout.addWidget(self.graph_widget)
        right_layout.addWidget(self.stats_label, 0, Qt.AlignmentFlag.AlignRight)
        splitter.addWidget(right_panel)
        splitter.setSizes([250, 550])

        main_layout.setStretchFactor(data_group, 1)

        button_layout = QHBoxLayout()
        self.export_button = QPushButton(self.translator.translate("win_mon_btn_export"))
        style_dialog_button(self.export_button, "accent")
        button_layout.addWidget(self.export_button)
        button_layout.addStretch()
        self.close_button = QPushButton(self.translator.translate("win_shared_button_close"))
        style_dialog_button(self.close_button, "secondary")
        button_layout.addWidget(self.close_button)
        main_layout.addLayout(button_layout)

    def _populate_sensor_list(self):
        """Fuellt die Liste mit allen verfuegbaren und aufzeichenbaren Sensoren."""
        self.sensor_list_widget.clear()

        all_metrics = {}
        for key in GRAPHABLE_METRICS_MAP:
            display_name = key
            if info := self.ui_manager.metric_widgets.get(key):
                display_name = info.get("full_text", key).replace(":", "")
            else:
                if key == "disk_read":
                    display_name = "Disk Read"
                elif key == "disk_write":
                    display_name = "Disk Write"
                elif key == "net_upload":
                    display_name = "Net Upload"
                elif key == "net_download":
                    display_name = "Net Download"
            all_metrics[key] = display_name

        for key, info in self.ui_manager.metric_widgets.items():
            if key.startswith("storage_temp_") or key.startswith("custom_"):
                all_metrics[key] = info.get("full_text", key).replace(":", "")

        for key, display_name in sorted(all_metrics.items(), key=lambda item: item[1]):
            item = QListWidgetItem(display_name, self.sensor_list_widget)
            item.setData(Qt.ItemDataRole.UserRole, key)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)

    def _load_settings(self):
        enabled = self.settings_manager.get_setting(
            SettingsKey.MONITORING_ENABLED.value,
            False,
        )
        self.monitoring_enabled_checkbox.setChecked(enabled)
        self.settings_widget.setEnabled(enabled)
        self.interval_spinbox.setValue(
            self.settings_manager.get_setting(SettingsKey.MONITORING_INTERVAL_SEC.value, 60)
        )
        self.duration_spinbox.setValue(
            self.settings_manager.get_setting(
                SettingsKey.MONITORING_MAX_DURATION_HOURS.value,
                24,
            )
        )
        self.filesize_spinbox.setValue(
            self.settings_manager.get_setting(
                SettingsKey.MONITORING_MAX_FILE_SIZE_MB.value,
                100,
            )
        )

    def _connect_signals(self):
        self.monitoring_enabled_checkbox.toggled.connect(self._on_monitoring_toggled)
        self.interval_spinbox.valueChanged.connect(self._on_interval_changed)
        self.duration_spinbox.valueChanged.connect(self._on_duration_changed)
        self.filesize_spinbox.valueChanged.connect(self._on_filesize_changed)
        self.sensor_list_widget.itemChanged.connect(self._update_graph_and_stats)
        self.export_button.clicked.connect(self._on_export_clicked)
        self.close_button.clicked.connect(self.close_safely)

    def _get_temperature_unit_symbol(self) -> str:
        return (
            " K"
            if self.settings_manager.get_setting(SettingsKey.TEMPERATURE_UNIT.value, "C") == "K"
            else "°C"
        )

    def _resolve_metric_unit(self, metric_key: str) -> str:
        if metric_key in {"cpu", "ram", "disk", "gpu_vram"}:
            return "%"
        if metric_key in {"gpu_core_clock", "gpu_memory_clock"}:
            return "MHz"
        if metric_key == "gpu_power":
            return "W"
        if metric_key in {"cpu_temp", "gpu", "gpu_hotspot", "gpu_memory_temp"}:
            return self._get_temperature_unit_symbol()
        if metric_key.startswith("storage_temp_"):
            return self._get_temperature_unit_symbol()
        if metric_key in {"disk_read", "disk_write"}:
            return self.settings_manager.get_setting(SettingsKey.DISK_IO_UNIT.value, "MB/s")
        if metric_key in {"net_upload", "net_download"}:
            return self.settings_manager.get_setting(SettingsKey.NETWORK_UNIT.value, "MBit/s")
        if metric_key.startswith("custom_"):
            return self.main_win.context.data_handler.custom_sensors.get(metric_key, {}).get(
                "unit",
                "",
            )
        return ""

    def _get_metric_compatibility_key(self, metric_key: str) -> str:
        unit = self._resolve_metric_unit(metric_key)
        return f"unit:{unit}" if unit else f"metric:{metric_key}"

    def _convert_history_value(self, metric_key: str, value: float | None) -> float | None:
        if value is None:
            return None

        if metric_key in {"cpu_temp", "gpu", "gpu_hotspot", "gpu_memory_temp"} or metric_key.startswith(
            "storage_temp_"
        ):
            if self.settings_manager.get_setting(SettingsKey.TEMPERATURE_UNIT.value, "C") == "K":
                return value + 273.15
            return value

        if metric_key in {"disk_read", "disk_write"}:
            if self.settings_manager.get_setting(SettingsKey.DISK_IO_UNIT.value, "MB/s") == "GB/s":
                return value / 1000.0
            return value

        if metric_key in {"net_upload", "net_download"}:
            if self.settings_manager.get_setting(SettingsKey.NETWORK_UNIT.value, "MBit/s") == "GBit/s":
                return value / 1000.0
            return value

        return value

    def _convert_history_series(self, metric_key: str, points):
        return [
            (timestamp, self._convert_history_value(metric_key, value))
            for timestamp, value in points
        ]

    def _get_graph_metrics(self, selected_metrics: List[str]) -> tuple[List[str], List[str]]:
        if not selected_metrics:
            return [], []
        compatibility_key = self._get_metric_compatibility_key(selected_metrics[0])
        graph_metrics = [
            metric_key
            for metric_key in selected_metrics
            if self._get_metric_compatibility_key(metric_key) == compatibility_key
        ]
        skipped_metrics = [
            metric_key for metric_key in selected_metrics if metric_key not in graph_metrics
        ]
        return graph_metrics, skipped_metrics

    @Slot()
    def _on_export_clicked(self):
        """Exportiert die Daten der ausgewaehlten Sensoren in eine CSV-Datei."""
        selected_metrics = self._get_selected_metrics()
        if not selected_metrics:
            QMessageBox.warning(
                self,
                self.translator.translate("win_mon_export_no_selection_title"),
                self.translator.translate("win_mon_export_no_selection_text"),
            )
            return

        data_to_export = self.history_manager.get_data_for_metrics(
            selected_metrics,
            hours_ago=None,
        )
        if not any(data_to_export.values()):
            QMessageBox.information(
                self,
                self.translator.translate("win_mon_export_no_data_title"),
                self.translator.translate("win_mon_export_no_data_text"),
            )
            return

        default_filename = (
            f"monitoring_export_{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.csv"
        )
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            self.translator.translate("win_mon_export_dialog_title"),
            default_filename,
            self.translator.translate("shared_file_filter_csv"),
        )
        if not file_path:
            return

        try:
            key_to_display_name = {}
            for i in range(self.sensor_list_widget.count()):
                item = self.sensor_list_widget.item(i)
                key_to_display_name[item.data(Qt.ItemDataRole.UserRole)] = item.text()

            all_rows = []
            for metric_key, points in data_to_export.items():
                display_name = key_to_display_name.get(metric_key, metric_key)
                for timestamp, value in points:
                    readable_ts = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
                    all_rows.append([readable_ts, display_name, value])

            all_rows.sort(key=lambda row: row[0])

            with open(file_path, "w", newline="", encoding="utf-8") as file_handle:
                writer = csv.writer(file_handle)
                writer.writerow(["timestamp", "sensor_name", "value"])
                writer.writerows(all_rows)

            QMessageBox.information(
                self,
                self.translator.translate("win_mon_export_success_title"),
                self.translator.translate(
                    "win_mon_export_success_text",
                    file_path=file_path,
                ),
            )
        except Exception as e:
            logging.error(f"Fehler beim CSV-Export: {e}")
            QMessageBox.critical(
                self,
                self.translator.translate("win_mon_export_failed_title"),
                self.translator.translate("win_mon_export_failed_text", error=e),
            )

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
        self.settings_manager.set_setting(
            SettingsKey.MONITORING_MAX_DURATION_HOURS.value,
            value,
        )
        self.history_manager.set_max_duration(value)

    @Slot(int)
    def _on_filesize_changed(self, value: int):
        self.settings_manager.set_setting(
            SettingsKey.MONITORING_MAX_FILE_SIZE_MB.value,
            value,
        )
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

        graph_metrics, skipped_metrics = self._get_graph_metrics(selected_metrics)
        raw_data = self.history_manager.get_data_for_metrics(
            graph_metrics,
            hours_ago=self.HISTORY_WINDOW_HOURS,
        )
        converted_data = {
            metric_key: self._convert_history_series(metric_key, points)
            for metric_key, points in raw_data.items()
        }
        self.graph_widget.set_data(
            converted_data,
            current_unit=self._resolve_metric_unit(current_graph_metric_key),
        )

        first_metric_key = selected_metrics[0]
        stats = self.history_manager.get_session_stats(
            first_metric_key,
            hours_ago=self.HISTORY_WINDOW_HOURS,
        )
        min_v = self._convert_history_value(first_metric_key, stats.get("min"))
        max_v = self._convert_history_value(first_metric_key, stats.get("max"))
        avg_v = self._convert_history_value(first_metric_key, stats.get("avg"))

        min_str = f"{min_v:.1f}" if min_v is not None else "-"
        max_str = f"{max_v:.1f}" if max_v is not None else "-"
        avg_str = f"{avg_v:.1f}" if avg_v is not None else "-"

        display_name = "N/A"
        for i in range(self.sensor_list_widget.count()):
            item = self.sensor_list_widget.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == first_metric_key:
                display_name = item.text()
                break

        stats_text = self.translator.translate(
            "win_mon_stats_text",
            name=display_name,
            min=min_str,
            max=max_str,
            avg=avg_str,
        )
        if skipped_metrics:
            stats_text = (
                f"{stats_text}\n"
                f"{self.translator.translate('win_mon_stats_mixed_units_note', name=display_name)}"
            )
        self.stats_label.setText(stats_text)

    def export_language_refresh_state(self) -> dict:
        return {
            "selected_metrics": self._get_selected_metrics(),
        }

    def apply_language_refresh_state(self, state: dict):
        selected_metrics = set(state.get("selected_metrics", []))
        for i in range(self.sensor_list_widget.count()):
            item = self.sensor_list_widget.item(i)
            item.setCheckState(
                Qt.CheckState.Checked
                if item.data(Qt.ItemDataRole.UserRole) in selected_metrics
                else Qt.CheckState.Unchecked
            )
        self._update_graph_and_stats()
