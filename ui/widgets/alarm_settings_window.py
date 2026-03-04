import logging
import re

from PySide6.QtGui import QDoubleValidator, QIcon
from PySide6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from config.constants import DiskIOUnit, NetworkUnit, SettingsKey, TemperatureUnit

from .base_window import (
    SafeWindow,
    configure_dialog_layout,
    configure_dialog_window,
    style_dialog_button,
)


class AlarmSettingsWindow(SafeWindow):
    """Window for editing alarm thresholds."""

    TEMPERATURE_THRESHOLD_KEYS = {
        SettingsKey.CPU_TEMP_THRESHOLD,
        SettingsKey.STORAGE_TEMP_THRESHOLD,
        SettingsKey.GPU_CORE_TEMP_THRESHOLD,
        SettingsKey.GPU_HOTSPOT_THRESHOLD,
        SettingsKey.GPU_MEMORY_TEMP_THRESHOLD,
    }
    DISK_IO_THRESHOLD_KEYS = {
        SettingsKey.DISK_READ_THRESHOLD,
        SettingsKey.DISK_WRITE_THRESHOLD,
    }
    NETWORK_THRESHOLD_KEYS = {
        SettingsKey.NET_UP_THRESHOLD,
        SettingsKey.NET_DOWN_THRESHOLD,
    }
    PERCENT_THRESHOLD_KEYS = {
        SettingsKey.CPU_THRESHOLD,
        SettingsKey.RAM_THRESHOLD,
        SettingsKey.DISK_THRESHOLD,
        SettingsKey.VRAM_THRESHOLD,
    }
    CLOCK_THRESHOLD_KEYS = {
        SettingsKey.GPU_CORE_CLOCK_THRESHOLD,
        SettingsKey.GPU_MEMORY_CLOCK_THRESHOLD,
    }

    def __init__(self, main_app):
        super().__init__(main_app)
        self.main_app = main_app
        self.translator = main_app.translator
        self.settings_manager = main_app.settings_manager
        self.setWindowTitle(self.translator.translate("win_title_alarm"))

        try:
            icon = self.main_app.tray_icon_manager.tray_icon.icon()
            self.setWindowIcon(icon)
        except AttributeError:
            logging.warning("Could not load tray icon for alarm settings window.")
            self.setWindowIcon(QIcon())

        configure_dialog_window(self, 400, 450)
        self.threshold_widgets = {}
        self.threshold_display_names = {}
        self.init_ui()
        self.load_thresholds()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        configure_dialog_layout(main_layout)

        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel(f'<b>{self.translator.translate("win_alarm_metric")}</b>'))
        header_layout.addWidget(QLabel(f'<b>{self.translator.translate("win_alarm_threshold")}</b>'))
        main_layout.addLayout(header_layout)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        main_layout.addWidget(scroll_area)
        container = QWidget()
        self.grid_layout = QGridLayout(container)
        scroll_area.setWidget(container)

        button_layout = QHBoxLayout()
        save_button = QPushButton(self.translator.translate("win_shared_button_save_close"))
        save_button.clicked.connect(self.save_and_apply)
        cancel_button = QPushButton(self.translator.translate("win_shared_button_cancel"))
        cancel_button.clicked.connect(self.close_safely)
        style_dialog_button(save_button, "primary")
        style_dialog_button(cancel_button, "secondary")
        button_layout.addStretch()
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)
        main_layout.addLayout(button_layout)

    def load_thresholds(self):
        """Load current thresholds and create editor widgets."""
        double_validator = QDoubleValidator(0.0, 99999.0, 2)
        display_map = {
            SettingsKey.CPU_THRESHOLD: self.translator.translate("metric_cpu_load"),
            SettingsKey.CPU_TEMP_THRESHOLD: self.translator.translate("metric_cpu_temp"),
            SettingsKey.RAM_THRESHOLD: self.translator.translate("metric_ram_load"),
            SettingsKey.DISK_THRESHOLD: self.translator.translate("metric_disk_load"),
            SettingsKey.STORAGE_TEMP_THRESHOLD: self.translator.translate("metric_storage_temp"),
            SettingsKey.GPU_CORE_TEMP_THRESHOLD: self.translator.translate("metric_gpu_core_temp"),
            SettingsKey.GPU_HOTSPOT_THRESHOLD: self.translator.translate("metric_gpu_hotspot_temp"),
            SettingsKey.GPU_MEMORY_TEMP_THRESHOLD: self.translator.translate("metric_gpu_mem_temp"),
            SettingsKey.VRAM_THRESHOLD: self.translator.translate("metric_vram_load"),
            SettingsKey.DISK_READ_THRESHOLD: self.translator.translate("metric_disk_read"),
            SettingsKey.DISK_WRITE_THRESHOLD: self.translator.translate("metric_disk_write"),
            SettingsKey.NET_UP_THRESHOLD: self.translator.translate("metric_net_upload"),
            SettingsKey.NET_DOWN_THRESHOLD: self.translator.translate("metric_net_download"),
            SettingsKey.GPU_CORE_CLOCK_THRESHOLD: self.translator.translate("metric_gpu_core_clock"),
            SettingsKey.GPU_MEMORY_CLOCK_THRESHOLD: self.translator.translate("metric_gpu_mem_clock"),
            SettingsKey.GPU_POWER_THRESHOLD: self.translator.translate("metric_gpu_power"),
        }

        sorted_keys = sorted(display_map, key=lambda key_enum: display_map[key_enum])

        for row, key_enum in enumerate(sorted_keys):
            key_str = key_enum.value
            label = self._build_threshold_label(display_map[key_enum], key_enum)
            value = self.settings_manager.get_setting(key_str, 0.0)
            display_value = self._to_display_threshold_value(key_enum, value)

            name_label = QLabel(label)
            value_input = QLineEdit(self._format_threshold_value(display_value))
            value_input.setValidator(double_validator)

            self.grid_layout.addWidget(name_label, row, 0)
            self.grid_layout.addWidget(value_input, row, 1)
            self.threshold_widgets[key_str] = value_input
            self.threshold_display_names[key_str] = label

    def save_and_apply(self):
        """Save thresholds in canonical units and close the window."""
        logging.info("Saving alarm thresholds.")
        updates = {}
        for key, line_edit in self.threshold_widgets.items():
            parsed_value = self._parse_threshold_input(line_edit.text())
            if parsed_value is None:
                logging.warning("Invalid threshold for %s: %s. Aborting save.", key, line_edit.text())
                self._show_invalid_threshold_error(key, line_edit)
                return

            key_enum = SettingsKey(key)
            updates[key] = self._to_storage_threshold_value(key_enum, parsed_value)

        self.settings_manager.update_settings(updates)
        logging.info("Alarm thresholds saved successfully.")
        self.close_safely()

    def _parse_threshold_input(self, value_text: str) -> float | None:
        normalized = value_text.strip().replace(",", ".")
        if not normalized:
            return None

        try:
            value = float(normalized)
        except ValueError:
            return None

        if not 0.0 <= value <= 99999.0:
            return None

        return value

    def _show_invalid_threshold_error(self, key: str, line_edit: QLineEdit):
        display_name = self.threshold_display_names.get(key, key)
        line_edit.setFocus()
        line_edit.selectAll()
        QMessageBox.warning(
            self,
            self.translator.translate("shared_error_title"),
            self.translator.translate("dlg_invalid_alarm_threshold_specific", metric=display_name),
        )

    def _build_threshold_label(self, display_name: str, key_enum: SettingsKey) -> str:
        unit_suffix = self._get_threshold_unit_suffix(key_enum)
        if not unit_suffix:
            return display_name

        base_name = re.sub(r"\s*\([^)]*\)\s*$", "", display_name).strip()
        return f"{base_name} ({unit_suffix})"

    def _get_threshold_unit_suffix(self, key_enum: SettingsKey) -> str:
        if key_enum in self.TEMPERATURE_THRESHOLD_KEYS:
            temperature_unit = self.settings_manager.get_setting(
                SettingsKey.TEMPERATURE_UNIT.value,
                TemperatureUnit.CELSIUS.value,
            )
            return "K" if temperature_unit == TemperatureUnit.KELVIN.value else "°C"
        if key_enum in self.DISK_IO_THRESHOLD_KEYS:
            return self.settings_manager.get_setting(
                SettingsKey.DISK_IO_UNIT.value,
                DiskIOUnit.MB_S.value,
            )
        if key_enum in self.NETWORK_THRESHOLD_KEYS:
            return self.settings_manager.get_setting(
                SettingsKey.NETWORK_UNIT.value,
                NetworkUnit.MBIT_S.value,
            )
        if key_enum in self.PERCENT_THRESHOLD_KEYS:
            return "%"
        if key_enum in self.CLOCK_THRESHOLD_KEYS:
            return "MHz"
        if key_enum == SettingsKey.GPU_POWER_THRESHOLD:
            return "W"
        return ""

    def _to_display_threshold_value(self, key_enum: SettingsKey, value: float) -> float:
        value = float(value)

        if key_enum in self.TEMPERATURE_THRESHOLD_KEYS:
            temperature_unit = self.settings_manager.get_setting(
                SettingsKey.TEMPERATURE_UNIT.value,
                TemperatureUnit.CELSIUS.value,
            )
            if temperature_unit == TemperatureUnit.KELVIN.value:
                return value + 273.15

        if key_enum in self.DISK_IO_THRESHOLD_KEYS:
            disk_io_unit = self.settings_manager.get_setting(
                SettingsKey.DISK_IO_UNIT.value,
                DiskIOUnit.MB_S.value,
            )
            if disk_io_unit == DiskIOUnit.GB_S.value:
                return value / 1024.0

        if key_enum in self.NETWORK_THRESHOLD_KEYS:
            network_unit = self.settings_manager.get_setting(
                SettingsKey.NETWORK_UNIT.value,
                NetworkUnit.MBIT_S.value,
            )
            if network_unit == NetworkUnit.GBIT_S.value:
                return value / 1000.0

        return value

    def _to_storage_threshold_value(self, key_enum: SettingsKey, value: float) -> float:
        value = float(value)

        if key_enum in self.TEMPERATURE_THRESHOLD_KEYS:
            temperature_unit = self.settings_manager.get_setting(
                SettingsKey.TEMPERATURE_UNIT.value,
                TemperatureUnit.CELSIUS.value,
            )
            if temperature_unit == TemperatureUnit.KELVIN.value:
                return value - 273.15

        if key_enum in self.DISK_IO_THRESHOLD_KEYS:
            disk_io_unit = self.settings_manager.get_setting(
                SettingsKey.DISK_IO_UNIT.value,
                DiskIOUnit.MB_S.value,
            )
            if disk_io_unit == DiskIOUnit.GB_S.value:
                return value * 1024.0

        if key_enum in self.NETWORK_THRESHOLD_KEYS:
            network_unit = self.settings_manager.get_setting(
                SettingsKey.NETWORK_UNIT.value,
                NetworkUnit.MBIT_S.value,
            )
            if network_unit == NetworkUnit.GBIT_S.value:
                return value * 1000.0

        return value

    def _format_threshold_value(self, value: float) -> str:
        formatted = f"{float(value):.2f}"
        return formatted.rstrip("0").rstrip(".")

    def export_language_refresh_state(self) -> dict:
        return {
            "threshold_values": {
                key: line_edit.text()
                for key, line_edit in self.threshold_widgets.items()
            }
        }

    def apply_language_refresh_state(self, state: dict):
        for key, value in state.get("threshold_values", {}).items():
            if key in self.threshold_widgets:
                self.threshold_widgets[key].setText(value)
