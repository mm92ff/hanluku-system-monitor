from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Dict

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QColorDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from config import default_values
from config.constants import SettingsKey

from .base_window import (
    SafeWindow,
    configure_dialog_layout,
    configure_dialog_window,
    style_choice_button,
    style_color_preview_button,
    style_dialog_button,
    style_info_label,
    style_section_separator_label,
)

if TYPE_CHECKING:
    from core.main_window import SystemMonitor


class ColorPickerButton(QPushButton):
    """Button showing a color preview and opening a color dialog."""

    def __init__(self, initial_hex_color: str, target_line_edit: QLineEdit, parent=None):
        super().__init__("", parent)
        self.target_line_edit = target_line_edit
        self.setFixedSize(25, 25)
        self.set_color(initial_hex_color)
        self.clicked.connect(self.open_color_dialog)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_color(self, hex_color: str):
        """Update the preview color."""
        color = QColor(hex_color)
        valid_color = hex_color if color.isValid() else "#FF0000"
        style_color_preview_button(self, valid_color)

    def open_color_dialog(self):
        """Open the color picker dialog."""
        initial_color = QColor(self.target_line_edit.text())
        dialog = QColorDialog(initial_color, self.parent())
        dialog.setPalette(QApplication.instance().palette())
        dialog.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog, True)
        if dialog.exec():
            new_color = dialog.selectedColor().name().upper()
            self.set_color(new_color)
            self.target_line_edit.setText(new_color)


class ColorManagementWindow(SafeWindow):
    """Window for managing all application colors."""
    TABLE_HEADER_ROW = 0
    TABLE_DATA_START_ROW = 1
    COLUMN_PREVIEW = 0
    COLUMN_NAME = 1
    COLUMN_CURRENT_HEX = 2
    COLUMN_NEW_HEX = 3
    COLUMN_ALARM_HEX = 4

    def __init__(self, main_app: "SystemMonitor"):
        super().__init__(main_app)
        self.main_app = main_app
        self.translator = main_app.translator
        self.settings_manager = main_app.settings_manager
        self.setWindowTitle(self.translator.translate("win_title_color"))

        try:
            self.setWindowIcon(self.main_app.tray_icon_manager.tray_icon.icon())
        except AttributeError:
            self.setWindowIcon(QIcon())

        configure_dialog_window(self, 700, 950)
        self.color_widgets: Dict[str, Dict[str, QLineEdit]] = {}
        self.color_display_names: Dict[str, str] = {}
        self.selected_group = "cpu"
        self._init_ui()
        self._load_colors()

    def _init_ui(self):
        """Initialize the window UI."""
        main_layout = QVBoxLayout(self)
        configure_dialog_layout(main_layout, spacing=15)
        main_layout.setSpacing(15)

        global_text_section = QGroupBox(self.translator.translate("win_color_global_text_group"))
        global_text_layout = QVBoxLayout(global_text_section)
        configure_dialog_layout(global_text_layout, margins=(12, 12, 12, 12))

        info_text = QLabel(self.translator.translate("win_color_global_text_info"))
        style_info_label(info_text, "muted")
        global_text_layout.addWidget(info_text)

        text_input_layout = QHBoxLayout()
        text_input_layout.addWidget(QLabel(self.translator.translate("win_color_global_text_label")))

        self.global_color_input = QLineEdit("#FFFFFF")
        self.global_color_picker = ColorPickerButton("#FFFFFF", self.global_color_input, self)

        text_apply_button = QPushButton(self.translator.translate("win_color_global_text_apply_button"))
        text_apply_button.clicked.connect(self._apply_global_text_color)
        style_dialog_button(text_apply_button, "accent")

        text_input_layout.addWidget(self.global_color_picker)
        text_input_layout.addWidget(self.global_color_input)
        text_input_layout.addWidget(text_apply_button)
        text_input_layout.addStretch()

        global_text_layout.addLayout(text_input_layout)
        main_layout.addWidget(global_text_section)

        global_alarm_section = QGroupBox(self.translator.translate("win_color_global_alarm_group"))
        global_alarm_layout = QVBoxLayout(global_alarm_section)
        configure_dialog_layout(global_alarm_layout, margins=(12, 12, 12, 12))

        alarm_info_text = QLabel(self.translator.translate("win_color_global_alarm_info"))
        style_info_label(alarm_info_text, "muted")
        global_alarm_layout.addWidget(alarm_info_text)

        alarm_input_layout = QHBoxLayout()
        alarm_input_layout.addWidget(QLabel(self.translator.translate("win_color_global_alarm_label")))

        self.global_alarm_color_input = QLineEdit("#FF4500")
        self.global_alarm_color_picker = ColorPickerButton("#FF4500", self.global_alarm_color_input, self)

        alarm_apply_button = QPushButton(self.translator.translate("win_color_global_alarm_apply_button"))
        alarm_apply_button.clicked.connect(self._apply_global_alarm_color)
        style_dialog_button(alarm_apply_button, "accent")

        alarm_input_layout.addWidget(self.global_alarm_color_picker)
        alarm_input_layout.addWidget(self.global_alarm_color_input)
        alarm_input_layout.addWidget(alarm_apply_button)
        alarm_input_layout.addStretch()

        global_alarm_layout.addLayout(alarm_input_layout)
        main_layout.addWidget(global_alarm_section)

        group_section = QGroupBox(self.translator.translate("win_color_group_change_group"))
        group_layout = QVBoxLayout(group_section)
        configure_dialog_layout(group_layout, margins=(12, 12, 12, 12))
        group_layout.setSpacing(10)

        group_info_text = QLabel(self.translator.translate("win_color_group_change_info"))
        style_info_label(group_info_text, "muted")
        group_layout.addWidget(group_info_text)

        category_layout = QHBoxLayout()
        category_layout.addWidget(QLabel(self.translator.translate("win_color_category_label")))

        self.cpu_group_button = QPushButton(self.translator.translate("win_color_category_cpu"))
        self.gpu_group_button = QPushButton(self.translator.translate("win_color_category_gpu"))
        self.ram_group_button = QPushButton(self.translator.translate("win_color_category_ram"))
        self.storage_group_button = QPushButton(self.translator.translate("win_color_category_storage"))
        self.network_group_button = QPushButton(self.translator.translate("win_color_category_network"))

        for button in (
            self.cpu_group_button,
            self.gpu_group_button,
            self.ram_group_button,
            self.storage_group_button,
            self.network_group_button,
        ):
            style_choice_button(button, selected=False)

        self.cpu_group_button.clicked.connect(lambda: self._select_group("cpu"))
        self.gpu_group_button.clicked.connect(lambda: self._select_group("gpu"))
        self.ram_group_button.clicked.connect(lambda: self._select_group("ram"))
        self.storage_group_button.clicked.connect(lambda: self._select_group("storage"))
        self.network_group_button.clicked.connect(lambda: self._select_group("network"))

        category_layout.addWidget(self.cpu_group_button)
        category_layout.addWidget(self.gpu_group_button)
        category_layout.addWidget(self.ram_group_button)
        category_layout.addWidget(self.storage_group_button)
        category_layout.addWidget(self.network_group_button)
        category_layout.addStretch()

        group_layout.addLayout(category_layout)

        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel(self.translator.translate("win_color_new_color_label")))

        self.group_color_input = QLineEdit("#FFFFFF")
        self.group_color_picker = ColorPickerButton("#FFFFFF", self.group_color_input, self)

        color_layout.addWidget(self.group_color_picker)
        color_layout.addWidget(self.group_color_input)
        color_layout.addStretch()
        group_layout.addLayout(color_layout)

        gradient_layout = QHBoxLayout()
        self.gradient_checkbox = QCheckBox(self.translator.translate("win_color_gradient_checkbox"))
        self.gradient_checkbox.setChecked(False)
        gradient_layout.addWidget(self.gradient_checkbox)
        gradient_layout.addStretch()
        group_layout.addLayout(gradient_layout)

        group_button_layout = QHBoxLayout()
        self.apply_group_button = QPushButton(self.translator.translate("win_color_apply_to_category_button"))
        self.apply_group_button.clicked.connect(self._apply_group_color)
        style_dialog_button(self.apply_group_button, "accent")
        group_button_layout.addWidget(self.apply_group_button)
        group_button_layout.addStretch()
        group_layout.addLayout(group_button_layout)

        self._select_group("cpu")
        main_layout.addWidget(group_section)

        individual_section = QGroupBox(self.translator.translate("win_color_individual_group"))
        individual_layout = QVBoxLayout(individual_section)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        individual_layout.addWidget(scroll_area)

        container = QWidget()
        self.grid_layout = QGridLayout(container)
        self.grid_layout.setContentsMargins(8, 8, 8, 8)
        self.grid_layout.setHorizontalSpacing(12)
        self.grid_layout.setVerticalSpacing(6)
        self.grid_layout.setColumnMinimumWidth(self.COLUMN_PREVIEW, 34)
        self.grid_layout.setColumnStretch(self.COLUMN_NAME, 1)
        self.grid_layout.setColumnMinimumWidth(self.COLUMN_CURRENT_HEX, 110)
        self.grid_layout.setColumnMinimumWidth(self.COLUMN_NEW_HEX, 150)
        self.grid_layout.setColumnMinimumWidth(self.COLUMN_ALARM_HEX, 150)
        self._build_color_table_header()
        scroll_area.setWidget(container)

        main_layout.addWidget(individual_section)

        buttons_layout = QHBoxLayout()
        save_button = QPushButton(self.translator.translate("win_shared_button_save_close"))
        save_button.clicked.connect(self._save_and_close)
        style_dialog_button(save_button, "primary")

        cancel_button = QPushButton(self.translator.translate("win_shared_button_cancel"))
        cancel_button.clicked.connect(self.close_safely)
        style_dialog_button(cancel_button, "secondary")

        buttons_layout.addStretch()
        buttons_layout.addWidget(save_button)
        buttons_layout.addWidget(cancel_button)
        main_layout.addLayout(buttons_layout)

    def _build_color_table_header(self):
        """Build the individual colors table header inside the same grid as the data rows."""
        header_labels = {
            self.COLUMN_PREVIEW: self.translator.translate("win_color_preview"),
            self.COLUMN_NAME: self.translator.translate("win_color_name"),
            self.COLUMN_CURRENT_HEX: self.translator.translate("win_color_current_hex"),
            self.COLUMN_NEW_HEX: self.translator.translate("win_color_new_hex"),
            self.COLUMN_ALARM_HEX: self.translator.translate("win_color_alarm_hex"),
        }

        for column, text in header_labels.items():
            header_label = QLabel(f"<b>{text}</b>")
            alignment = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
            self.grid_layout.addWidget(header_label, self.TABLE_HEADER_ROW, column, alignment=alignment)

    def _select_group(self, group_name):
        """Select a color category and highlight the active button."""
        self.selected_group = group_name

        button_map = {
            "cpu": self.cpu_group_button,
            "gpu": self.gpu_group_button,
            "ram": self.ram_group_button,
            "storage": self.storage_group_button,
            "network": self.network_group_button,
        }
        for name, button in button_map.items():
            style_choice_button(button, selected=(name == group_name))

    def _lighten_color(self, hex_color, factor):
        """Return a lighter version of a hex color."""
        color = QColor(hex_color)
        if not color.isValid():
            return hex_color

        r, g, b = color.red(), color.green(), color.blue()
        r = int(r + (255 - r) * factor)
        g = int(g + (255 - g) * factor)
        b = int(b + (255 - b) * factor)
        return f"#{r:02X}{g:02X}{b:02X}"

    def _apply_global_text_color(self):
        """Apply the same text color to all non-alarm text colors."""
        global_color = self.global_color_input.text().strip()
        if not global_color:
            QMessageBox.warning(
                self,
                self.translator.translate("shared_error_title"),
                self.translator.translate("dlg_invalid_hex_color"),
            )
            return

        if not QColor(global_color).isValid():
            QMessageBox.warning(
                self,
                self.translator.translate("shared_error_title"),
                self.translator.translate("dlg_invalid_hex_color_specific", color=global_color),
            )
            return

        excluded_keys = [
            SettingsKey.TRAY_ICON_COLOR.value,
            SettingsKey.TRAY_BORDER_COLOR.value,
            SettingsKey.TRAY_TEXT_COLOR.value,
            SettingsKey.BACKGROUND_COLOR.value,
        ]

        for key_str, widgets in self.color_widgets.items():
            if "new_color" in widgets and not key_str.endswith("_alarm_color") and key_str not in excluded_keys:
                widgets["new_color"].setText(global_color)

    def _apply_global_alarm_color(self):
        """Apply the same alarm color to all alarm color fields."""
        global_alarm_color = self.global_alarm_color_input.text().strip()
        if not global_alarm_color:
            QMessageBox.warning(
                self,
                self.translator.translate("shared_error_title"),
                self.translator.translate("dlg_invalid_hex_color"),
            )
            return

        if not QColor(global_alarm_color).isValid():
            QMessageBox.warning(
                self,
                self.translator.translate("shared_error_title"),
                self.translator.translate("dlg_invalid_hex_color_specific", color=global_alarm_color),
            )
            return

        for widgets in self.color_widgets.values():
            if "alarm_color" in widgets:
                widgets["alarm_color"].setText(global_alarm_color)

    def _apply_group_color(self):
        """Apply a color to the currently selected category."""
        group_color = self.group_color_input.text().strip()
        selected_group = self.selected_group

        if not group_color:
            QMessageBox.warning(
                self,
                self.translator.translate("shared_error_title"),
                self.translator.translate("dlg_invalid_hex_color"),
            )
            return

        if not QColor(group_color).isValid():
            QMessageBox.warning(
                self,
                self.translator.translate("shared_error_title"),
                self.translator.translate("dlg_invalid_hex_color_specific", color=group_color),
            )
            return

        group_mappings = {
            "cpu": [
                SettingsKey.CPU_COLOR.value,
                SettingsKey.CPU_TEMP_COLOR.value,
            ],
            "gpu": [
                SettingsKey.GPU_CORE_TEMP_COLOR.value,
                SettingsKey.GPU_HOTSPOT_COLOR.value,
                SettingsKey.GPU_MEMORY_TEMP_COLOR.value,
                SettingsKey.GPU_VRAM_COLOR.value,
                SettingsKey.GPU_CORE_CLOCK_COLOR.value,
                SettingsKey.GPU_MEMORY_CLOCK_COLOR.value,
                SettingsKey.GPU_POWER_COLOR.value,
            ],
            "ram": [
                SettingsKey.RAM_COLOR.value,
            ],
            "storage": [
                SettingsKey.DISK_COLOR.value,
                SettingsKey.STORAGE_TEMP_COLOR.value,
                SettingsKey.DISK_IO_COLOR.value,
            ],
            "network": [
                SettingsKey.NET_COLOR.value,
            ],
        }

        if selected_group not in group_mappings:
            QMessageBox.warning(
                self,
                self.translator.translate("shared_error_title"),
                self.translator.translate("dlg_color_unknown_category"),
            )
            return

        affected_keys = group_mappings[selected_group]
        use_gradient = self.gradient_checkbox.isChecked()

        for index, key_str in enumerate(affected_keys):
            if key_str in self.color_widgets and "new_color" in self.color_widgets[key_str]:
                if use_gradient and len(affected_keys) > 1:
                    factor = (index / (len(affected_keys) - 1)) * 0.6
                    color_to_use = self._lighten_color(group_color, factor)
                else:
                    color_to_use = group_color
                self.color_widgets[key_str]["new_color"].setText(color_to_use)

    def _load_colors(self):
        """Load colors from settings and build the editor rows."""
        display_map = {
            SettingsKey.BACKGROUND_COLOR: self.translator.translate("color_name_background"),
            SettingsKey.CPU_COLOR: self.translator.translate("color_name_cpu"),
            SettingsKey.CPU_TEMP_COLOR: self.translator.translate("color_name_cpu_temp"),
            SettingsKey.RAM_COLOR: self.translator.translate("color_name_ram"),
            SettingsKey.DISK_COLOR: self.translator.translate("color_name_disk"),
            SettingsKey.STORAGE_TEMP_COLOR: self.translator.translate("color_name_storage_temp"),
            SettingsKey.DISK_IO_COLOR: self.translator.translate("color_name_disk_io"),
            SettingsKey.NET_COLOR: self.translator.translate("color_name_net"),
            SettingsKey.GPU_CORE_TEMP_COLOR: self.translator.translate("color_name_gpu_core_temp"),
            SettingsKey.GPU_HOTSPOT_COLOR: self.translator.translate("color_name_gpu_hotspot"),
            SettingsKey.GPU_MEMORY_TEMP_COLOR: self.translator.translate("color_name_gpu_mem_temp"),
            SettingsKey.GPU_VRAM_COLOR: self.translator.translate("color_name_vram"),
            SettingsKey.GPU_CORE_CLOCK_COLOR: self.translator.translate("color_name_gpu_core_clock"),
            SettingsKey.GPU_MEMORY_CLOCK_COLOR: self.translator.translate("color_name_gpu_mem_clock"),
            SettingsKey.GPU_POWER_COLOR: self.translator.translate("color_name_gpu_power"),
            SettingsKey.TRAY_ICON_COLOR: self.translator.translate("color_name_tray_icon"),
            SettingsKey.TRAY_BORDER_COLOR: self.translator.translate("color_name_tray_border"),
            SettingsKey.TRAY_TEXT_COLOR: self.translator.translate("color_name_tray_text"),
        }

        row = self.TABLE_DATA_START_ROW
        for key, name in display_map.items():
            self._add_color_row(row, key.value, name, True)
            row += 1

        custom_sensors = self.settings_manager.get_setting(SettingsKey.CUSTOM_SENSORS.value, {})
        if custom_sensors:
            separator_label = QLabel(f"<b>{self.translator.translate('menu_custom_sensors')}</b>")
            style_section_separator_label(separator_label)
            self.grid_layout.addWidget(separator_label, row, 0, 1, 5)
            row += 1

            for sensor_id, sensor_data in custom_sensors.items():
                if sensor_data.get("enabled", True):
                    display_name = sensor_data.get(
                        "display_name",
                        self.translator.translate("custom_sensor_fallback_name", id=sensor_id),
                    )
                    storage_key = f"custom_sensor|{sensor_id}"
                    self._add_color_row(row, storage_key, display_name, False, sensor_data.get("color", "#FFFFFF"))
                    row += 1

    def _add_color_row(self, row, storage_key, display_name, has_alarm, current_hex=None):
        """Add one editable color row."""
        if current_hex is None:
            current_hex = self.settings_manager.get_setting(storage_key, "#FFFFFF")

        new_color_input = QLineEdit(current_hex)
        color_picker = ColorPickerButton(current_hex, new_color_input, self)
        current_hex_label = QLabel(current_hex)
        current_hex_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        new_color_input.textChanged.connect(color_picker.set_color)

        self.grid_layout.addWidget(color_picker, row, self.COLUMN_PREVIEW, alignment=Qt.AlignmentFlag.AlignLeft)
        self.grid_layout.addWidget(QLabel(display_name), row, self.COLUMN_NAME)
        self.grid_layout.addWidget(current_hex_label, row, self.COLUMN_CURRENT_HEX)

        new_color_layout = QHBoxLayout()
        new_color_layout.setContentsMargins(0, 0, 0, 0)
        new_color_layout.addWidget(new_color_input)
        self.grid_layout.addLayout(new_color_layout, row, self.COLUMN_NEW_HEX)

        widgets = {"new_color": new_color_input}

        if has_alarm:
            alarm_key_str = storage_key.replace("_color", "_alarm_color")
            if alarm_key_str in default_values.DEFAULT_SETTINGS_BASE:
                alarm_hex = self.settings_manager.get_setting(alarm_key_str, "#FF4500")
                alarm_color_input = QLineEdit(alarm_hex)
                alarm_color_picker = ColorPickerButton(alarm_hex, alarm_color_input, self)
                alarm_color_input.textChanged.connect(alarm_color_picker.set_color)

                alarm_color_layout = QHBoxLayout()
                alarm_color_layout.setContentsMargins(0, 0, 0, 0)
                alarm_color_layout.addWidget(alarm_color_picker)
                alarm_color_layout.addWidget(alarm_color_input)
                self.grid_layout.addLayout(alarm_color_layout, row, self.COLUMN_ALARM_HEX, alignment=Qt.AlignmentFlag.AlignLeft)

                widgets["alarm_color"] = alarm_color_input

        self.color_widgets[storage_key] = widgets
        self.color_display_names[storage_key] = display_name
        if has_alarm:
            self.color_display_names[storage_key.replace("_color", "_alarm_color")] = f"{display_name} Alarm"

    def _validate_hex_input(self, field_name: str, line_edit: QLineEdit) -> str | None:
        """Validate one hex input. Abort save on empty or invalid values."""
        color_value = line_edit.text().strip().upper()
        if not color_value:
            line_edit.setFocus()
            line_edit.selectAll()
            QMessageBox.warning(
                self,
                self.translator.translate("shared_error_title"),
                self.translator.translate("dlg_invalid_hex_color"),
            )
            logging.warning("Color value for '%s' is empty. Aborting save.", field_name)
            return None

        if not QColor(color_value).isValid():
            line_edit.setFocus()
            line_edit.selectAll()
            QMessageBox.warning(
                self,
                self.translator.translate("shared_error_title"),
                self.translator.translate("dlg_invalid_hex_color_specific", color=color_value),
            )
            logging.warning("Color value for '%s' is invalid: %s. Aborting save.", field_name, color_value)
            return None

        return color_value

    def _save_and_close(self):
        """Save all changed colors and close the window."""
        try:
            updates = {}
            custom_sensors = self.settings_manager.get_setting(SettingsKey.CUSTOM_SENSORS.value, {})
            custom_sensors_changed = False

            for key_str, widgets in self.color_widgets.items():
                if key_str.startswith("custom_sensor|"):
                    sensor_id = key_str.split("|")[1]
                    if sensor_id in custom_sensors:
                        field_name = self.color_display_names.get(key_str, key_str)
                        new_color = self._validate_hex_input(field_name, widgets["new_color"])
                        if new_color is None:
                            return
                        if custom_sensors[sensor_id].get("color") != new_color:
                            custom_sensors[sensor_id]["color"] = new_color
                            custom_sensors_changed = True
                else:
                    field_name = self.color_display_names.get(key_str, key_str)
                    new_color = self._validate_hex_input(field_name, widgets["new_color"])
                    if new_color is None:
                        return
                    updates[key_str] = new_color

                    if "alarm_color" in widgets:
                        alarm_key_str = key_str.replace("_color", "_alarm_color")
                        alarm_field_name = self.color_display_names.get(alarm_key_str, alarm_key_str)
                        alarm_color = self._validate_hex_input(alarm_field_name, widgets["alarm_color"])
                        if alarm_color is None:
                            return
                        updates[alarm_key_str] = alarm_color

            if custom_sensors_changed:
                updates[SettingsKey.CUSTOM_SENSORS.value] = custom_sensors

            if updates:
                self.settings_manager.update_settings(updates)

            self.main_app.ui_manager.apply_styles()
            self.main_app.tray_icon_manager.update_tray_icon()

            logging.info("Farbeinstellungen gespeichert und angewendet")
            self.close_safely()
        except Exception as e:
            logging.error(f"Fehler beim Speichern der Farbeinstellungen: {e}", exc_info=True)

    def export_language_refresh_state(self) -> dict:
        color_values = {}
        for key_str, widgets in self.color_widgets.items():
            color_values[key_str] = {
                "new_color": widgets["new_color"].text(),
            }
            if "alarm_color" in widgets:
                color_values[key_str]["alarm_color"] = widgets["alarm_color"].text()

        return {
            "global_color": self.global_color_input.text(),
            "global_alarm_color": self.global_alarm_color_input.text(),
            "group_color": self.group_color_input.text(),
            "gradient_enabled": self.gradient_checkbox.isChecked(),
            "selected_group": self.selected_group,
            "color_values": color_values,
        }

    def apply_language_refresh_state(self, state: dict):
        self.global_color_input.setText(state.get("global_color", self.global_color_input.text()))
        self.global_alarm_color_input.setText(state.get("global_alarm_color", self.global_alarm_color_input.text()))
        self.group_color_input.setText(state.get("group_color", self.group_color_input.text()))
        self.gradient_checkbox.setChecked(state.get("gradient_enabled", False))
        self._select_group(state.get("selected_group", "cpu"))

        for key_str, values in state.get("color_values", {}).items():
            if key_str not in self.color_widgets:
                continue
            widgets = self.color_widgets[key_str]
            widgets["new_color"].setText(values.get("new_color", widgets["new_color"].text()))
            if "alarm_color" in widgets:
                widgets["alarm_color"].setText(values.get("alarm_color", widgets["alarm_color"].text()))
