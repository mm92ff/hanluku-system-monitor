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
from .base_window import (
    SafeWindow,
    configure_dialog_layout,
    configure_dialog_window,
    style_dialog_button,
    style_info_label,
)
from .custom_sensor_dialog import CustomSensorDialog
from config.constants import SettingsKey
from core.sensor_mapping import is_hardware_compatible


SPECIFIC_SENSOR_OPTIONS = [
    ("CPU_PACKAGE_TEMP", "metric_cpu_temp"),
    ("GPU_CORE_TEMP", "metric_gpu_core_temp"),
    ("GPU_HOTSPOT_TEMP", "metric_gpu_hotspot_temp"),
    ("GPU_MEMORY_TEMP", "metric_gpu_mem_temp"),
    ("GPU_CORE_CLOCK", "metric_gpu_core_clock"),
    ("GPU_MEMORY_CLOCK", "metric_gpu_mem_clock"),
    ("GPU_POWER", "metric_gpu_power"),
]


class DiagnosisWorkerThread(QThread):
    """Worker-Thread fÃ¼r aufwendige Diagnose-Operationen."""
    progress_updated = Signal(int)
    status_updated = Signal(str, str)
    diagnosis_completed = Signal(str)

    def __init__(self, main_app, diagnosis_type="full"):
        super().__init__()
        self.main_app = main_app
        self.hw_manager = main_app.hw_manager
        self.translator = main_app.translator
        self.diagnosis_type = diagnosis_type
        self.cache_reset_succeeded = False
        self.selected_hardware = None
        self.selected_sensor = None

    def set_specific_test(self, hardware_name: str, sensor_name: str):
        """Setzt Parameter fÃ¼r spezifische Sensor-Tests."""
        self.diagnosis_type = "specific"
        self.selected_hardware = hardware_name
        self.selected_sensor = sensor_name

    def run(self):
        """FÃ¼hrt die gewÃ¤hlte Diagnose durch."""
        try:
            if self.diagnosis_type == "full":
                self._run_full_diagnosis()
            elif self.diagnosis_type == "specific":
                self._run_specific_test()
            elif self.diagnosis_type == "all_specific":
                self._run_all_specific_tests()
            elif self.diagnosis_type == "cache_reset":
                self._run_cache_reset_test()
        except Exception as e:
            self.diagnosis_completed.emit(f"Fehler bei der Diagnose: {e}")

    def _run_full_diagnosis(self):
        """FÃ¼hrt eine vollstÃ¤ndige Hardware-Diagnose durch."""
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
        """FÃ¼hrt einen spezifischen Sensor-Test durch."""
        self.progress_updated.emit(20)
        self.status_updated.emit("diag_status_running_specific_test", f"{self.selected_sensor} on {self.selected_hardware}")

        result = self.hw_manager.test_sensor_recognition(self.selected_sensor, self.selected_hardware)

        self.progress_updated.emit(100)
        self.status_updated.emit("diag_status_test_done", "")
        self.diagnosis_completed.emit(result)

    def _get_all_specific_test_targets(self):
        """Liefert alle kompatiblen Hardware-/Sensor-Kombinationen für den Batchlauf."""
        if not self.hw_manager.computer:
            return []

        targets = []
        for canonical_name, display_name_key in SPECIFIC_SENSOR_OPTIONS:
            compatible_hardware = [
                hw for hw in self.hw_manager.computer.Hardware
                if is_hardware_compatible(canonical_name, hw)
            ]
            targets.append((canonical_name, display_name_key, compatible_hardware))
        return targets

    def _run_all_specific_tests(self):
        """Führt alle Specific-Tests nacheinander aus und sammelt einen Gesamtbericht."""
        self.progress_updated.emit(10)
        self.status_updated.emit("diag_status_testing_sensors", "")

        targets = self._get_all_specific_test_targets()
        runnable_targets = [
            (canonical_name, display_name_key, hardware)
            for canonical_name, display_name_key, hardware_list in targets
            for hardware in hardware_list
        ]

        report_parts = [f"=== {self.translator.translate('win_diag_all_tests_header')} ===", ""]

        for canonical_name, display_name_key, hardware_list in targets:
            display_name = self.translator.translate(display_name_key)
            if not hardware_list:
                report_parts.append(
                    self.translator.translate(
                        "win_diag_all_tests_no_compatible_hardware",
                        sensor_name=display_name,
                    )
                )
                report_parts.append("")

        total = len(runnable_targets)
        if total == 0:
            self.progress_updated.emit(100)
            self.status_updated.emit("diag_status_all_specific_tests_done", "")
            self.diagnosis_completed.emit("\n".join(report_parts).strip())
            return

        for index, (canonical_name, display_name_key, hardware) in enumerate(runnable_targets, start=1):
            progress = 10 + int((index / total) * 85)
            self.progress_updated.emit(progress)
            self.status_updated.emit("diag_status_testing_sensor", display_name_key)

            display_name = self.translator.translate(display_name_key)
            header = self.translator.translate(
                'win_diag_report_header_specific_test',
                test_name=display_name,
                hardware_name=hardware.Name,
            )
            report_parts.append(f"--- {header} ---")
            report_parts.append(self.hw_manager.test_sensor_recognition(canonical_name, hardware.Name))
            report_parts.append("")

        self.progress_updated.emit(100)
        self.status_updated.emit("diag_status_all_specific_tests_done", "")
        self.diagnosis_completed.emit("\n".join(report_parts).strip())

    def _run_cache_reset_test(self):
        """FÃ¼hrt einen Cache-Reset und Neu-Erkennung durch."""
        self.progress_updated.emit(20)
        self.status_updated.emit("diag_status_resetting_cache", "")

        operation_result = self.hw_manager.redetect_hardware(reset_cache=True)

        if operation_result.success:
            self.cache_reset_succeeded = True
            self.progress_updated.emit(70)
            self.status_updated.emit("diag_status_redetecting", "")

            diagnosis = self.hw_manager.run_sensor_diagnosis()
            result = f"=== {self.translator.translate('win_diag_report_header_cache_reset')} ===\n"
            result += f"{self.translator.translate('win_diag_report_cache_reset_success')}\n\n"
            result += diagnosis
        else:
            result = operation_result.message or self.translator.translate('win_diag_report_cache_reset_error')

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
        configure_dialog_window(self, 800, 600)

        self.diagnosis_thread = None
        self._worker_was_paused_for_diagnosis = False
        self._last_status_key = "win_diag_status_ready"
        self._last_status_param = ""
        self.init_ui()

        QTimer.singleShot(100, self.run_full_diagnosis)

    def init_ui(self):
        """Initialisiert die erweiterte BenutzeroberflÃ¤che."""
        main_layout = QVBoxLayout(self)
        configure_dialog_layout(main_layout)

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
        style_info_label(self.status_label, "muted")
        main_layout.addWidget(self.status_label)

        button_layout = QHBoxLayout()

        self.refresh_btn = QPushButton(self.translator.translate("win_diag_refresh_button"))
        self.refresh_btn.clicked.connect(self.run_full_diagnosis)
        style_dialog_button(self.refresh_btn, "accent")
        button_layout.addWidget(self.refresh_btn)

        self.export_btn = QPushButton(self.translator.translate("win_diag_export_button"))
        self.export_btn.clicked.connect(self.export_diagnosis)
        style_dialog_button(self.export_btn, "compact")
        button_layout.addWidget(self.export_btn)

        button_layout.addStretch()

        self.close_btn = QPushButton(self.translator.translate("win_shared_button_close"))
        self.close_btn.clicked.connect(self.close)
        style_dialog_button(self.close_btn, "secondary")
        button_layout.addWidget(self.close_btn)

        main_layout.addLayout(button_layout)

    def closeEvent(self, event):
        """Hält das Fenster bei laufender Diagnose verborgen, bis der Worker fertig ist."""
        if self.diagnosis_thread and self.diagnosis_thread.isRunning():
            logging.info("Diagnose läuft noch. Fenster wird verborgen und nach Abschluss weiterverwendet.")
            self.hide()
            event.ignore()
            return
        super().closeEvent(event)

    def create_full_diagnosis_tab(self):
        """Erstellt das Tab fÃ¼r die vollstÃ¤ndige Diagnose."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        configure_dialog_layout(layout, margins=(12, 12, 12, 12))

        self.full_diag_info_label = QLabel(self.translator.translate("win_diag_full_diag_title"))
        self.full_diag_info_label.setFont(QFont("", 10, QFont.Weight.Bold))
        layout.addWidget(self.full_diag_info_label)

        self.full_diagnosis_text = QTextEdit()
        self.full_diagnosis_text.setReadOnly(True)
        self.full_diagnosis_text.setFont(QFont("Consolas", 9))
        layout.addWidget(self.full_diagnosis_text)

        self.tab_widget.addTab(tab, self.translator.translate("win_diag_tab_full"))

    def create_specific_tests_tab(self):
        """Erstellt das Tab fÃ¼r spezifische Sensor-Tests."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        configure_dialog_layout(layout, margins=(12, 12, 12, 12))

        config_layout = QVBoxLayout()

        self.specific_tests_title_label = QLabel(self.translator.translate("win_diag_specific_tests_title"))
        config_layout.addWidget(self.specific_tests_title_label)

        test_layout = QHBoxLayout()
        self.hardware_label = QLabel(self.translator.translate("win_diag_label_hardware"))
        test_layout.addWidget(self.hardware_label)

        self.hardware_combo = QComboBox()
        test_layout.addWidget(self.hardware_combo)

        self.sensor_label = QLabel(self.translator.translate("win_diag_label_sensor"))
        test_layout.addWidget(self.sensor_label)

        self.sensor_combo = QComboBox()
        self._populate_sensor_options()

        self.sensor_combo.currentIndexChanged.connect(self.update_hardware_list)
        test_layout.addWidget(self.sensor_combo)

        self.test_btn = QPushButton(self.translator.translate("win_diag_start_test_button"))
        self.test_btn.clicked.connect(self.run_specific_test)
        style_dialog_button(self.test_btn, "accent")
        test_layout.addWidget(self.test_btn)

        self.run_all_tests_btn = QPushButton(self.translator.translate("win_diag_run_all_tests_button"))
        self.run_all_tests_btn.clicked.connect(self.run_all_specific_tests)
        style_dialog_button(self.run_all_tests_btn, "primary")
        test_layout.addWidget(self.run_all_tests_btn)

        config_layout.addLayout(test_layout)
        layout.addLayout(config_layout)

        self.specific_test_text = QTextEdit()
        self.specific_test_text.setReadOnly(True)
        self.specific_test_text.setFont(QFont("Consolas", 9))
        layout.addWidget(self.specific_test_text)

        self.update_hardware_list()
        self.tab_widget.addTab(tab, self.translator.translate("win_diag_tab_specific"))

    def create_sensor_explorer_tab(self):
        """Erstellt das Tab fÃ¼r den Sensor Explorer."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        configure_dialog_layout(layout, margins=(12, 12, 12, 12))

        self.explorer_title_label = QLabel(self.translator.translate("win_diag_sensor_explorer_title"))
        self.explorer_title_label.setFont(QFont("", 10, QFont.Weight.Bold))
        layout.addWidget(self.explorer_title_label)

        # KORRIGIERT: Hardcodierter String durch Ãœbersetzungsaufruf ersetzt
        self.explorer_hint_label = QLabel(self.translator.translate("win_diag_explorer_hint"))
        style_info_label(self.explorer_hint_label, "subtle")
        layout.addWidget(self.explorer_hint_label)

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
        
        self.refresh_explorer_btn = QPushButton(self.translator.translate("win_diag_refresh_explorer"))
        self.refresh_explorer_btn.clicked.connect(self._populate_sensor_tree)
        style_dialog_button(self.refresh_explorer_btn, "accent")
        button_layout.addWidget(self.refresh_explorer_btn)

        self.export_all_btn = QPushButton(self.translator.translate("win_diag_export_all_sensors"))
        self.export_all_btn.clicked.connect(self._export_all_sensors)
        style_dialog_button(self.export_all_btn, "compact")
        button_layout.addWidget(self.export_all_btn)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        self.tab_widget.addTab(tab, self.translator.translate("win_diag_tab_explorer"))

    def create_cache_management_tab(self):
        """Erstellt das Tab fÃ¼r Cache-Verwaltung."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        configure_dialog_layout(layout, margins=(12, 12, 12, 12))

        self.cache_management_title_label = QLabel(self.translator.translate("win_diag_cache_management_title"))
        self.cache_management_title_label.setFont(QFont("", 10, QFont.Weight.Bold))
        layout.addWidget(self.cache_management_title_label)

        self.cache_desc_label = QLabel(self.translator.translate("win_diag_cache_desc"))
        style_info_label(self.cache_desc_label, "muted")
        layout.addWidget(self.cache_desc_label)

        cache_buttons = QHBoxLayout()

        self.cache_reset_btn = QPushButton(self.translator.translate("win_diag_cache_reset_button"))
        self.cache_reset_btn.clicked.connect(self.reset_cache_and_diagnose)
        style_dialog_button(self.cache_reset_btn, "accent")
        cache_buttons.addWidget(self.cache_reset_btn)

        self.clear_cache_btn = QPushButton(self.translator.translate("win_diag_cache_clear_button"))
        self.clear_cache_btn.clicked.connect(self.clear_sensor_cache)
        style_dialog_button(self.clear_cache_btn, "danger")
        cache_buttons.addWidget(self.clear_cache_btn)

        layout.addLayout(cache_buttons)

        self.cache_info_text = QTextEdit()
        self.cache_info_text.setReadOnly(True)
        self.cache_info_text.setFont(QFont("Consolas", 9))
        self.load_cache_info()
        layout.addWidget(self.cache_info_text)

        self.tab_widget.addTab(tab, self.translator.translate("win_diag_tab_cache"))

    def _populate_sensor_tree(self):
        """FÃ¼llt den Sensor Tree rekursiv mit allen GerÃ¤ten, Unter-GerÃ¤ten und Sensoren."""
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
        """FÃ¼gt ein Hardware-Objekt und all seine Sensoren und Sub-Hardware rekursiv zum Baum hinzu."""
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
        """Zeigt KontextmenÃ¼ fÃ¼r Sensoren."""
        item = self.sensor_tree.itemAt(position)
        if not item or not item.data(0, Qt.ItemDataRole.UserRole):
            return

        sensor_data = item.data(0, Qt.ItemDataRole.UserRole)
        
        menu = QMenu(self)
        
        copy_id_action = QAction(self.translator.translate("win_diag_copy_identifier"), self)
        copy_id_action.triggered.connect(lambda: QApplication.clipboard().setText(sensor_data['identifier']))
        menu.addAction(copy_id_action)
        
        add_custom_action = QAction(self.translator.translate("win_diag_add_as_custom"), self)
        add_custom_action.triggered.connect(lambda: self._add_as_custom_sensor(sensor_data))
        menu.addAction(add_custom_action)
        
        menu.exec(self.sensor_tree.mapToGlobal(position))

    def _add_as_custom_sensor(self, sensor_data):
        """Ã–ffnet Dialog zum HinzufÃ¼gen eines Custom Sensors."""
        dialog = CustomSensorDialog(self, sensor_data)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            custom_sensors = self.main_app.settings_manager.get_setting(SettingsKey.CUSTOM_SENSORS.value, {})
            
            custom_key = str(uuid.uuid4())[:8]
            custom_sensors[custom_key] = {
                'identifier': sensor_data['identifier'],
                'display_name': dialog.get_display_name(),
                'sensor_type': sensor_data['sensor_type'],
                'hardware_name': sensor_data.get('hardware_name', ''),
                'sensor_name': sensor_data.get('sensor_name', ''),
                'color': '#FFFFFF',
                'unit': dialog.get_unit(),
                'enabled': True
            }
            
            self.main_app.settings_manager.set_setting(SettingsKey.CUSTOM_SENSORS.value, custom_sensors)
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

    def _get_compatible_hardware_items(self):
        """Liefert nur die Hardware, die zum aktuell gewählten Test-Sensor passt."""
        if not self.main_app.hw_manager.computer:
            return []

        selected_sensor = self.sensor_combo.currentData() if hasattr(self, 'sensor_combo') else None
        hardware_items = list(self.main_app.hw_manager.computer.Hardware)

        if not selected_sensor:
            return hardware_items

        return [
            hw for hw in hardware_items
            if is_hardware_compatible(selected_sensor, hw)
        ]

    def _populate_sensor_options(self, selected_sensor: str | None = None):
        self.sensor_combo.clear()
        for sensor_id, key in SPECIFIC_SENSOR_OPTIONS:
            self.sensor_combo.addItem(self.translator.translate(key), sensor_id)

        if selected_sensor:
            index = self.sensor_combo.findData(selected_sensor)
            if index >= 0:
                self.sensor_combo.setCurrentIndex(index)

    def update_hardware_list(self):
        """Aktualisiert die Hardware-Liste fÃ¼r spezifische Tests."""
        previous_selection = self.hardware_combo.currentData() if self.hardware_combo.count() else None
        self.hardware_combo.clear()

        for hw in self._get_compatible_hardware_items():
            self.hardware_combo.addItem(f"{hw.Name} ({hw.HardwareType})", hw.Name)

        if previous_selection:
            index = self.hardware_combo.findData(previous_selection)
            if index >= 0:
                self.hardware_combo.setCurrentIndex(index)

        if hasattr(self, 'test_btn') and not (self.diagnosis_thread and self.diagnosis_thread.isRunning()):
            self.test_btn.setEnabled(self.hardware_combo.count() > 0)

    def _build_cache_info_text(self, prefix_info: str | None = None) -> str:
        """Erstellt den Cache-Bericht aus dem aktuellen In-Memory-Cache."""
        cache = getattr(self.main_app.hw_manager, "sensor_cache", {}) or {}
        cached_entries = {key: value for key, value in cache.items() if not key.startswith('_')}

        info_parts = []
        if prefix_info:
            info_parts.extend([prefix_info, ""])

        info_parts.extend([
            f"=== {self.translator.translate('win_diag_cache_info_header')} ===",
            f"{self.translator.translate('win_diag_cache_info_entries')}: {len(cached_entries)}",
            ""
        ])

        fingerprint = cache.get('_hardware_fingerprint')
        if fingerprint:
            info_parts.append(f"{self.translator.translate('win_diag_cache_info_fingerprint')}: {fingerprint[:80]}...")
            info_parts.append("")

        info_parts.append(f"{self.translator.translate('win_diag_cache_info_cached_entries')}:")
        for key, value in cached_entries.items():
            info_parts.append(f"  {key}: {value}")

        return "\n".join(info_parts)

    def load_cache_info(self):
        """LÃ¤dt und zeigt Cache-Informationen an."""
        self.cache_info_text.setPlainText(self._build_cache_info_text())

    def _set_diagnosis_controls_enabled(self, enabled: bool):
        """Sperrt hardware-nahe Aktionen während einer laufenden Diagnose."""
        self.refresh_btn.setEnabled(enabled)
        self.test_btn.setEnabled(enabled)
        self.run_all_tests_btn.setEnabled(enabled)
        self.cache_reset_btn.setEnabled(enabled)
        self.clear_cache_btn.setEnabled(enabled)
        self.refresh_explorer_btn.setEnabled(enabled)
        self.export_all_btn.setEnabled(enabled)
        self.hardware_combo.setEnabled(enabled)
        self.sensor_combo.setEnabled(enabled)

    def _start_diagnosis_thread(self, thread: DiagnosisWorkerThread, result_slot):
        """Startet genau einen Diagnose-Thread mit pausiertem Monitoring-Worker."""
        if self.diagnosis_thread and self.diagnosis_thread.isRunning():
            return False

        self._worker_was_paused_for_diagnosis = self.main_app.pause_worker()
        self.diagnosis_thread = thread
        self.diagnosis_thread.progress_updated.connect(self.update_progress)
        self.diagnosis_thread.status_updated.connect(self.update_status)
        self.diagnosis_thread.diagnosis_completed.connect(result_slot)
        self.diagnosis_thread.finished.connect(self._on_diagnosis_thread_finished)

        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self._set_diagnosis_controls_enabled(False)
        self.diagnosis_thread.start()
        return True

    def run_full_diagnosis(self):
        """Startet die vollstÃ¤ndige Diagnose im Worker-Thread."""
        thread = DiagnosisWorkerThread(self.main_app, "full")
        self._start_diagnosis_thread(thread, self.set_full_diagnosis_info)

    def run_specific_test(self):
        """Startet einen spezifischen Sensor-Test."""
        if self.diagnosis_thread and self.diagnosis_thread.isRunning():
            return

        hardware_name = self.hardware_combo.currentData()
        sensor_name = self.sensor_combo.currentData()

        if not hardware_name or not sensor_name:
            QMessageBox.warning(self, self.translator.translate("shared_error_title"), self.translator.translate("win_diag_error_no_selection"))
            return

        thread = DiagnosisWorkerThread(self.main_app, "specific")
        thread.set_specific_test(hardware_name, sensor_name)
        self._start_diagnosis_thread(thread, self.set_specific_test_info)

    def run_all_specific_tests(self):
        """Startet alle Specific-Tests nacheinander."""
        if self.diagnosis_thread and self.diagnosis_thread.isRunning():
            return

        thread = DiagnosisWorkerThread(self.main_app, "all_specific")
        self._start_diagnosis_thread(thread, self.set_specific_test_info)

    def reset_cache_and_diagnose(self):
        """Setzt den Cache zurÃ¼ck und fÃ¼hrt eine neue Diagnose durch."""
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

        thread = DiagnosisWorkerThread(self.main_app, "cache_reset")
        self._start_diagnosis_thread(thread, self.set_cache_reset_info)

    def update_progress(self, value: int):
        """Aktualisiert den Fortschrittsbalken."""
        self.progress_bar.setValue(value)

    def update_status(self, key: str, param: str):
        """Aktualisiert den Status-Text."""
        self._last_status_key = key
        self._last_status_param = param
        if param:
            if param in self.translator.translations:
                param = self.translator.translate(param)
            text = self.translator.translate(key, value=param)
        else:
            text = self.translator.translate(key)
        self.status_label.setText(text)

    def set_diagnosis_info(self, info: str):
        """KompatibilitÃ¤tsmethode fÃ¼r action_handler - setzt Diagnose-Info im aktuellen Tab."""
        self.full_diagnosis_text.setPlainText(info)
        self._last_status_key = None
        self._last_status_param = ""

        if len(info) < 100:
            self.status_label.setText(info)

    def set_full_diagnosis_info(self, info: str):
        """Setzt die vollstÃ¤ndigen Diagnose-Informationen."""
        self.full_diagnosis_text.setPlainText(info)
        self.update_status("diag_status_full_done", "")

    def set_specific_test_info(self, info: str):
        """Setzt die Ergebnisse des spezifischen Tests."""
        self.specific_test_text.setPlainText(info)
        self.update_status("diag_status_test_done", "")

    def set_cache_reset_info(self, info: str):
        """Setzt die Ergebnisse des Cache-Resets."""
        self.cache_info_text.setPlainText(self._build_cache_info_text(info))
        self.update_status("diag_status_cache_reset_done", "")

    def _on_diagnosis_thread_finished(self):
        """Synchronisiert UI und Worker nach Abschluss einer Diagnose."""
        completed_thread = self.diagnosis_thread
        self.progress_bar.setVisible(False)
        self._set_diagnosis_controls_enabled(True)

        self.update_hardware_list()
        self._populate_sensor_tree()
        self.load_cache_info()

        if completed_thread and completed_thread.cache_reset_succeeded:
            self.main_app.action_handler.sync_after_hardware_change()

        self.main_app.resume_worker(self._worker_was_paused_for_diagnosis)
        self._worker_was_paused_for_diagnosis = False
        self.diagnosis_thread = None

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
        """LÃ¶scht die sensor_cache.json Datei und bietet Programmneustart an."""
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
            else:
                cache_deleted = False

            runtime_cache = getattr(self.main_app.hw_manager, 'sensor_cache', {}) or {}
            fingerprint = runtime_cache.get('_hardware_fingerprint')
            self.main_app.hw_manager.sensor_cache = (
                {'_hardware_fingerprint': fingerprint} if fingerprint else {}
            )
            self.main_app.hw_manager.cache_updated = False

            cache_message = (
                self.translator.translate('win_diag_cache_cleared_success')
                if cache_deleted else
                self.translator.translate('win_diag_cache_not_found')
            )
            self.cache_info_text.setPlainText(self._build_cache_info_text(cache_message))

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
            logging.error(f"Fehler beim LÃ¶schen des Sensor-Cache: {e}", exc_info=True)
            error_text = self.translator.translate('shared_unexpected_error_text', error=e)
            QMessageBox.critical(self, self.translator.translate("shared_error_title"), error_text)

    def retranslate_ui(self):
        selected_sensor = self.sensor_combo.currentData()
        selected_hardware = self.hardware_combo.currentData()
        current_tab_index = self.tab_widget.currentIndex()

        self.setWindowTitle(self.translator.translate("win_title_diagnosis"))
        self.status_label.setText(self.translator.translate("win_diag_status_ready"))
        self.refresh_btn.setText(self.translator.translate("win_diag_refresh_button"))
        self.export_btn.setText(self.translator.translate("win_diag_export_button"))
        self.close_btn.setText(self.translator.translate("win_shared_button_close"))
        self.full_diag_info_label.setText(self.translator.translate("win_diag_full_diag_title"))
        self.specific_tests_title_label.setText(self.translator.translate("win_diag_specific_tests_title"))
        self.hardware_label.setText(self.translator.translate("win_diag_label_hardware"))
        self.sensor_label.setText(self.translator.translate("win_diag_label_sensor"))
        self.test_btn.setText(self.translator.translate("win_diag_start_test_button"))
        self.run_all_tests_btn.setText(self.translator.translate("win_diag_run_all_tests_button"))
        self.explorer_title_label.setText(self.translator.translate("win_diag_sensor_explorer_title"))
        self.explorer_hint_label.setText(self.translator.translate("win_diag_explorer_hint"))
        self.refresh_explorer_btn.setText(self.translator.translate("win_diag_refresh_explorer"))
        self.export_all_btn.setText(self.translator.translate("win_diag_export_all_sensors"))
        self.cache_management_title_label.setText(self.translator.translate("win_diag_cache_management_title"))
        self.cache_desc_label.setText(self.translator.translate("win_diag_cache_desc"))
        self.cache_reset_btn.setText(self.translator.translate("win_diag_cache_reset_button"))
        self.clear_cache_btn.setText(self.translator.translate("win_diag_cache_clear_button"))
        self.tab_widget.setTabText(0, self.translator.translate("win_diag_tab_full"))
        self.tab_widget.setTabText(1, self.translator.translate("win_diag_tab_specific"))
        self.tab_widget.setTabText(2, self.translator.translate("win_diag_tab_explorer"))
        self.tab_widget.setTabText(3, self.translator.translate("win_diag_tab_cache"))
        self.sensor_tree.setHeaderLabels([
            self.translator.translate("win_diag_explorer_hardware"),
            self.translator.translate("win_diag_explorer_sensor_name"),
            self.translator.translate("win_diag_explorer_type"),
            self.translator.translate("win_diag_explorer_value"),
            self.translator.translate("win_diag_explorer_identifier"),
        ])
        self._populate_sensor_options(selected_sensor)
        self.update_hardware_list()
        if selected_hardware:
            index = self.hardware_combo.findData(selected_hardware)
            if index >= 0:
                self.hardware_combo.setCurrentIndex(index)
        self.tab_widget.setCurrentIndex(current_tab_index)

        if self._last_status_key:
            self.update_status(self._last_status_key, self._last_status_param)

