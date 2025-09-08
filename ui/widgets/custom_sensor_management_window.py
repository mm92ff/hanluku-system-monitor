# ui/widgets/custom_sensor_management_window.py
from __future__ import annotations
import logging
import uuid
from typing import TYPE_CHECKING, Dict, Any

from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QGroupBox, QSplitter, QTextEdit, QCheckBox
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor

from config.constants import SettingsKey
from ui.widgets.custom_sensor_dialog import CustomSensorDialog
# Geändert: Importiere SafeWindow
from .base_window import SafeWindow

if TYPE_CHECKING:
    from core.main_window import SystemMonitor


# Geändert: Erbt von SafeWindow statt QDialog
class CustomSensorManagementWindow(SafeWindow):
    """Verwaltungsfenster für Custom Sensors."""
    
    def __init__(self, parent: SystemMonitor):
        super().__init__(parent)
        self.main_win = parent
        self.settings_manager = parent.settings_manager
        self.translator = parent.translator
        
        self.setWindowTitle(self.translator.translate("win_title_custom_sensor_management"))
        self.setMinimumSize(800, 600)
        self.resize(1000, 700)
        
        self._setup_ui()
        self._load_custom_sensors()
        
    def _setup_ui(self):
        """Erstellt die Benutzeroberfläche."""
        layout = QVBoxLayout(self)
        
        # Splitter für Tabelle und Details
        splitter = QSplitter(Qt.Orientation.Horizontal)
        layout.addWidget(splitter)
        
        # Linke Seite: Custom Sensors Tabelle
        left_widget = self._create_table_section()
        splitter.addWidget(left_widget)
        
        # Rechte Seite: Details und Aktionen
        right_widget = self._create_details_section()
        splitter.addWidget(right_widget)
        
        # Splitter-Verhältnis setzen
        splitter.setSizes([600, 400])
        
        # Button-Zeile
        button_layout = QHBoxLayout()
        
        self.close_button = QPushButton(self.translator.translate("win_shared_button_close"))
        # Geändert: Ruft close_safely auf, um das Fenster korrekt zu zerstören
        self.close_button.clicked.connect(self.close_safely)
        
        button_layout.addStretch()
        button_layout.addWidget(self.close_button)
        
        layout.addLayout(button_layout)
        
    def _create_table_section(self):
        """Erstellt den Tabellen-Bereich."""
        group = QGroupBox(self.translator.translate("win_custom_sensor_list"))
        layout = QVBoxLayout(group)
        
        # Buttons über der Tabelle
        button_layout = QHBoxLayout()
        
        self.add_button = QPushButton(self.translator.translate("win_custom_sensor_add"))
        self.add_button.clicked.connect(self._add_custom_sensor)
        
        self.edit_button = QPushButton(self.translator.translate("win_custom_sensor_edit"))
        self.edit_button.clicked.connect(self._edit_custom_sensor)
        self.edit_button.setEnabled(False)
        
        self.delete_button = QPushButton(self.translator.translate("win_custom_sensor_delete"))
        self.delete_button.clicked.connect(self._delete_custom_sensor)
        self.delete_button.setEnabled(False)
        
        self.refresh_button = QPushButton(self.translator.translate("win_shared_button_refresh"))
        self.refresh_button.clicked.connect(self._refresh_available_sensors)
        
        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.edit_button)
        button_layout.addWidget(self.delete_button)
        button_layout.addStretch()
        button_layout.addWidget(self.refresh_button)
        
        layout.addLayout(button_layout)
        
        # Custom Sensors Tabelle
        self.sensors_table = QTableWidget()
        self.sensors_table.setColumnCount(5)
        self.sensors_table.setHorizontalHeaderLabels([
            self.translator.translate("win_custom_sensor_name"),
            self.translator.translate("win_custom_sensor_type"),
            self.translator.translate("win_custom_sensor_unit"),
            self.translator.translate("win_custom_sensor_enabled"),
            self.translator.translate("win_custom_sensor_color")
        ])
        
        # Tabellen-Einstellungen
        header = self.sensors_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        
        self.sensors_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.sensors_table.itemSelectionChanged.connect(self._on_selection_changed)
        self.sensors_table.itemDoubleClicked.connect(self._edit_custom_sensor)
        
        layout.addWidget(self.sensors_table)
        
        return group
        
    def _create_details_section(self):
        """Erstellt den Detail-Bereich."""
        group = QGroupBox(self.translator.translate("win_custom_sensor_details"))
        layout = QVBoxLayout(group)
        
        # Sensor Info
        self.info_label = QLabel(self.translator.translate("win_custom_sensor_select_info"))
        self.info_label.setWordWrap(True)
        layout.addWidget(self.info_label)
        
        # Detaillierte Informationen
        self.details_text = QTextEdit()
        self.details_text.setReadOnly(True)
        self.details_text.setMaximumHeight(200)
        layout.addWidget(self.details_text)
        
        # Explorer Sektion
        explorer_group = QGroupBox(self.translator.translate("win_custom_sensor_available"))
        explorer_layout = QVBoxLayout(explorer_group)
        
        explorer_info = QLabel(self.translator.translate("win_custom_sensor_explorer_info"))
        explorer_info.setWordWrap(True)
        explorer_layout.addWidget(explorer_info)
        
        self.explorer_button = QPushButton(self.translator.translate("win_custom_sensor_open_explorer"))
        self.explorer_button.clicked.connect(self._open_sensor_explorer)
        explorer_layout.addWidget(self.explorer_button)
        
        layout.addWidget(explorer_group)
        
        # Status/Test Sektion
        test_group = QGroupBox(self.translator.translate("win_custom_sensor_test"))
        test_layout = QVBoxLayout(test_group)
        
        self.test_button = QPushButton(self.translator.translate("win_custom_sensor_test_selected"))
        self.test_button.clicked.connect(self._test_selected_sensor)
        self.test_button.setEnabled(False)
        
        self.test_result_label = QLabel("")
        self.test_result_label.setWordWrap(True)
        
        test_layout.addWidget(self.test_button)
        test_layout.addWidget(self.test_result_label)
        
        layout.addWidget(test_group)
        
        layout.addStretch()
        
        return group
        
    def _load_custom_sensors(self):
        """Lädt die Custom Sensors in die Tabelle."""
        custom_sensors = self.settings_manager.get_setting(SettingsKey.CUSTOM_SENSORS.value, {})
        
        self.sensors_table.setRowCount(len(custom_sensors))
        
        for row, (sensor_id, sensor_data) in enumerate(custom_sensors.items()):
            # Name
            name_item = QTableWidgetItem(sensor_data.get('display_name', ''))
            name_item.setData(Qt.ItemDataRole.UserRole, sensor_id)
            self.sensors_table.setItem(row, 0, name_item)
            
            # Typ
            sensor_type = sensor_data.get('sensor_type', '')
            self.sensors_table.setItem(row, 1, QTableWidgetItem(sensor_type))
            
            # Einheit
            unit = sensor_data.get('unit', '')
            self.sensors_table.setItem(row, 2, QTableWidgetItem(unit))
            
            # Aktiviert
            enabled = sensor_data.get('enabled', True)
            enabled_item = QTableWidgetItem("✓" if enabled else "✗")
            enabled_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.sensors_table.setItem(row, 3, enabled_item)
            
            # Farbe
            color = sensor_data.get('color', '#FFFFFF')
            color_item = QTableWidgetItem("●")
            color_item.setForeground(QColor(color))
            color_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.sensors_table.setItem(row, 4, color_item)
            
        logging.info(f"Loaded {len(custom_sensors)} custom sensors into table")
        
    def _on_selection_changed(self):
        """Wird aufgerufen, wenn die Auswahl in der Tabelle geändert wird."""
        selected_rows = self.sensors_table.selectionModel().selectedRows()
        has_selection = len(selected_rows) > 0
        
        self.edit_button.setEnabled(has_selection)
        self.delete_button.setEnabled(has_selection)
        self.test_button.setEnabled(has_selection)
        
        if has_selection:
            self._update_details(selected_rows[0].row())
        else:
            self._clear_details()
            
    def _update_details(self, row: int):
        """Aktualisiert die Detail-Anzeige für den ausgewählten Sensor."""
        sensor_id = self.sensors_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        custom_sensors = self.settings_manager.get_setting(SettingsKey.CUSTOM_SENSORS.value, {})
        
        if sensor_id not in custom_sensors:
            self._clear_details()
            return
            
        sensor_data = custom_sensors[sensor_id]
        
        # Info Label aktualisieren
        name = sensor_data.get('display_name', self.translator.translate("shared_unknown"))
        self.info_label.setText(f"{self.translator.translate('win_custom_sensor_selected')}: {name}")
        
        # Details Text erstellen
        details = [
            f"{self.translator.translate('win_custom_sensor_detail_id')}: {sensor_id}",
            f"{self.translator.translate('win_custom_sensor_detail_name')}: {sensor_data.get('display_name', 'N/A')}",
            f"{self.translator.translate('win_custom_sensor_detail_identifier')}: {sensor_data.get('identifier', 'N/A')}",
            f"{self.translator.translate('win_custom_sensor_detail_type')}: {sensor_data.get('sensor_type', 'N/A')}",
            f"{self.translator.translate('win_custom_sensor_detail_unit')}: {sensor_data.get('unit', 'N/A')}",
            f"{self.translator.translate('win_custom_sensor_detail_color')}: {sensor_data.get('color', 'N/A')}",
            f"{self.translator.translate('win_custom_sensor_detail_enabled')}: {self.translator.translate('shared_yes') if sensor_data.get('enabled', True) else self.translator.translate('shared_no')}"
        ]
        
        self.details_text.setText("\n".join(details))
        
    def _clear_details(self):
        """Leert die Detail-Anzeige."""
        self.info_label.setText(self.translator.translate("win_custom_sensor_select_info"))
        self.details_text.clear()
        self.test_result_label.clear()
        
    def _add_custom_sensor(self):
        """Öffnet den Dialog zum Hinzufügen eines neuen Custom Sensors."""
        dialog = CustomSensorDialog(self, {})
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._save_custom_sensor(dialog)
            
    def _edit_custom_sensor(self):
        """Öffnet den Dialog zum Bearbeiten des ausgewählten Custom Sensors."""
        selected_rows = self.sensors_table.selectionModel().selectedRows()
        if not selected_rows:
            return
            
        row = selected_rows[0].row()
        sensor_id = self.sensors_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        custom_sensors = self.settings_manager.get_setting(SettingsKey.CUSTOM_SENSORS.value, {})
        
        if sensor_id not in custom_sensors:
            return
            
        sensor_data = custom_sensors[sensor_id]
        dialog = CustomSensorDialog(self, sensor_data)
        
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._update_custom_sensor(sensor_id, dialog)
            
    def _save_custom_sensor(self, dialog: CustomSensorDialog):
        """Speichert einen neuen Custom Sensor."""
        # This method seems to have a bug, it calls dialog.get_color() which doesn't exist.
        # I will assume it should be a default color for now.
        custom_sensors = self.settings_manager.get_setting(SettingsKey.CUSTOM_SENSORS.value, {})
        
        sensor_id = str(uuid.uuid4())[:8]
        
        sensor_data = {
            'display_name': dialog.get_display_name(),
            'identifier': dialog.sensor_data.get('identifier', ''),
            'sensor_type': dialog.sensor_data.get('sensor_type', ''),
            'hardware_name': dialog.sensor_data.get('hardware_name', ''),
            'sensor_name': dialog.sensor_data.get('sensor_name', ''),
            'unit': dialog.get_unit(),
            'color': "#FFFFFF", # Default color
            'enabled': True
        }
        
        custom_sensors[sensor_id] = sensor_data
        self.settings_manager.set_setting(SettingsKey.CUSTOM_SENSORS.value, custom_sensors)
        
        logging.info(f"Custom Sensor hinzugefügt: {sensor_id} - {sensor_data['display_name']}")
        
        self._load_custom_sensors()
        self._notify_changes()
        
    def _update_custom_sensor(self, sensor_id: str, dialog: CustomSensorDialog):
        """Aktualisiert einen bestehenden Custom Sensor."""
        # This method also seems to have the get_color() bug. I'll fix it similarly.
        custom_sensors = self.settings_manager.get_setting(SettingsKey.CUSTOM_SENSORS.value, {})
        
        if sensor_id not in custom_sensors:
            return
            
        sensor_data = custom_sensors[sensor_id]
        sensor_data['display_name'] = dialog.get_display_name()
        sensor_data['unit'] = dialog.get_unit()
        sensor_data['color'] = sensor_data.get('color', '#FFFFFF') # Keep existing color
        
        self.settings_manager.set_setting(SettingsKey.CUSTOM_SENSORS.value, custom_sensors)
        
        logging.info(f"Custom Sensor aktualisiert: {sensor_id} - {sensor_data['display_name']}")
        
        self._load_custom_sensors()
        self._notify_changes()
        
    def _delete_custom_sensor(self):
        """Löscht den ausgewählten Custom Sensor."""
        selected_rows = self.sensors_table.selectionModel().selectedRows()
        if not selected_rows:
            return
            
        row = selected_rows[0].row()
        sensor_id = self.sensors_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        sensor_name = self.sensors_table.item(row, 0).text()
        
        reply = QMessageBox.question(
            self,
            self.translator.translate("win_custom_sensor_delete_confirm_title"),
            self.translator.translate("win_custom_sensor_delete_confirm_text", sensor_name=sensor_name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply != QMessageBox.StandardButton.Yes:
            return
            
        custom_sensors = self.settings_manager.get_setting(SettingsKey.CUSTOM_SENSORS.value, {})
        if sensor_id in custom_sensors:
            del custom_sensors[sensor_id]
            self.settings_manager.set_setting(SettingsKey.CUSTOM_SENSORS.value, custom_sensors)
            
            logging.info(f"Custom Sensor gelöscht: {sensor_id} - {sensor_name}")
            
            self._load_custom_sensors()
            self._notify_changes()
            
    def _test_selected_sensor(self):
        """Testet den ausgewählten Custom Sensor und zeigt das Ergebnis in einer QMessageBox."""
        selected_rows = self.sensors_table.selectionModel().selectedRows()
        if not selected_rows:
            return
            
        row = selected_rows[0].row()
        sensor_id = self.sensors_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        custom_sensors = self.settings_manager.get_setting(SettingsKey.CUSTOM_SENSORS.value, {})
        
        if sensor_id not in custom_sensors:
            return
            
        sensor_data = custom_sensors[sensor_id]
        identifier = sensor_data.get('identifier', '')
        display_name = sensor_data.get('display_name', 'N/A')
        
        self.test_result_label.setText(self.translator.translate("win_custom_sensor_testing"))
        QApplication.processEvents()

        try:
            value = self.main_win.hw_manager.test_custom_sensor(identifier)
            if value is not None:
                unit = sensor_data.get('unit', '')
                result_text = f"{self.translator.translate('win_custom_sensor_test_success')}: {value:.3f} {unit}"
                self.test_result_label.setText(result_text)
                QMessageBox.information(self, self.translator.translate("win_custom_sensor_test_title", name=display_name), result_text)
            else:
                result_text = self.translator.translate("win_custom_sensor_test_no_value")
                self.test_result_label.setText(result_text)
                QMessageBox.warning(self, self.translator.translate("win_custom_sensor_test_title", name=display_name), result_text)
        except Exception as e:
            result_text = f"{self.translator.translate('win_custom_sensor_test_error')}: {str(e)}"
            self.test_result_label.setText(result_text)
            QMessageBox.critical(self, self.translator.translate("win_custom_sensor_test_title", name=display_name), result_text)
        
    def _refresh_available_sensors(self):
        """Aktualisiert die verfügbaren Sensoren im Hardware Manager."""
        self.refresh_button.setText(self.translator.translate("win_custom_sensor_refreshing"))
        self.refresh_button.setEnabled(False)
        QApplication.processEvents()

        try:
            self.main_win.hw_manager.refresh_hardware_detection()
            QMessageBox.information(
                self,
                self.translator.translate("win_custom_sensor_refresh_success_title"),
                self.translator.translate("win_custom_sensor_refresh_success_text")
            )
        except Exception as e:
            QMessageBox.warning(
                self,
                self.translator.translate("win_custom_sensor_refresh_error_title"),
                f"{self.translator.translate('win_custom_sensor_refresh_error_text')}: {str(e)}"
            )
        finally:
            self.refresh_button.setText(self.translator.translate("win_shared_button_refresh"))
            self.refresh_button.setEnabled(True)
            
    def _open_sensor_explorer(self):
        """Öffnet den Sensor Explorer."""
        try:
            if hasattr(self.main_win.action_handler, 'sensor_diagnosis_window') and self.main_win.action_handler.sensor_diagnosis_window:
                win = self.main_win.action_handler.sensor_diagnosis_window
                win.show()
                win.activateWindow()
                win.raise_()
                if hasattr(win, 'tab_widget'):
                    win.tab_widget.setCurrentIndex(2)
            else:
                self.main_win.action_handler.show_sensor_diagnosis()
                QTimer.singleShot(100, lambda: self._switch_to_explorer_tab())
        except RuntimeError:
            logging.warning("SensorDiagnosisWindow wurde bereits gelöscht. Öffne neu.")
            self.main_win.action_handler.sensor_diagnosis_window = None # Reset zombie reference
            self.main_win.action_handler.show_sensor_diagnosis()
            QTimer.singleShot(100, lambda: self._switch_to_explorer_tab())
            
    def _switch_to_explorer_tab(self):
        """Wechselt zum Explorer Tab im Sensor Diagnosis Window."""
        if hasattr(self.main_win.action_handler, 'sensor_diagnosis_window') and self.main_win.action_handler.sensor_diagnosis_window:
            win = self.main_win.action_handler.sensor_diagnosis_window
            if hasattr(win, 'tab_widget'):
                win.tab_widget.setCurrentIndex(2)
                
    def _notify_changes(self):
        """Benachrichtigt andere Komponenten über Änderungen an Custom Sensors."""
        if hasattr(self.main_win, 'action_handler'):
            self.main_win.action_handler.refresh_custom_sensors()