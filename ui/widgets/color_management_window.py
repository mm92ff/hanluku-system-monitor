# ui/widgets/color_management_window.py
from __future__ import annotations
import logging
from typing import TYPE_CHECKING, Dict

from PySide6.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QGridLayout, QColorDialog, QApplication, QWidget, QGroupBox, QMessageBox, QCheckBox
from PySide6.QtGui import QColor, QIcon
from PySide6.QtCore import Qt

from config import default_values
from .base_window import SafeWindow
from config.constants import SettingsKey


if TYPE_CHECKING:
    from core.main_window import SystemMonitor


class ColorPickerButton(QPushButton):
    """Ein Button, der eine Farbe anzeigt und den QColorDialog öffnet."""
    def __init__(self, initial_hex_color: str, target_line_edit: QLineEdit, parent=None):
        super().__init__("", parent)
        self.target_line_edit = target_line_edit
        self.setFixedSize(25, 25)
        self.set_color(initial_hex_color)
        self.clicked.connect(self.open_color_dialog)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def set_color(self, hex_color: str):
        """Setzt die Hintergrundfarbe des Buttons. Konsolidierte Fehlerbehandlung."""
        color = QColor(hex_color)
        valid_color = hex_color if color.isValid() else "#FF0000"
        self.setStyleSheet(f"background-color: {valid_color}; border: 1px solid #888;")

    def open_color_dialog(self):
        """Öffnet den Farbauswahldialog."""
        initial_color = QColor(self.target_line_edit.text())
        dialog = QColorDialog(initial_color, self.parent())
        dialog.setPalette(QApplication.instance().palette())
        dialog.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog, True)
        if dialog.exec():
            new_color = dialog.selectedColor().name().upper()
            self.set_color(new_color)
            self.target_line_edit.setText(new_color)


class ColorManagementWindow(SafeWindow):
    """Fenster zur Verwaltung aller Anwendungsfarben."""
    def __init__(self, main_app: SystemMonitor):
        super().__init__(main_app)
        self.main_app = main_app
        self.translator = main_app.translator
        self.settings_manager = main_app.settings_manager
        self.setWindowTitle(self.translator.translate("win_title_color"))

        try:
            self.setWindowIcon(self.main_app.tray_icon_manager.tray_icon.icon())
        except AttributeError:
            self.setWindowIcon(QIcon())

        self.setGeometry(300, 300, 700, 950)
        self.color_widgets: Dict[str, Dict[str, QLineEdit]] = {}
        self.selected_group = "CPU-Farben"
        self._init_ui()
        self._load_colors()

    def _init_ui(self):
        """Initialisiert die Benutzeroberfläche."""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)

        # Globale Textfarben-Sektion
        global_text_section = QGroupBox(self.translator.translate("win_color_global_text_group"))
        global_text_layout = QVBoxLayout(global_text_section)
        
        info_text = QLabel(self.translator.translate("win_color_global_text_info"))
        info_text.setWordWrap(True)
        global_text_layout.addWidget(info_text)
        
        text_input_layout = QHBoxLayout()
        text_input_layout.addWidget(QLabel(self.translator.translate("win_color_global_text_label")))
        
        self.global_color_input = QLineEdit("#FFFFFF")
        self.global_color_picker = ColorPickerButton("#FFFFFF", self.global_color_input, self)
        
        text_apply_button = QPushButton(self.translator.translate("win_color_global_text_apply_button"))
        text_apply_button.clicked.connect(self._apply_global_text_color)
        
        text_input_layout.addWidget(self.global_color_picker)
        text_input_layout.addWidget(self.global_color_input)
        text_input_layout.addWidget(text_apply_button)
        text_input_layout.addStretch()
        
        global_text_layout.addLayout(text_input_layout)
        main_layout.addWidget(global_text_section)

        # Globale Alarmfarben-Sektion
        global_alarm_section = QGroupBox(self.translator.translate("win_color_global_alarm_group"))
        global_alarm_layout = QVBoxLayout(global_alarm_section)
        
        alarm_info_text = QLabel(self.translator.translate("win_color_global_alarm_info"))
        alarm_info_text.setWordWrap(True)
        global_alarm_layout.addWidget(alarm_info_text)
        
        alarm_input_layout = QHBoxLayout()
        alarm_input_layout.addWidget(QLabel(self.translator.translate("win_color_global_alarm_label")))
        
        self.global_alarm_color_input = QLineEdit("#FF4500")
        self.global_alarm_color_picker = ColorPickerButton("#FF4500", self.global_alarm_color_input, self)
        
        alarm_apply_button = QPushButton(self.translator.translate("win_color_global_alarm_apply_button"))
        alarm_apply_button.clicked.connect(self._apply_global_alarm_color)
        
        alarm_input_layout.addWidget(self.global_alarm_color_picker)
        alarm_input_layout.addWidget(self.global_alarm_color_input)
        alarm_input_layout.addWidget(alarm_apply_button)
        alarm_input_layout.addStretch()
        
        global_alarm_layout.addLayout(alarm_input_layout)
        main_layout.addWidget(global_alarm_section)

        # Gruppen-Farbänderungs-Sektion
        group_section = QGroupBox(self.translator.translate("win_color_group_change_group"))
        group_layout = QVBoxLayout(group_section)
        group_layout.setSpacing(10)
        
        group_info_text = QLabel(self.translator.translate("win_color_group_change_info"))
        group_info_text.setWordWrap(True)
        group_layout.addWidget(group_info_text)
        
        # Kategorie-Auswahl Buttons
        category_layout = QHBoxLayout()
        category_layout.addWidget(QLabel(self.translator.translate("win_color_category_label")))
        
        self.cpu_group_button = QPushButton(self.translator.translate("win_color_category_cpu"))
        self.gpu_group_button = QPushButton(self.translator.translate("win_color_category_gpu"))
        self.ram_group_button = QPushButton(self.translator.translate("win_color_category_ram"))
        self.storage_group_button = QPushButton(self.translator.translate("win_color_category_storage"))
        self.network_group_button = QPushButton(self.translator.translate("win_color_category_network"))
        
        # Button-Styling
        button_style = "QPushButton { padding: 8px 16px; font-weight: bold; }"
        self.cpu_group_button.setStyleSheet(button_style)
        self.gpu_group_button.setStyleSheet(button_style)
        self.ram_group_button.setStyleSheet(button_style)
        self.storage_group_button.setStyleSheet(button_style)
        self.network_group_button.setStyleSheet(button_style)
        
        # Button-Verhalten
        self.cpu_group_button.clicked.connect(lambda: self._select_group("CPU-Farben"))
        self.gpu_group_button.clicked.connect(lambda: self._select_group("GPU-Farben"))
        self.ram_group_button.clicked.connect(lambda: self._select_group("RAM-Farben"))
        self.storage_group_button.clicked.connect(lambda: self._select_group("Speicher-Farben"))
        self.network_group_button.clicked.connect(lambda: self._select_group("Netzwerk-Farben"))
        
        category_layout.addWidget(self.cpu_group_button)
        category_layout.addWidget(self.gpu_group_button)
        category_layout.addWidget(self.ram_group_button)
        category_layout.addWidget(self.storage_group_button)
        category_layout.addWidget(self.network_group_button)
        category_layout.addStretch()
        
        group_layout.addLayout(category_layout)
        
        # Farbauswahl
        color_layout = QHBoxLayout()
        color_layout.addWidget(QLabel(self.translator.translate("win_color_new_color_label")))
        
        self.group_color_input = QLineEdit("#FFFFFF")
        self.group_color_picker = ColorPickerButton("#FFFFFF", self.group_color_input, self)
        
        color_layout.addWidget(self.group_color_picker)
        color_layout.addWidget(self.group_color_input)
        color_layout.addStretch()
        
        group_layout.addLayout(color_layout)
        
        # Verlauf-Option
        gradient_layout = QHBoxLayout()
        self.gradient_checkbox = QCheckBox(self.translator.translate("win_color_gradient_checkbox"))
        self.gradient_checkbox.setChecked(False)
        gradient_layout.addWidget(self.gradient_checkbox)
        gradient_layout.addStretch()
        
        group_layout.addLayout(gradient_layout)
        
        # Apply Button
        group_button_layout = QHBoxLayout()
        self.apply_group_button = QPushButton(self.translator.translate("win_color_apply_to_category_button"))
        self.apply_group_button.clicked.connect(self._apply_group_color)
        self.apply_group_button.setStyleSheet("QPushButton { padding: 10px; font-weight: bold; }")
        
        group_button_layout.addWidget(self.apply_group_button)
        group_button_layout.addStretch()
        
        group_layout.addLayout(group_button_layout)
        
        # Standard-Button aktivieren
        self._select_group("CPU-Farben")
        
        main_layout.addWidget(group_section)

        # Individuelle Farben-Sektion
        individual_section = QGroupBox(self.translator.translate("win_color_individual_group"))
        individual_layout = QVBoxLayout(individual_section)

        # Header
        header = QHBoxLayout()
        header.addWidget(QLabel(f'<b>{self.translator.translate("win_color_preview")}</b>'), 1)
        header.addWidget(QLabel(f'<b>{self.translator.translate("win_color_name")}</b>'), 4)
        header.addWidget(QLabel(f'<b>{self.translator.translate("win_color_current_hex")}</b>'), 2)
        header.addWidget(QLabel(f'<b>{self.translator.translate("win_color_new_hex")}</b>'), 3)
        header.addWidget(QLabel(f'<b>{self.translator.translate("win_color_alarm_hex")}</b>'), 3)
        individual_layout.addLayout(header)

        # Scrollable content
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        individual_layout.addWidget(scroll_area)

        container = QWidget()
        self.grid_layout = QGridLayout(container)
        self.grid_layout.setColumnStretch(1, 1)
        scroll_area.setWidget(container)

        main_layout.addWidget(individual_section)

        # Speichern/Abbrechen Buttons
        buttons_layout = QHBoxLayout()
        save_button = QPushButton(self.translator.translate("win_shared_button_save_close"))
        save_button.clicked.connect(self._save_and_close)
        save_button.setStyleSheet("QPushButton { padding: 10px; font-weight: bold; background-color: #4CAF50; color: white; }")
        
        cancel_button = QPushButton(self.translator.translate("win_shared_button_cancel"))
        cancel_button.clicked.connect(self.close_safely)
        cancel_button.setStyleSheet("QPushButton { padding: 10px; }")

        buttons_layout.addStretch()
        buttons_layout.addWidget(save_button)
        buttons_layout.addWidget(cancel_button)
        main_layout.addLayout(buttons_layout)

    def _select_group(self, group_name):
        """Wählt eine Gruppe aus und markiert den entsprechenden Button."""
        self.selected_group = group_name
        
        # Button-Styles
        normal_style = "QPushButton { padding: 8px 16px; font-weight: bold; }"
        selected_style = "QPushButton { padding: 8px 16px; font-weight: bold; background-color: #4CAF50; color: white; }"
        
        # Alle Buttons zurücksetzen
        self.cpu_group_button.setStyleSheet(normal_style)
        self.gpu_group_button.setStyleSheet(normal_style)
        self.ram_group_button.setStyleSheet(normal_style)
        self.storage_group_button.setStyleSheet(normal_style)
        self.network_group_button.setStyleSheet(normal_style)
        
        # Ausgewählten Button hervorheben
        if group_name == "CPU-Farben":
            self.cpu_group_button.setStyleSheet(selected_style)
        elif group_name == "GPU-Farben":
            self.gpu_group_button.setStyleSheet(selected_style)
        elif group_name == "RAM-Farben":
            self.ram_group_button.setStyleSheet(selected_style)
        elif group_name == "Speicher-Farben":
            self.storage_group_button.setStyleSheet(selected_style)
        elif group_name == "Netzwerk-Farben":
            self.network_group_button.setStyleSheet(selected_style)

    def _lighten_color(self, hex_color, factor):
        """Macht eine Hex-Farbe heller. Factor zwischen 0.0 und 1.0 (1.0 = weiß)."""
        color = QColor(hex_color)
        if not color.isValid():
            return hex_color
            
        r, g, b = color.red(), color.green(), color.blue()
        
        r = int(r + (255 - r) * factor)
        g = int(g + (255 - g) * factor)
        b = int(b + (255 - b) * factor)
        
        return f"#{r:02X}{g:02X}{b:02X}"

    def _apply_global_text_color(self):
        """Wendet die globale Textfarbe auf alle Text-Farben an."""
        global_color = self.global_color_input.text().strip()
        
        if not global_color:
            QMessageBox.warning(self, self.translator.translate("shared_error_title"), self.translator.translate("dlg_invalid_hex_color"))
            return
            
        test_color = QColor(global_color)
        if not test_color.isValid():
            QMessageBox.warning(self, self.translator.translate("shared_error_title"), self.translator.translate("dlg_invalid_hex_color_specific", color=global_color))
            return

        excluded_keys = [
            SettingsKey.TRAY_ICON_COLOR.value,
            SettingsKey.TRAY_BORDER_COLOR.value,
            SettingsKey.TRAY_TEXT_COLOR.value,
            SettingsKey.BACKGROUND_COLOR.value
        ]

        for key_str, widgets in self.color_widgets.items():
            if ("new_color" in widgets and 
                not key_str.endswith("_alarm_color") and 
                key_str not in excluded_keys):
                widgets["new_color"].setText(global_color)

    def _apply_global_alarm_color(self):
        """Wendet die globale Alarmfarbe auf alle Alarm-Farben an."""
        global_alarm_color = self.global_alarm_color_input.text().strip()
        
        if not global_alarm_color:
            QMessageBox.warning(self, self.translator.translate("shared_error_title"), self.translator.translate("dlg_invalid_hex_color"))
            return
            
        test_color = QColor(global_alarm_color)
        if not test_color.isValid():
            QMessageBox.warning(self, self.translator.translate("shared_error_title"), self.translator.translate("dlg_invalid_hex_color_specific", color=global_alarm_color))
            return

        for key_str, widgets in self.color_widgets.items():
            if "alarm_color" in widgets:
                widgets["alarm_color"].setText(global_alarm_color)

    def _apply_group_color(self):
        """Wendet eine Farbe auf alle Farben einer bestimmten Kategorie an."""
        group_color = self.group_color_input.text().strip()
        selected_group = self.selected_group
        
        if not group_color:
            QMessageBox.warning(self, self.translator.translate("shared_error_title"), self.translator.translate("dlg_invalid_hex_color"))
            return
            
        test_color = QColor(group_color)
        if not test_color.isValid():
            QMessageBox.warning(self, self.translator.translate("shared_error_title"), self.translator.translate("dlg_invalid_hex_color_specific", color=group_color))
            return

        group_mappings = {
            "CPU-Farben": [
                SettingsKey.CPU_COLOR.value,
                SettingsKey.CPU_TEMP_COLOR.value
            ],
            "GPU-Farben": [
                SettingsKey.GPU_CORE_TEMP_COLOR.value,
                SettingsKey.GPU_HOTSPOT_COLOR.value,
                SettingsKey.GPU_MEMORY_TEMP_COLOR.value,
                SettingsKey.GPU_VRAM_COLOR.value,
                SettingsKey.GPU_CORE_CLOCK_COLOR.value,
                SettingsKey.GPU_MEMORY_CLOCK_COLOR.value,
                SettingsKey.GPU_POWER_COLOR.value
            ],
            "RAM-Farben": [
                SettingsKey.RAM_COLOR.value
            ],
            "Speicher-Farben": [
                SettingsKey.DISK_COLOR.value,
                SettingsKey.STORAGE_TEMP_COLOR.value,
                SettingsKey.DISK_IO_COLOR.value
            ],
            "Netzwerk-Farben": [
                SettingsKey.NET_COLOR.value
            ]
        }

        if selected_group not in group_mappings:
            QMessageBox.warning(self, self.translator.translate("shared_error_title"), self.translator.translate("dlg_color_unknown_category"))
            return

        affected_keys = group_mappings[selected_group]
        use_gradient = self.gradient_checkbox.isChecked()
        
        for i, key_str in enumerate(affected_keys):
            if key_str in self.color_widgets and "new_color" in self.color_widgets[key_str]:
                if use_gradient and len(affected_keys) > 1:
                    factor = (i / (len(affected_keys) - 1)) * 0.6 if len(affected_keys) > 1 else 0.0
                    color_to_use = self._lighten_color(group_color, factor)
                else:
                    color_to_use = group_color
                    
                self.color_widgets[key_str]["new_color"].setText(color_to_use)

    def _load_colors(self):
        """Lädt die Farben aus den Einstellungen und baut die UI auf."""
        # Step 1: Standard-Sensoren laden
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
            SettingsKey.TRAY_TEXT_COLOR: self.translator.translate("color_name_tray_text")
        }

        row = 0
        for key, name in display_map.items():
            self._add_color_row(row, key.value, name, True)
            row += 1

        # Step 2: Custom Sensors dynamisch hinzufügen
        custom_sensors = self.settings_manager.get_setting(SettingsKey.CUSTOM_SENSORS.value, {})
        if custom_sensors:
            # Separator-Label für bessere Übersicht
            separator_label = QLabel(f"<b>{self.translator.translate('menu_custom_sensors')}</b>")
            separator_label.setStyleSheet("margin-top: 10px; padding-top: 5px; border-top: 1px solid #555;")
            self.grid_layout.addWidget(separator_label, row, 0, 1, 5) # Spanne über alle Spalten
            row += 1

            for sensor_id, sensor_data in custom_sensors.items():
                if sensor_data.get('enabled', True):
                    display_name = sensor_data.get('display_name', self.translator.translate("custom_sensor_fallback_name", id=sensor_id))
                    # Spezieller Schlüssel-Präfix, um Custom Sensors beim Speichern zu erkennen
                    storage_key = f"custom_sensor|{sensor_id}"
                    self._add_color_row(row, storage_key, display_name, False, sensor_data.get('color', '#FFFFFF'))
                    row += 1

    def _add_color_row(self, row, storage_key, display_name, has_alarm, current_hex=None):
        """Hilfsfunktion zum Erstellen einer Zeile im Grid."""
        if current_hex is None:
            current_hex = self.settings_manager.get_setting(storage_key, "#FFFFFF")

        new_color_input = QLineEdit(current_hex)
        color_picker = ColorPickerButton(current_hex, new_color_input, self)
        current_hex_label = QLabel(current_hex)
        new_color_input.textChanged.connect(color_picker.set_color)

        self.grid_layout.addWidget(color_picker, row, 0)
        self.grid_layout.addWidget(QLabel(display_name), row, 1)
        self.grid_layout.addWidget(current_hex_label, row, 2)
        
        new_color_layout = QHBoxLayout()
        new_color_layout.addWidget(new_color_input)
        self.grid_layout.addLayout(new_color_layout, row, 3)
        
        widgets = {"new_color": new_color_input}

        if has_alarm:
            alarm_key_str = storage_key.replace('_color', '_alarm_color')
            if alarm_key_str in default_values.DEFAULT_SETTINGS_BASE:
                alarm_hex = self.settings_manager.get_setting(alarm_key_str, "#FF4500")
                alarm_color_input = QLineEdit(alarm_hex)
                alarm_color_picker = ColorPickerButton(alarm_hex, alarm_color_input, self)
                alarm_color_input.textChanged.connect(alarm_color_picker.set_color)

                alarm_color_layout = QHBoxLayout()
                alarm_color_layout.addWidget(alarm_color_picker)
                alarm_color_layout.addWidget(alarm_color_input)
                self.grid_layout.addLayout(alarm_color_layout, row, 4, alignment=Qt.AlignmentFlag.AlignLeft)
                
                widgets["alarm_color"] = alarm_color_input

        self.color_widgets[storage_key] = widgets

    def _save_and_close(self):
        """Speichert alle geänderten Farben und schließt das Fenster."""
        try:
            updates = {}
            custom_sensors = self.settings_manager.get_setting(SettingsKey.CUSTOM_SENSORS.value, {})
            custom_sensors_changed = False

            for key_str, widgets in self.color_widgets.items():
                # Handling für Custom Sensors
                if key_str.startswith("custom_sensor|"):
                    sensor_id = key_str.split('|')[1]
                    if sensor_id in custom_sensors:
                        new_color = widgets["new_color"].text().strip()
                        if custom_sensors[sensor_id].get('color') != new_color:
                            custom_sensors[sensor_id]['color'] = new_color
                            custom_sensors_changed = True
                # Handling für Standard-Sensoren
                else:
                    if new_color := widgets["new_color"].text().strip():
                        updates[key_str] = new_color
                    
                    if "alarm_color" in widgets:
                        if alarm_color := widgets["alarm_color"].text().strip():
                            alarm_key_str = key_str.replace('_color', '_alarm_color')
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