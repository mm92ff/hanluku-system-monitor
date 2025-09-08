# ui/widgets/misc_settings_window.py
import logging
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QGridLayout,
    QPushButton, QComboBox, QWidget, QSpinBox
)
from PySide6.QtGui import QIcon
from .base_window import SafeWindow
from config.constants import SettingsKey

class MiscSettingsWindow(SafeWindow):
    """Fenster zum Bearbeiten diverser Anzeige-Einstellungen."""

    def __init__(self, main_app):
        super().__init__(main_app)
        self.main_app = main_app
        self.translator = main_app.translator
        self.settings_manager = main_app.settings_manager
        self.setWindowTitle(self.translator.translate("win_title_misc"))

        try:
            self.setWindowIcon(self.main_app.tray_icon_manager.tray_icon.icon())
        except AttributeError:
            self.setWindowIcon(QIcon())

        self.setGeometry(300, 300, 450, 450)
        self.combo_boxes: dict[str, QComboBox] = {}
        self.init_ui()
        self.load_settings()

    def init_ui(self):
        """Initialisiert die Benutzeroberfläche."""
        main_layout = QVBoxLayout(self)
        grid_layout = QGridLayout()
        grid_layout.setColumnStretch(1, 1)

        settings_config = {
            SettingsKey.VALUE_FORMAT: ("win_misc_value_format", {
                "decimal": "win_misc_format_decimal", "integer": "win_misc_format_integer"
            }),
            SettingsKey.DISK_IO_DISPLAY_MODE: ("win_misc_disk_io_display", {
                "both": "win_misc_display_both", "read": "win_misc_display_read_only", "write": "win_misc_display_write_only"
            }),
            SettingsKey.NETWORK_DISPLAY_MODE: ("win_misc_network_display", {
                "both": "win_misc_display_both", "up": "win_misc_display_up_only", "down": "win_misc_display_down_only"
            }),
            SettingsKey.TEMPERATURE_UNIT: ("win_misc_temp_unit", {
                "C": "win_misc_unit_celsius", "K": "win_misc_unit_kelvin"
            }),
            SettingsKey.NETWORK_UNIT: ("win_misc_network_unit", {
                "MBit/s": "unit_mbit_s", "GBit/s": "unit_gbit_s"
            }),
            SettingsKey.DISK_IO_UNIT: ("win_misc_disk_io_unit", {
                "MB/s": "unit_mb_s", "GB/s": "unit_gb_s"
            })
        }

        for row, (key_enum, (label_key, options)) in enumerate(settings_config.items()):
            label = QLabel(self.translator.translate(label_key))
            combo_box = QComboBox()
            for value, text_key in options.items():
                display_text = self.translator.translate(text_key)
                combo_box.addItem(display_text, userData=value)
            
            grid_layout.addWidget(label, row, 0)
            grid_layout.addWidget(combo_box, row, 1)
            self.combo_boxes[key_enum.value] = combo_box
        
        row = len(settings_config)
        gap_label = QLabel(self.translator.translate("win_misc_docking_gap"))
        self.gap_spinbox = QSpinBox()
        self.gap_spinbox.setRange(0, 100)
        self.gap_spinbox.setSuffix(self.translator.translate("shared_unit_px"))
        grid_layout.addWidget(gap_label, row, 0)
        grid_layout.addWidget(self.gap_spinbox, row, 1)

        container_widget = QWidget()
        container_widget.setLayout(grid_layout)
        main_layout.addWidget(container_widget)
        main_layout.addStretch()

        button_layout = QHBoxLayout()
        save_button = QPushButton(self.translator.translate("win_shared_button_save_close"))
        save_button.clicked.connect(self.save_and_close)
        cancel_button = QPushButton(self.translator.translate("win_shared_button_cancel"))
        cancel_button.clicked.connect(self.close_safely)
        button_layout.addStretch()
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)
        main_layout.addLayout(button_layout)

    def load_settings(self):
        """Lädt die aktuellen Einstellungen und setzt die UI-Werte."""
        for key, combo_box in self.combo_boxes.items():
            current_value = self.settings_manager.get_setting(key)
            index = combo_box.findData(current_value)
            if index != -1:
                combo_box.setCurrentIndex(index)
        self.gap_spinbox.setValue(self.settings_manager.get_setting(SettingsKey.DOCKING_GAP.value, 1))

    def save_and_close(self):
        """Speichert die neuen Einstellungen und schließt das Fenster."""
        updates = {}
        for key, combo_box in self.combo_boxes.items():
            updates[key] = combo_box.currentData()
        
        new_gap = self.gap_spinbox.value()
        updates[SettingsKey.DOCKING_GAP.value] = new_gap
        
        self.settings_manager.update_settings(updates)
        
        if hasattr(self.main_app, 'detachable_manager'):
            self.main_app.detachable_manager.docker.set_gap(new_gap)
        
        self.close_safely()