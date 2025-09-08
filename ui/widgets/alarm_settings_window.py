# ui/widgets/alarm_settings_window.py
import logging
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QGridLayout,
    QPushButton, QLineEdit, QWidget
)
from PySide6.QtGui import QDoubleValidator, QIcon
from .base_window import SafeWindow
from config.constants import SettingsKey

class AlarmSettingsWindow(SafeWindow):
    """Fenster zum Bearbeiten der Alarmschwellenwerte."""
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
            logging.warning("Konnte Tray-Icon für Fenster nicht laden.")
            self.setWindowIcon(QIcon())

        self.setGeometry(350, 350, 400, 450)
        self.threshold_widgets = {}
        self.init_ui()
        self.load_thresholds()

    def init_ui(self):
        main_layout = QVBoxLayout(self)

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
        button_layout.addStretch()
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)
        main_layout.addLayout(button_layout)

    def load_thresholds(self):
        """Lädt die aktuellen Schwellenwerte und erstellt die Widgets."""
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
            SettingsKey.GPU_POWER_THRESHOLD: self.translator.translate("metric_gpu_power")
        }

        # Sortiere die Schlüssel nach dem übersetzten Anzeigenamen
        sorted_keys = sorted(display_map, key=lambda k: display_map[k])

        for row, key_enum in enumerate(sorted_keys):
            key_str = key_enum.value
            display_name = display_map[key_enum]
            
            value = self.settings_manager.get_setting(key_str, 0.0)
            name_label = QLabel(display_name)
            value_input = QLineEdit(str(value))
            value_input.setValidator(double_validator)

            self.grid_layout.addWidget(name_label, row, 0)
            self.grid_layout.addWidget(value_input, row, 1)
            self.threshold_widgets[key_str] = value_input

    def save_and_apply(self):
        """Speichert die geänderten Werte und schliesst das Fenster."""
        logging.info("Alarm-Schwellenwerte werden gespeichert.")
        updates = {}
        for key, line_edit in self.threshold_widgets.items():
            try:
                # Konvertiere Komma zu Punkt für float-Konvertierung
                value_str = line_edit.text().replace(',', '.')
                updates[key] = float(value_str)
            except ValueError:
                logging.warning(f"Ungültiger Wert für {key}: {line_edit.text()}. Ignoriere.")

        # Nutze update_settings für eine einzelne, atomare Speicheroperation
        self.settings_manager.update_settings(updates)
        logging.info("Alarm-Schwellenwerte erfolgreich gespeichert.")
        self.close_safely()