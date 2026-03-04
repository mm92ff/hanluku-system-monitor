# ui/widgets/custom_sensor_dialog.py
from PySide6.QtWidgets import (
    QVBoxLayout, QLabel, QLineEdit,
    QDialogButtonBox, QGroupBox, QFormLayout, QMessageBox
)
from .base_window import SafeDialog, configure_dialog_layout, configure_dialog_window, style_dialog_button

class CustomSensorDialog(SafeDialog):
    """Dialog zum Erstellen/Bearbeiten von Custom Sensors."""
    
    def __init__(self, parent, sensor_data=None):
        super().__init__(parent)
        self.sensor_data = sensor_data or {}
        self.translator = parent.translator
        
        self.setWindowTitle(self.translator.translate("win_custom_sensor_dialog_title"))
        configure_dialog_window(self, 420, 260, min_width=400, min_height=240)
        
        self._setup_ui()
        self._load_data()
    
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        configure_dialog_layout(layout)
        
        # Sensor Info Group
        info_group = QGroupBox(self.translator.translate("win_custom_sensor_group_info"))
        info_layout = QFormLayout(info_group)
        
        self.display_name_edit = QLineEdit()
        self.display_name_edit.setPlaceholderText(self.translator.translate("win_custom_sensor_placeholder_name"))
        info_layout.addRow(self.translator.translate("win_custom_sensor_label_display_name"), self.display_name_edit)
        
        self.identifier_edit = QLineEdit()
        self.identifier_edit.setPlaceholderText(self.translator.translate("win_custom_sensor_placeholder_identifier"))
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
        ok_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        cancel_button = self.button_box.button(QDialogButtonBox.StandardButton.Cancel)
        if ok_button is not None:
            style_dialog_button(ok_button, "primary")
        if cancel_button is not None:
            style_dialog_button(cancel_button, "secondary")
        self.button_box.accepted.connect(self._accept_if_valid)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)
    
    def _load_data(self):
        """Lädt Daten wenn vorhanden."""
        if self.sensor_data:
            suggested_name = f"{self.sensor_data.get('hardware_name', '')} - {self.sensor_data.get('sensor_name', '')}"
            self.display_name_edit.setText(self.sensor_data.get('display_name', suggested_name))
            identifier = self.sensor_data.get('identifier', '')
            self.identifier_edit.setText(identifier)
            self.identifier_edit.setReadOnly(bool(identifier))
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
        else:
            self.identifier_edit.setReadOnly(False)

    def _accept_if_valid(self):
        display_name = self.get_display_name()
        identifier = self.get_identifier()

        if not display_name:
            QMessageBox.warning(
                self,
                self.translator.translate("shared_error_title"),
                self.translator.translate("win_custom_sensor_error_name_required"),
            )
            self.display_name_edit.setFocus()
            return

        if not identifier:
            QMessageBox.warning(
                self,
                self.translator.translate("shared_error_title"),
                self.translator.translate("win_custom_sensor_error_identifier_required"),
            )
            self.identifier_edit.setFocus()
            return

        self.accept()

    def get_display_name(self):
        return self.display_name_edit.text().strip()

    def get_identifier(self):
        return self.identifier_edit.text().strip()
    
    def get_unit(self):
        return self.unit_edit.text().strip()
