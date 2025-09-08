# ui/widgets/custom_sensor_dialog.py
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
    QPushButton, QComboBox, QDialogButtonBox, QGroupBox, QFormLayout
)
from PySide6.QtGui import QColor
from ui.widgets.color_management_window import ColorPickerButton

class CustomSensorDialog(QDialog):
    """Dialog zum Erstellen/Bearbeiten von Custom Sensors."""
    
    def __init__(self, parent, sensor_data=None):
        super().__init__(parent)
        self.sensor_data = sensor_data or {}
        self.translator = parent.translator
        
        self.setWindowTitle(self.translator.translate("win_custom_sensor_dialog_title"))
        self.setMinimumWidth(400)
        
        self._setup_ui()
        self._load_data()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Sensor Info Group
        info_group = QGroupBox(self.translator.translate("win_custom_sensor_group_info"))
        info_layout = QFormLayout(info_group)
        
        self.display_name_edit = QLineEdit()
        self.display_name_edit.setPlaceholderText(self.translator.translate("win_custom_sensor_placeholder_name"))
        info_layout.addRow(self.translator.translate("win_custom_sensor_label_display_name"), self.display_name_edit)
        
        self.identifier_edit = QLineEdit()
        self.identifier_edit.setReadOnly(True)
        info_layout.addRow(self.translator.translate("win_custom_sensor_label_identifier"), self.identifier_edit)
        
        self.sensor_type_label = QLabel()
        info_layout.addRow(self.translator.translate("win_custom_sensor_label_type"), self.sensor_type_label)
        
        layout.addWidget(info_group)
        
        # Darstellungs-Optionen
        display_group = QGroupBox(self.translator.translate("win_custom_sensor_group_display"))
        display_layout = QFormLayout(display_group)
        
        # Einheit
        self.unit_edit = QLineEdit()
        self.unit_edit.setPlaceholderText(self.translator.translate("win_custom_sensor_placeholder_unit"))
        display_layout.addRow(self.translator.translate("win_custom_sensor_label_unit"), self.unit_edit)
        
        layout.addWidget(display_group)
        
        # Buttons
        self.button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)
    
    def _load_data(self):
        """Lädt Daten wenn vorhanden."""
        if self.sensor_data:
            suggested_name = f"{self.sensor_data.get('hardware_name', '')} - {self.sensor_data.get('sensor_name', '')}"
            self.display_name_edit.setText(self.sensor_data.get('display_name', suggested_name))
            self.identifier_edit.setText(self.sensor_data.get('identifier', ''))
            self.sensor_type_label.setText(self.sensor_data.get('sensor_type', ''))
            
            # Einheit basierend auf Sensor-Typ vorschlagen
            sensor_type = self.sensor_data.get('sensor_type', '')
            unit_suggestions = {
                'Temperature': self.translator.translate("unit_celsius"),
                'Voltage': self.translator.translate("unit_volt"), 
                'Fan': self.translator.translate("unit_rpm"),
                'Load': self.translator.translate("unit_percent"),
                'Clock': self.translator.translate("unit_megahertz"),
                'Power': self.translator.translate("unit_watt")
            }
            self.unit_edit.setText(self.sensor_data.get('unit', unit_suggestions.get(sensor_type, '')))
    
    def get_display_name(self):
        return self.display_name_edit.text().strip()
    
    def get_unit(self):
        return self.unit_edit.text().strip()