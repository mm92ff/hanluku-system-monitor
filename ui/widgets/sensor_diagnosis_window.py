# ui/widgets/sensor_diagnosis_window.py
import os
import logging
import csv
import uuid
from pathlib import Path
from datetime import datetime
from PySide6.QtWidgets import (
    QVBoxLayout, QTextEdit, QPushButton, QWidget, QHBoxLayout,
    QMessageBox, QComboBox, QLabel, QSplitter, QTabWidget,
    QTreeWidget, QTreeWidgetItem, QProgressBar, QApplication, QMenu,
    QDialog
)
from PySide6.QtCore import QDateTime, QThread, Signal, QTimer, Qt
from PySide6.QtGui import QFont, QAction
from .base_window import SafeWindow
from .custom_sensor_dialog import CustomSensorDialog

class DiagnosisWorkerThread(QThread):
    """Worker-Thread für aufwendige Diagnose-Operationen."""
    progress_updated = Signal(int)
    status_updated = Signal(str, str)
    diagnosis_completed = Signal(str)

    def __init__(self, main_app, diagnosis_type="full"):
        super().__init__()
        self.main_app = main_app
        self.hw_manager = main_app.hw_manager
        self.translator = main_app.translator
        self.diagnosis_type = diagnosis_type
        self.selected_hardware = None
        self.selected_sensor = None

    def set_specific_test(self, hardware_name: str, sensor_name: str):
        """Setzt Parameter für spezifische Sensor-Tests."""
        self.diagnosis_type = "specific"
        self.selected_hardware = hardware_name
        self.selected_sensor = sensor_name

    def run(self):
        """Führt die gewählte Diagnose durch."""
        try:
            if self.diagnosis_type == "full":
                self._run_full_diagnosis()
            elif self.diagnosis_type == "specific":
                self._run_specific_test()
            elif self.diagnosis_type == "cache_reset":
                self._run_cache_reset_test()
        except Exception as e:
            self.diagnosis_completed.emit(f"Fehler bei der Diagnose: {e}")

    def _run_full_diagnosis(self):
        """Führt eine vollständige Hardware-Diagnose durch."""
        self.progress_updated.emit(10)
        self.status_updated.emit("diag_status_collecting_hw", "")

        diagnosis = self.hw_manager.run_sensor_diagnosis()

        self.progress_updated.emit(50)
        self.status_updated.emit("diag_status_testing_sensors", "")

        test_sensors = [
            ("CPU_PACKAGE_TEMP", "metric_cpu_temp"),
            ("GPU_CORE_TEMP", "metric_gpu_core_temp"),
            ("GPU_HOTSPOT_TEMP", "metric_gpu_hotspot_temp"),
            ("GPU_MEMORY_TEMP", "metric_gpu_mem_temp")
        ]

        additional_tests = [f"\n=== {self.translator.translate('win_diag_report_header_recognition')} ==="]

        for i, (canonical_name, display_name_key) in enumerate(test_sensors):
            self.progress_updated.emit(50 + (i * 10))
            self.status_updated.emit("diag_status_testing_sensor", display_name_key)

            if self.hw_manager.computer:
                for hw in self.hw_manager.computer.Hardware:
                    hw_type = str(hw.HardwareType).lower()

                    if ((canonical_name.startswith("CPU") and "cpu" in hw_type) or
                        (canonical_name.startswith("GPU") and "gpu" in hw_type)):

                        test_result = self.hw_manager.test_sensor_recognition(canonical_name, hw.Name)
                        header = self.translator.translate('win_diag_report_header_specific_test', test_name=self.translator.translate(display_name_key), hardware_name=hw.Name)
                        additional_tests.append(f"\n--- {header} ---")
                        additional_tests.append(test_result)

        self.progress_updated.emit(90)
        self.status_updated.emit("diag_status_creating_report", "")

        complete_diagnosis = diagnosis + "\n" + "\n".join(additional_tests)

        self.progress_updated.emit(100)
        self.status_updated.emit("diag_status_done", "")
        self.diagnosis_completed.emit(complete_diagnosis)

    def _run_specific_test(self):
        """Führt einen spezifischen Sensor-Test durch."""
        self.progress_updated.emit(20)
        self.status_updated.emit("diag_status_running_specific_test", f"{self.selected_sensor} on {self.selected_hardware}")

        result = self.hw_manager.test_sensor_recognition(self.selected_sensor, self.selected_hardware)

        self.progress_updated.emit(100)
        self.status_updated.emit("diag_status_test_done", "")
        self.diagnosis_completed.emit(result)

    def _run_cache_reset_test(self):
        """Führt einen Cache-Reset und Neu-Erkennung durch."""
        self.progress_updated.emit(20)
        self.status_updated.emit("diag_status_resetting_cache", "")

        success = self.hw_manager.reset_sensor_cache()

        if success:
            self.progress_updated.emit(70)
            self.status_updated.emit("diag_status_redetecting", "")

            diagnosis = self.hw_manager.run_sensor_diagnosis()
            result = f"=== {self.translator.translate('win_diag_report_header_cache_reset')} ===\n"
            result += f"{self.translator.translate('win_diag_report_cache_reset_success')}\n\n"
            result += diagnosis
        else:
            result = self.translator.translate('win_diag_report_cache_reset_error')

        self.progress_updated.emit(100)
        self.status_updated.emit("diag_status_cache_reset_done", "")
        self.diagnosis_completed.emit(result)


class SensorDiagnosisWindow(SafeWindow):
    """Erweiterte Sensor-Diagnose mit interaktiven Test-Funktionen."""

    def __init__(self, main_app):
        super().__init__(main_app)
        self.main_app = main_app
        self.translator = main_app.translator
        self.setWindowTitle(self.translator.translate("win_title_diagnosis"))
        self.resize(800, 600)

        self.diagnosis_thread = None
        self.init_ui()

        QTimer.singleShot(100, self.run_full_diagnosis)

    def init_ui(self):
        """Initialisiert die erweiterte Benutzeroberfläche."""
        main_layout = QVBoxLayout(self)

        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        self.create_full_diagnosis_tab()
        self.create_specific_tests_tab()
        self.create_sensor_explorer_tab()
        self.create_cache_management_tab()

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        self.status_label = QLabel(self.translator.translate("win_diag_status_ready"))
        main_layout.addWidget(self.status_label)

        button_layout = QHBoxLayout()

        self.refresh_btn = QPushButton("🔄 " + self.translator.translate("win_diag_refresh_button"))
        self.refresh_btn.clicked.connect(self.run_full_diagnosis)
        button_layout.addWidget(self.refresh_btn)

        self.export_btn = QPushButton("💾 " + self.translator.translate("win_diag_export_button"))
        self.export_btn.clicked.connect(self.export_diagnosis)
        button_layout.addWidget(self.export_btn)

        button_layout.addStretch()

        close_btn = QPushButton(self.translator.translate("win_shared_button_close"))
        close_btn.clicked.connect(self.close_safely)
        button_layout.addWidget(close_btn)

        main_layout.addLayout(button_layout)

    def closeEvent(self, event):
        """Stellt sicher, dass die Signale des laufenden Threads getrennt werden, bevor das Fenster geschlossen wird."""
        if self.diagnosis_thread and self.diagnosis_thread.isRunning():
            logging.warning("Schließe Diagnose-Fenster, während Thread läuft. Trenne Signale.")
            try:
                self.diagnosis_thread.progress_updated.disconnect()
                self.diagnosis_thread.status_updated.disconnect()
                self.diagnosis_thread.diagnosis_completed.disconnect()
            except (TypeError, RuntimeError):
                pass
        super().closeEvent(event)

    def create_full_diagnosis_tab(self):
        """Erstellt das Tab für die vollständige Diagnose."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        info_label = QLabel(self.translator.translate("win_diag_full_diag_title"))
        info_label.setFont(QFont("", 10, QFont.Weight.Bold))
        layout.addWidget(info_label)

        self.full_diagnosis_text = QTextEdit()
        self.full_diagnosis_text.setReadOnly(True)
        self.full_diagnosis_text.setFont(QFont("Consolas", 9))
        layout.addWidget(self.full_diagnosis_text)

        self.tab_widget.addTab(tab, self.translator.translate("win_diag_tab_full"))

    def create_specific_tests_tab(self):
        """Erstellt das Tab für spezifische Sensor-Tests."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        config_layout = QVBoxLayout()

        config_layout.addWidget(QLabel(self.translator.translate("win_diag_specific_tests_title")))

        test_layout = QHBoxLayout()
        test_layout.addWidget(QLabel(self.translator.translate("win_diag_label_hardware")))

        self.hardware_combo = QComboBox()
        self.update_hardware_list()
        test_layout.addWidget(self.hardware_combo)

        test_layout.addWidget(QLabel(self.translator.translate("win_diag_label_sensor")))

        self.sensor_combo = QComboBox()
        sensor_options = [
            ("CPU_PACKAGE_TEMP", "metric_cpu_temp"), ("GPU_CORE_TEMP", "metric_gpu_core_temp"),
            ("GPU_HOTSPOT_TEMP", "metric_gpu_hotspot_temp"), ("GPU_MEMORY_TEMP", "metric_gpu_mem_temp"),
            ("GPU_CORE_CLOCK", "metric_gpu_core_clock"), ("GPU_MEMORY_CLOCK", "metric_gpu_mem_clock"),
            ("GPU_POWER", "metric_gpu_power")
        ]

        for sensor_id, key in sensor_options:
            self.sensor_combo.addItem(self.translator.translate(key), sensor_id)

        test_layout.addWidget(self.sensor_combo)

        self.test_btn = QPushButton("🧪 " + self.translator.translate("win_diag_start_test_button"))
        self.test_btn.clicked.connect(self.run_specific_test)
        test_layout.addWidget(self.test_btn)

        config_layout.addLayout(test_layout)
        layout.addLayout(config_layout)

        self.specific_test_text = QTextEdit()
        self.specific_test_text.setReadOnly(True)
        self.specific_test_text.setFont(QFont("Consolas", 9))
        layout.addWidget(self.specific_test_text)

        self.tab_widget.addTab(tab, self.translator.translate("win_diag_tab_specific"))

    def create_sensor_explorer_tab(self):
        """Erstellt das Tab für den Sensor Explorer."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        title_label = QLabel(self.translator.translate("win_diag_sensor_explorer_title"))
        title_label.setFont(QFont("", 10, QFont.Weight.Bold))
        layout.addWidget(title_label)

        # KORRIGIERT: Hardcodierter String durch Übersetzungsaufruf ersetzt
        hint_label = QLabel(self.translator.translate("win_diag_explorer_hint"))
        hint_label.setStyleSheet("font-size: 9pt; color: #aaa; margin-bottom: 5px;")
        layout.addWidget(hint_label)

        self.sensor_tree = QTreeWidget()
        self.sensor_tree.setHeaderLabels([
            self.translator.translate("win_diag_explorer_hardware"),
            self.translator.translate("win_diag_explorer_sensor_name"), 
            self.translator.translate("win_diag_explorer_type"),
            self.translator.translate("win_diag_explorer_value"),
            self.translator.translate("win_diag_explorer_identifier")
        ])
        self.sensor_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.sensor_tree.customContextMenuRequested.connect(self._show_sensor_context_menu)
        layout.addWidget(self.sensor_tree)

        button_layout = QHBoxLayout()
        
        self.refresh_explorer_btn = QPushButton("🔄 " + self.translator.translate("win_diag_refresh_explorer"))
        self.refresh_explorer_btn.clicked.connect(self._populate_sensor_tree)
        button_layout.addWidget(self.refresh_explorer_btn)

        self.export_all_btn = QPushButton("💾 " + self.translator.translate("win_diag_export_all_sensors"))
        self.export_all_btn.clicked.connect(self._export_all_sensors)
        button_layout.addWidget(self.export_all_btn)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        self.tab_widget.addTab(tab, self.translator.translate("win_diag_tab_explorer"))
        QTimer.singleShot(200, self._populate_sensor_tree)

    def create_cache_management_tab(self):
        """Erstellt das Tab für Cache-Verwaltung."""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        info_label = QLabel(self.translator.translate("win_diag_cache_management_title"))
        info_label.setFont(QFont("", 10, QFont.Weight.Bold))
        layout.addWidget(info_label)

        desc_label = QLabel(self.translator.translate("win_diag_cache_desc"))
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        cache_buttons = QHBoxLayout()

        self.cache_reset_btn = QPushButton("🗑️ " + self.translator.translate("win_diag_cache_reset_button"))
        self.cache_reset_btn.clicked.connect(self.reset_cache_and_diagnose)
        cache_buttons.addWidget(self.cache_reset_btn)

        self.clear_cache_btn = QPushButton("🧹 " + self.translator.translate("win_diag_cache_clear_button"))
        self.clear_cache_btn.clicked.connect(self.clear_sensor_cache)
        cache_buttons.addWidget(self.clear_cache_btn)

        layout.addLayout(cache_buttons)

        self.cache_info_text = QTextEdit()
        self.cache_info_text.setReadOnly(True)
        self.cache_info_text.setFont(QFont("Consolas", 9))
        self.load_cache_info()
        layout.addWidget(self.cache_info_text)

        self.tab_widget.addTab(tab, self.translator.translate("win_diag_tab_cache"))

    def _populate_sensor_tree(self):
        """Füllt den Sensor Tree rekursiv mit allen Geräten, Unter-Geräten und Sensoren."""
        self.sensor_tree.clear()
        self.sensor_tree.setUpdatesEnabled(False)
        
        if self.main_app.hw_manager.computer:
            for hw in self.main_app.hw_manager.computer.Hardware:
                hw.Update()
            for hw in self.main_app.hw_manager.computer.Hardware:
                self._add_hardware_to_tree(self.sensor_tree, hw)

        self.sensor_tree.resizeColumnToContents(0)
        self.sensor_tree.resizeColumnToContents(1)
        self.sensor_tree.resizeColumnToContents(2)
        self.sensor_tree.setUpdatesEnabled(True)

    def _add_hardware_to_tree(self, parent_item, hardware):
        """Fügt ein Hardware-Objekt und all seine Sensoren und Sub-Hardware rekursiv zum Baum hinzu."""
        hw_item = QTreeWidgetItem([hardware.Name, "", str(hardware.HardwareType), "", str(hardware.Identifier)])
        
        if isinstance(parent_item, QTreeWidgetItem):
            parent_item.addChild(hw_item)
        else:
            parent_item.addTopLevelItem(hw_item)

        for sensor in hardware.Sensors:
            value_str = f"{sensor.Value:.2f}" if sensor.Value is not None else "N/A"
            sensor_item = QTreeWidgetItem(["", sensor.Name, str(sensor.SensorType), value_str, str(sensor.Identifier)])
            sensor_item.setData(0, Qt.ItemDataRole.UserRole, {
                'hardware_name': hardware.Name,
                'sensor_name': sensor.Name,
                'sensor_type': str(sensor.SensorType),
                'identifier': str(sensor.Identifier),
                'current_value': sensor.Value
            })
            hw_item.addChild(sensor_item)

        for sub_hardware in hardware.SubHardware:
            sub_hardware.Update()
            self._add_hardware_to_tree(hw_item, sub_hardware)

    def _show_sensor_context_menu(self, position):
        """Zeigt Kontextmenü für Sensoren."""
        item = self.sensor_tree.itemAt(position)
        if not item or not item.data(0, Qt.ItemDataRole.UserRole):
            return

        sensor_data = item.data(0, Qt.ItemDataRole.UserRole)
        
        menu = QMenu(self)
        
        copy_id_action = QAction("📋 " + self.translator.translate("win_diag_copy_identifier"), self)
        copy_id_action.triggered.connect(lambda: QApplication.clipboard().setText(sensor_data['identifier']))
        menu.addAction(copy_id_action)
        
        add_custom_action = QAction("➕ " + self.translator.translate("win_diag_add_as_custom"), self)
        add_custom_action.triggered.connect(lambda: self._add_as_custom_sensor(sensor_data))
        menu.addAction(add_custom_action)
        
        menu.exec(self.sensor_tree.mapToGlobal(position))

    def _add_as_custom_sensor(self, sensor_data):
        """Öffnet Dialog zum Hinzufügen eines Custom Sensors."""
        dialog = CustomSensorDialog(self, sensor_data)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            custom_sensors = self.main_app.settings_manager.get_setting("custom_sensors", {})
            
            custom_key = str(uuid.uuid4())[:8]
            custom_sensors[custom_key] = {
                'identifier': sensor_data['identifier'],
                'display_name': dialog.get_display_name(),
                'sensor_type': sensor_data['sensor_type'],
                'color': '#FFFFFF',
                'unit': dialog.get_unit(),
                'enabled': True
            }
            
            self.main_app.settings_manager.set_setting("custom_sensors", custom_sensors)
            self.main_app.action_handler.refresh_custom_sensors()
            
            QMessageBox.information(self, 
                self.translator.translate("win_diag_custom_added_title"),
                self.translator.translate("win_diag_custom_added_text", name=dialog.get_display_name())
            )

    def _export_all_sensors(self):
        """Exportiert alle Sensoren in eine CSV-Datei."""
        from PySide6.QtWidgets import QFileDialog

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            self.translator.translate("win_diag_export_all_title"),
            f"all_sensors_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            self.translator.translate("shared_file_filter_csv")
        )

        if not file_path:
            return

        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                
                writer.writerow([
                    "Hardware", "Sensor Name", "Sensor Type", "Value", "Identifier", "Hardware Type"
                ])

                def write_hardware_recursively(hw):
                    hw.Update()
                    for sensor in hw.Sensors:
                        writer.writerow([
                            hw.Name, sensor.Name, str(sensor.SensorType),
                            sensor.Value if sensor.Value is not None else "N/A",
                            str(sensor.Identifier), str(hw.HardwareType)
                        ])
                    for sub_hw in hw.SubHardware:
                        write_hardware_recursively(sub_hw)

                if self.main_app.hw_manager.computer:
                    for hardware in self.main_app.hw_manager.computer.Hardware:
                        write_hardware_recursively(hardware)

            QMessageBox.information(self, 
                self.translator.translate("dlg_export_success_title"),
                self.translator.translate("win_diag_export_all_success", path=file_path)
            )

        except Exception as e:
            QMessageBox.critical(self,
                self.translator.translate("shared_error_title"), 
                self.translator.translate("win_diag_export_all_failed", error=e)
            )

    def update_hardware_list(self):
        """Aktualisiert die Hardware-Liste für spezifische Tests."""
        self.hardware_combo.clear()

        if self.main_app.hw_manager.computer:
            for hw in self.main_app.hw_manager.computer.Hardware:
                self.hardware_combo.addItem(f"{hw.Name} ({hw.HardwareType})", hw.Name)

    def load_cache_info(self):
        """Lädt und zeigt Cache-Informationen an."""
        cache = self.main_app.hw_manager.sensor_cache

        info_parts = [
            f"=== {self.translator.translate('win_diag_cache_info_header')} ===",
            f"{self.translator.translate('win_diag_cache_info_entries')}: {len(cache)}",
            ""
        ]

        if '_hardware_fingerprint' in cache:
            fingerprint = cache['_hardware_fingerprint']
            info_parts.append(f"{self.translator.translate('win_diag_cache_info_fingerprint')}: {fingerprint[:80]}...")
            info_parts.append("")

        info_parts.append(f"{self.translator.translate('win_diag_cache_info_cached_entries')}:")
        for key, value in cache.items():
            if not key.startswith('_'):
                info_parts.append(f"  {key}: {value}")

        self.cache_info_text.setPlainText("\n".join(info_parts))

    def run_full_diagnosis(self):
        """Startet die vollständige Diagnose im Worker-Thread."""
        if self.diagnosis_thread and self.diagnosis_thread.isRunning():
            return

        self.diagnosis_thread = DiagnosisWorkerThread(self.main_app, "full")
        self.diagnosis_thread.progress_updated.connect(self.update_progress)
        self.diagnosis_thread.status_updated.connect(self.update_status)
        self.diagnosis_thread.diagnosis_completed.connect(self.set_full_diagnosis_info)

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.refresh_btn.setEnabled(False)

        self.diagnosis_thread.start()

    def run_specific_test(self):
        """Startet einen spezifischen Sensor-Test."""
        if self.diagnosis_thread and self.diagnosis_thread.isRunning():
            return

        hardware_name = self.hardware_combo.currentData()
        sensor_name = self.sensor_combo.currentData()

        if not hardware_name or not sensor_name:
            QMessageBox.warning(self, self.translator.translate("shared_error_title"), self.translator.translate("win_diag_error_no_selection"))
            return

        self.diagnosis_thread = DiagnosisWorkerThread(self.main_app, "specific")
        self.diagnosis_thread.set_specific_test(hardware_name, sensor_name)
        self.diagnosis_thread.progress_updated.connect(self.update_progress)
        self.diagnosis_thread.status_updated.connect(self.update_status)
        self.diagnosis_thread.diagnosis_completed.connect(self.set_specific_test_info)

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.test_btn.setEnabled(False)

        self.diagnosis_thread.start()

    def reset_cache_and_diagnose(self):
        """Setzt den Cache zurück und führt eine neue Diagnose durch."""
        reply = QMessageBox.question(
            self,
            self.translator.translate("win_diag_reset_cache_title"),
            self.translator.translate("win_diag_reset_cache_text"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        if self.diagnosis_thread and self.diagnosis_thread.isRunning():
            return

        self.diagnosis_thread = DiagnosisWorkerThread(self.main_app, "cache_reset")
        self.diagnosis_thread.progress_updated.connect(self.update_progress)
        self.diagnosis_thread.status_updated.connect(self.update_status)
        self.diagnosis_thread.diagnosis_completed.connect(self.set_cache_reset_info)

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.cache_reset_btn.setEnabled(False)

        self.diagnosis_thread.start()

    def update_progress(self, value: int):
        """Aktualisiert den Fortschrittsbalken."""
        self.progress_bar.setValue(value)

    def update_status(self, key: str, param: str):
        """Aktualisiert den Status-Text."""
        if param:
            if param in self.translator.translations:
                param = self.translator.translate(param)
            text = self.translator.translate(key, value=param)
        else:
            text = self.translator.translate(key)
        self.status_label.setText(text)

    def set_diagnosis_info(self, info: str):
        """Kompatibilitätsmethode für action_handler - setzt Diagnose-Info im aktuellen Tab."""
        current_index = self.tab_widget.currentIndex()
        if current_index == 0:
            self.full_diagnosis_text.setPlainText(info)
        elif current_index == 1:
            self.specific_test_text.setPlainText(info)
        else:
            self.cache_info_text.setPlainText(info)

        if len(info) < 100:
            self.status_label.setText(info)

    def set_full_diagnosis_info(self, info: str):
        """Setzt die vollständigen Diagnose-Informationen."""
        self.full_diagnosis_text.setPlainText(info)
        self.progress_bar.setVisible(False)
        self.refresh_btn.setEnabled(True)
        self.update_status("diag_status_full_done", "")

    def set_specific_test_info(self, info: str):
        """Setzt die Ergebnisse des spezifischen Tests."""
        self.specific_test_text.setPlainText(info)
        self.progress_bar.setVisible(False)
        self.test_btn.setEnabled(True)
        self.update_status("diag_status_test_done", "")

    def set_cache_reset_info(self, info: str):
        """Setzt die Ergebnisse des Cache-Resets."""
        self.cache_info_text.setPlainText(info)
        self.load_cache_info()
        self.progress_bar.setVisible(False)
        self.cache_reset_btn.setEnabled(True)
        self.update_status("diag_status_cache_reset_done", "")

    def export_diagnosis(self):
        """Exportiert den Diagnose-Bericht in eine Datei."""
        from PySide6.QtWidgets import QFileDialog

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            self.translator.translate("win_diag_export_title"),
            f"sensor_diagnosis_{QDateTime.currentDateTime().toString('yyyy-MM-dd_hh-mm-ss')}.txt",
            f"{self.translator.translate('shared_text_files')} (*.txt);;{self.translator.translate('shared_all_files')} (*)"
        )

        if not file_path:
            return

        try:
            content_parts = [
                f"=== {self.translator.translate('win_diag_export_header')} ===",
                f"{self.translator.translate('win_diag_export_created_at')}: {QDateTime.currentDateTime().toString('dd.MM.yyyy hh:mm:ss')}",
                self.translator.translate('win_diag_export_system_info', system=os.name),
                "",
                f"=== {self.translator.translate('win_diag_tab_full').upper()} ===",
                self.full_diagnosis_text.toPlainText(),
                "",
                f"=== {self.translator.translate('win_diag_cache_info_header')} ===",
                self.cache_info_text.toPlainText()
            ]

            if self.specific_test_text.toPlainText():
                content_parts.extend([
                    "",
                    f"=== {self.translator.translate('win_diag_tab_specific').upper()} ===",
                    self.specific_test_text.toPlainText()
                ])

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write("\n".join(content_parts))

            QMessageBox.information(
                self,
                self.translator.translate("dlg_export_success_title"),
                self.translator.translate("win_diag_export_success_text", path=file_path)
            )

        except Exception as e:
            QMessageBox.critical(
                self,
                self.translator.translate("win_diag_export_error_title"),
                self.translator.translate("win_diag_export_error_text", error=e)
            )

    def clear_sensor_cache(self):
        """Löscht die sensor_cache.json Datei und bietet Programmneustart an."""
        reply = QMessageBox.question(
            self,
            self.translator.translate("dlg_clear_cache_title"),
            self.translator.translate("dlg_clear_cache_text"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            from config import config as app_config
            cache_file = Path(app_config.CONFIG_DIR) / 'sensor_cache.json'
            cache_deleted = False

            if cache_file.exists():
                cache_file.unlink()
                cache_deleted = True
                self.cache_info_text.append(f"\n{self.translator.translate('win_diag_cache_cleared_success')}")
            else:
                self.cache_info_text.append(f"\n{self.translator.translate('win_diag_cache_not_found')}")

            status_text = self.translator.translate('shared_deleted') if cache_deleted else self.translator.translate('shared_was_not_present')
            restart_text = self.translator.translate('dlg_restart_after_cache_clear_text', status=status_text)

            restart_reply = QMessageBox.question(
                self,
                self.translator.translate("msg_restart_title"),
                restart_text,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )

            if restart_reply == QMessageBox.StandardButton.Yes:
                self.main_app.restart_app()

        except Exception as e:
            logging.error(f"Fehler beim Löschen des Sensor-Cache: {e}", exc_info=True)
            error_text = self.translator.translate('shared_unexpected_error_text', error=e)
            QMessageBox.critical(self, self.translator.translate("shared_error_title"), error_text)