# tray/action_handler.py
from __future__ import annotations
import os
import platform
import subprocess
import logging
import shutil
import json
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Callable
from functools import partial

from PySide6.QtWidgets import (
    QApplication, QInputDialog, QMessageBox, QFileDialog
)
from PySide6.QtCore import QTimer, QThread, Signal

from config.config import CONFIG_DIR, reconfigure_logging
from config.constants import SettingsKey
from ui.widgets.reorder_window import ReorderWindow
from ui.widgets.color_management_window import ColorManagementWindow
from ui.widgets.alarm_settings_window import AlarmSettingsWindow
from ui.widgets.sensor_diagnosis_window import SensorDiagnosisWindow
from ui.widgets.health_status_window import HealthStatusWindow
from ui.widgets.label_editor_window import LabelEditorWindow
from ui.widgets.performance_settings_window import PerformanceSettingsWindow
from ui.widgets.font_settings_window import FontSettingsWindow
from ui.widgets.misc_settings_window import MiscSettingsWindow
from ui.widgets.widget_settings_window import WidgetSettingsWindow
from ui.widgets.custom_sensor_management_window import CustomSensorManagementWindow
from ui.widgets.help_window import HelpWindow
from ui.widgets.monitoring_window import MonitoringWindow


if TYPE_CHECKING:
    from core.main_window import SystemMonitor


class ActionHandler:
    """Behandelt alle Aktionen aus dem Tray-Menü und anderen UI-Elementen."""

    def __init__(self, main_window: SystemMonitor):
        self.main_win = main_window
        self.translator = main_window.translator
        self.settings_manager = main_window.settings_manager

        # Instanzvariablen für Fenster, um sie wiederverwenden zu können
        self.reorder_window: Optional[ReorderWindow] = None
        self.color_management_window: Optional[ColorManagementWindow] = None
        self.alarm_settings_window: Optional[AlarmSettingsWindow] = None
        self.sensor_diagnosis_window: Optional[SensorDiagnosisWindow] = None
        self.health_status_window: Optional[HealthStatusWindow] = None
        self.label_editor_window: Optional[LabelEditorWindow] = None
        self.performance_settings_window: Optional[PerformanceSettingsWindow] = None
        self.font_settings_window: Optional[FontSettingsWindow] = None
        self.misc_settings_window: Optional[MiscSettingsWindow] = None
        self.widget_settings_window: Optional[WidgetSettingsWindow] = None
        self.custom_sensor_management_window: Optional[CustomSensorManagementWindow] = None
        self.help_window: Optional[HelpWindow] = None
        self.monitoring_window: Optional[MonitoringWindow] = None

    def show_set_width_dialog(self, metric_key: str):
        """Öffnet einen Dialog, um die Breite eines Widgets manuell einzustellen."""
        manager = self.main_win.detachable_manager
        if not (widget := manager.active_widgets.get(metric_key)):
            return

        min_w = self.settings_manager.get_setting(SettingsKey.WIDGET_MIN_WIDTH.value, 50)
        max_w = self.settings_manager.get_setting(SettingsKey.WIDGET_MAX_WIDTH.value, 2000)

        current_width = widget.width()
        new_width, ok = QInputDialog.getInt(
            self.main_win,
            self.translator.translate("dlg_title_set_width"),
            self.translator.translate("dlg_label_set_width", widget_name=widget.label.text()),
            current_width, min_w, max_w, 5
        )

        if ok:
            manager.set_widget_width(metric_key, new_width)


    def _show_single_instance_window(self, attr_name: str, window_class):
        """Öffnet ein Fenster und stellt sicher, dass nur eine Instanz existiert."""
        win = getattr(self, attr_name, None)
        try:
            if win and not win.isHidden():
                win.activateWindow()
                win.raise_()
                return
        except RuntimeError:
            logging.debug(f"Fenster {attr_name} C++ Objekt wurde gelöscht, erstelle neue Instanz")

        new_win = window_class(self.main_win)
        setattr(self, attr_name, new_win)
        new_win.show()
        new_win.activateWindow()
        new_win.raise_()

    def set_language(self, language_name: str):
        """Setzt die Anwendungssprache und aktualisiert die UI dynamisch ohne Neustart."""
        self.settings_manager.set_setting("language", language_name)
        self.main_win.ui_manager.refresh_metric_definitions()
        self.main_win.tray_icon_manager.rebuild_menu()
        logging.info(f"Sprache dynamisch zu '{language_name}' gewechselt und UI aktualisiert.")

    # Layout-Management
    def prompt_and_save_layout(self):
        text, ok = QInputDialog.getText(self.main_win, self.translator.translate("dlg_title_save_layout"), self.translator.translate("dlg_label_save_layout"))
        if ok and text:
            self.main_win.detachable_manager._synchronize_group_layout()
            self.main_win.detachable_manager.save_layout_as(text)
            self.main_win.tray_icon_manager.rebuild_menu()

    def load_named_layout(self, name: str):
        self.main_win.detachable_manager.load_layout(name)

    def manage_layouts(self):
        user_layouts = [name for name in self.main_win.detachable_manager.get_available_layout_names() if not name.startswith('_')]
        if not user_layouts:
            QMessageBox.information(self.main_win, self.translator.translate("dlg_title_manage_layout"), self.translator.translate("dlg_info_no_layouts"))
            return
        item, ok = QInputDialog.getItem(self.main_win, self.translator.translate("dlg_title_delete_layout"), self.translator.translate("dlg_label_delete_layout"), user_layouts, 0, False)
        if ok and item:
            reply = QMessageBox.question(self.main_win, self.translator.translate("dlg_confirm_delete_layout_title"), self.translator.translate("dlg_confirm_delete_layout_text", layout_name=item), QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.main_win.detachable_manager.delete_layout(item)
                self.main_win.tray_icon_manager.rebuild_menu()

    def reset_all_settings(self):
        """
        Setzt ALLE Einstellungen und Widget-Positionen auf Standardwerte zurück.
        Alle Widgets werden wieder sichtbar und in der Standardanordnung angezeigt.
        """
        # 1. Alle aktuell angezeigten Widgets schließen
        self.main_win.detachable_manager._deactivate_view()
        
        # 2. ALLE Einstellungen auf Standardwerte zurücksetzen
        self.settings_manager.reset_to_defaults()
        
        # 3. Dynamische Sensoren (Storage, Custom) erneut zur Konfiguration hinzufügen
        self.main_win.ui_manager.update_dynamic_metric_order()

        # 4. CPU- und GPU-Sensoren sofort neu auswählen, BEVOR die UI neu aufgebaut wird
        if hasattr(self.main_win, 'hw_manager'):
            self.main_win.hw_manager.update_selected_cpu_sensors("auto")
            self.main_win.hw_manager.update_selected_gpu_sensors("auto")

        # 5. UI-Komponenten über die Änderungen informieren und Neuaufbau anstoßen
        QTimer.singleShot(0, self._execute_post_reset_ui_setup)
        
        logging.info("VOLLSTÄNDIGER Reset durchgeführt: Alle Einstellungen und Positionen auf Standardwerte zurückgesetzt")

    def _execute_post_reset_ui_setup(self):
        """Führt die UI-Neuerstellung nach einem Reset in der korrekten Reihenfolge aus."""
        # Schritt 5a: Aktiviere die neue Ansicht mit leeren Daten (erzeugt den Standard-Stack)
        self.main_win.detachable_manager._activate_view_with_data({})
        
        # Schritt 5b: Aktualisiere alle restlichen UI-Komponenten (Stile, Menü etc.)
        self._refresh_ui_after_complete_reset()

    def reset_positions_only(self):
        """
        Setzt NUR die Widget-Positionen auf Standard-Stapel zurück.
        Alle anderen Einstellungen bleiben unverändert.
        """
        # Nur Widget-Positionen zurücksetzen
        self.main_win.detachable_manager.reset_to_default_stack()
        
        logging.info("Widget-Positionen auf Standard-Stapel zurückgesetzt (Einstellungen bleiben unverändert)")

    def _refresh_ui_after_complete_reset(self):
        """Aktualisiert alle UI-Komponenten nach dem vollständigen Reset."""
        try:
            # UI-Manager über Sprachänderung informieren (falls Sprache zurückgesetzt wurde)
            self.main_win.ui_manager.refresh_metric_definitions()
            
            # Stile auf alle Widgets anwenden
            self.main_win.ui_manager.apply_styles()
            
            # Tray-Icon aktualisieren
            self.main_win.tray_icon_manager.update_tray_icon()
            
            # Menü neu aufbauen für aktualisierte Einstellungen
            self.main_win.tray_icon_manager.rebuild_menu()
            
            # Worker-Thread neu starten (falls Update-Intervall geändert wurde)
            self.main_win.restart_worker_thread()
            
        except Exception as e:
            logging.error(f"Fehler beim UI-Update nach vollständigem Reset: {e}", exc_info=True)

    def unstack_all_widgets(self):
        manager = self.main_win.detachable_manager
        manager.group_manager.groups.clear()
        manager.group_manager.widget_to_group.clear()
        for widget in manager.active_widgets.values():
            widget.remove_group_border()
        manager.active_layout_name = None
        manager.layout_modified.emit()

    # Widget-Sichtbarkeit
    def toggle_metric_visibility(self, metric_key: str, visible: bool):
        setting_key = f"show_{metric_key}"
        self.settings_manager.set_setting(setting_key, visible)
        manager = self.main_win.detachable_manager
        if visible:
            if metric_key not in manager.active_widgets:
                manager.detach_metric(metric_key, manager.get_safe_position_for_new_widget())
        else:
             manager.attach_metric(metric_key)
        self.main_win.tray_icon_manager.rebuild_menu()

    # Custom Sensor Management
    def show_custom_sensor_management(self):
        """Öffnet das Custom Sensor Management Fenster."""
        self._show_single_instance_window('custom_sensor_management_window', CustomSensorManagementWindow)

    def refresh_custom_sensors(self):
        """Aktualisiert Custom Sensors nach Änderungen und zeigt neue Widgets sofort an."""
        active_before = set(self.main_win.detachable_manager.active_widgets.keys())

        self.main_win.ui_manager.refresh_metric_definitions()
        self.main_win.tray_icon_manager.rebuild_menu()

        custom_sensors = self.settings_manager.get_setting(SettingsKey.CUSTOM_SENSORS.value, {})
        for sensor_id in custom_sensors.keys():
            metric_key = f"custom_{sensor_id}"
            
            if (custom_sensors[sensor_id].get('enabled', True) and
                    metric_key in self.main_win.ui_manager.metric_widgets and
                    metric_key not in active_before):
                
                logging.info(f"Neuer Custom Sensor '{metric_key}' wird automatisch angezeigt.")
                self.main_win.detachable_manager.detach_metric(metric_key)
        
        logging.info("Custom Sensors wurden aktualisiert.")

    # Fenster-Einstellungen
    def toggle_position_lock(self, checked: bool):
        self.settings_manager.set_setting(SettingsKey.POSITION_FIXED.value, checked)

    def toggle_always_on_top(self, checked: bool):
        self.settings_manager.set_setting(SettingsKey.ALWAYS_ON_TOP.value, checked)
        self.main_win.detachable_manager.update_all_window_flags()

    def toggle_overlay_visibility(self):
        manager = self.main_win.detachable_manager
        if not manager.active_widgets: return
        is_visible = any(w.isVisible() for w in manager.active_widgets.values())
        for widget in manager.active_widgets.values(): widget.setVisible(not is_visible)

    # Anzeige-Einstellungen
    def toggle_bar_graphs(self, checked: bool):
        self.settings_manager.set_setting(SettingsKey.SHOW_BAR_GRAPHS.value, checked)
        self.main_win.ui_manager.apply_styles()

    def show_bar_width_dialog(self):
        current_value = self.settings_manager.get_setting(SettingsKey.BAR_GRAPH_WIDTH_MULTIPLIER.value, 9)
        new_value, ok = QInputDialog.getInt(
            self.main_win,
            self.translator.translate("dlg_title_bar_width"),
            self.translator.translate("dlg_label_bar_width"),
            current_value, 2, 20
        )
        if ok:
            self.settings_manager.set_setting(SettingsKey.BAR_GRAPH_WIDTH_MULTIPLIER.value, new_value)
            self.main_win.ui_manager.apply_styles()

    def show_bar_height_dialog(self):
        current_value = self.settings_manager.get_setting(SettingsKey.BAR_GRAPH_HEIGHT_FACTOR.value, 0.65)
        new_value, ok = QInputDialog.getDouble(
            self.main_win,
            self.translator.translate("dlg_title_bar_height"),
            self.translator.translate("dlg_label_bar_height"),
            current_value, 0.1, 2.0, 2
        )
        if ok:
            self.settings_manager.set_setting(SettingsKey.BAR_GRAPH_HEIGHT_FACTOR.value, new_value)
            self.main_win.ui_manager.apply_styles()

    def show_opacity_dialog(self):
        current_value = self.settings_manager.get_setting(SettingsKey.BACKGROUND_ALPHA.value, 200)
        new_value, ok = QInputDialog.getInt(
            self.main_win,
            self.translator.translate("dlg_title_opacity"),
            self.translator.translate("dlg_label_opacity"),
            current_value, 0, 255
        )
        if ok:
            self.settings_manager.set_setting(SettingsKey.BACKGROUND_ALPHA.value, new_value)
            self.main_win.ui_manager.apply_styles()

    # Hardware-Auswahl
    def select_hardware(self, key: str, value: str, is_gpu: bool = False, is_cpu: bool = False):
        if is_gpu:
            value = self.main_win.hw_manager.update_selected_gpu_sensors(value)
        if is_cpu:
            value = self.main_win.hw_manager.update_selected_cpu_sensors(value)
        self.settings_manager.set_setting(key, value)

    def set_unit(self, key: str, value: str):
        self.settings_manager.set_setting(key, value)

    # Tray-Icon-Einstellungen
    def set_tray_setting(self, key: str, value):
        self.settings_manager.set_setting(key, value)
        self.main_win.tray_icon_manager.update_tray_icon()

    def show_tray_text_dialog(self):
        current_value = self.settings_manager.get_setting(SettingsKey.TRAY_CUSTOM_TEXT.value, "")
        new_value, ok = QInputDialog.getText(
            self.main_win,
            self.translator.translate("menu_tray_text_change"),
            self.translator.translate("dlg_label_tray_text"),
            text=current_value
        )
        if ok:
            self.settings_manager.set_setting(SettingsKey.TRAY_CUSTOM_TEXT.value, new_value)
            self.main_win.tray_icon_manager.update_tray_icon()

    def show_tray_font_size_dialog(self):
        current_value = self.settings_manager.get_setting(SettingsKey.TRAY_TEXT_FONT_SIZE.value, 12)
        new_value, ok = QInputDialog.getInt(
            self.main_win,
            self.translator.translate("menu_tray_font_size"),
            self.translator.translate("dlg_label_tray_font_size"),
            current_value, 6, 20
        )
        if ok:
            self.settings_manager.set_setting(SettingsKey.TRAY_TEXT_FONT_SIZE.value, new_value)
            self.main_win.tray_icon_manager.update_tray_icon()

    def show_tray_border_width_dialog(self):
        current_value = self.settings_manager.get_setting(SettingsKey.TRAY_BORDER_THICKNESS.value, 1)
        new_value, ok = QInputDialog.getInt(
            self.main_win,
            self.translator.translate("menu_tray_border_width"),
            self.translator.translate("dlg_label_tray_border_width"),
            current_value, 0, 10
        )
        if ok:
            self.settings_manager.set_setting(SettingsKey.TRAY_BORDER_THICKNESS.value, new_value)
            self.main_win.tray_icon_manager.update_tray_icon()

    def show_blink_rate_dialog(self):
        current_value = self.settings_manager.get_setting(SettingsKey.TRAY_BLINK_RATE_SEC.value, 1.0)
        new_value, ok = QInputDialog.getDouble(
            self.main_win,
            self.translator.translate("menu_tray_blink_rate"),
            self.translator.translate("dlg_label_tray_blink_rate"),
            current_value, 0.5, 60.0, 1
        )
        if ok:
            self.settings_manager.set_setting(SettingsKey.TRAY_BLINK_RATE_SEC.value, new_value)

    def show_blink_duration_dialog(self):
        blink_rate_sec = self.settings_manager.get_setting(SettingsKey.TRAY_BLINK_RATE_SEC.value, 1.0)
        max_duration = max(100, int(blink_rate_sec * 1000) - 100)
        current_value = self.settings_manager.get_setting(SettingsKey.TRAY_BLINK_DURATION_MS.value, 500)
        new_value, ok = QInputDialog.getInt(
            self.main_win,
            self.translator.translate("menu_tray_blink_duration"),
            self.translator.translate("dlg_label_tray_blink_duration"),
            current_value, 100, max_duration
        )
        if ok:
            self.settings_manager.set_setting(SettingsKey.TRAY_BLINK_DURATION_MS.value, new_value)

    # System-Einstellungen
    def show_update_interval_dialog(self):
        current_value = self.settings_manager.get_setting(SettingsKey.UPDATE_INTERVAL_MS.value, 2000)
        new_value, ok = QInputDialog.getInt(
            self.main_win,
            self.translator.translate("dlg_title_update_interval"),
            self.translator.translate("dlg_label_update_interval"),
            current_value, 500, 60000
        )
        if ok:
            self.settings_manager.set_setting(SettingsKey.UPDATE_INTERVAL_MS.value, new_value)
            QTimer.singleShot(100, self.main_win.restart_worker_thread)

    def set_logging_level(self, key: str, level: str):
        self.settings_manager.set_setting(key, level)
        reconfigure_logging(self.settings_manager.get_all_settings())
        self.main_win.tray_icon_manager.rebuild_menu()

    def show_log_size_dialog(self):
        current_value = self.settings_manager.get_setting(SettingsKey.LOG_MAX_SIZE_MB.value, 20)
        new_value, ok = QInputDialog.getInt(
            self.main_win,
            self.translator.translate("menu_config_log_size"),
            self.translator.translate("dlg_label_log_size"),
            current_value, 1, 100
        )
        if ok:
            self.settings_manager.set_setting(SettingsKey.LOG_MAX_SIZE_MB.value, new_value)
            reconfigure_logging(self.settings_manager.get_all_settings())

    def show_log_backup_dialog(self):
        current_value = self.settings_manager.get_setting(SettingsKey.LOG_BACKUP_COUNT.value, 5)
        new_value, ok = QInputDialog.getInt(
            self.main_win,
            self.translator.translate("menu_config_log_backups"),
            self.translator.translate("dlg_label_log_backups"),
            current_value, 1, 20
        )
        if ok:
            self.settings_manager.set_setting(SettingsKey.LOG_BACKUP_COUNT.value, new_value)
            reconfigure_logging(self.settings_manager.get_all_settings())

    # Fenster-Dialoge
    def show_font_dialog(self): self._show_single_instance_window('font_settings_window', FontSettingsWindow)
    def show_reorder_window(self):
        if not self.main_win.detachable_manager.are_all_widgets_in_single_stack():
            QMessageBox.warning(
                self.main_win,
                self.translator.translate("dlg_title_reorder_impossible"),
                self.translator.translate("dlg_text_reorder_impossible")
            )
            return
        self._show_single_instance_window('reorder_window', ReorderWindow)
    def show_label_editor_window(self): self._show_single_instance_window('label_editor_window', LabelEditorWindow)
    def show_color_management(self): self._show_single_instance_window('color_management_window', ColorManagementWindow)
    def show_alarm_settings_window(self): self._show_single_instance_window('alarm_settings_window', AlarmSettingsWindow)
    def show_performance_settings_window(self): self._show_single_instance_window('performance_settings_window', PerformanceSettingsWindow)
    def show_misc_settings_window(self): self._show_single_instance_window('misc_settings_window', MiscSettingsWindow)
    def show_widget_settings_window(self):
        self._show_single_instance_window('widget_settings_window', WidgetSettingsWindow)

    def show_health_status_window(self):
        self._show_single_instance_window('health_status_window', HealthStatusWindow)
        if win := getattr(self, 'health_status_window', None): QTimer.singleShot(50, win.update_report)

    def show_help_window(self):
        self._show_single_instance_window('help_window', HelpWindow)

    def show_monitoring_window(self):
        """Öffnet das Fenster für den Monitoring-Verlauf."""
        self._show_single_instance_window('monitoring_window', MonitoringWindow)

    def show_sensor_diagnosis(self):
        self._show_single_instance_window('sensor_diagnosis_window', SensorDiagnosisWindow)
        if not (win := getattr(self, 'sensor_diagnosis_window', None)): return
        
        if hasattr(self, 'diag_thread') and self.diag_thread and self.diag_thread.isRunning():
            logging.debug("Diagnose-Thread läuft bereits. Überspringe Start.")
            return

        win.set_diagnosis_info(self.translator.translate("diag_status_loading_data"))
        class DiagnosisThread(QThread):
            finished = Signal(str)
            def __init__(self, hw_manager): super().__init__(); self.hw_manager = hw_manager
            def run(self): self.finished.emit(self.hw_manager.run_sensor_diagnosis())
        
        self.diag_thread = DiagnosisThread(self.main_win.hw_manager)
        self.diag_thread.finished.connect(win.set_diagnosis_info)
        self.diag_thread.start()

    # Import/Export
    def export_settings(self):
        file_path, _ = QFileDialog.getSaveFileName(self.main_win, self.translator.translate("dlg_title_export"), "settings_export.json", self.translator.translate("shared_file_filter_json"))
        if not file_path: return
        self.settings_manager.export_settings(file_path)
        QMessageBox.information(self.main_win, self.translator.translate("dlg_export_success_title"), self.translator.translate("dlg_export_success_text", file_path=file_path))

    def import_settings(self):
        if QMessageBox.question(self.main_win, self.translator.translate("dlg_title_import"), self.translator.translate("dlg_confirm_import_text"), QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes: return
        file_path, _ = QFileDialog.getOpenFileName(self.main_win, self.translator.translate("dlg_title_import"), "", self.translator.translate("shared_file_filter_json"))
        if not file_path: return
        if self.settings_manager.import_settings(file_path):
            if QMessageBox.question(self.main_win, self.translator.translate("dlg_title_import"), self.translator.translate("dlg_import_success_restart_prompt"), QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes) == QMessageBox.StandardButton.Yes: self.main_win.restart_app()
        else:
            QMessageBox.critical(self.main_win, self.translator.translate("dlg_import_failed_title"), self.translator.translate("dlg_import_failed_text"))

    def reset_settings_to_default(self):
        if QMessageBox.question(self.main_win, self.translator.translate("dlg_title_reset"), self.translator.translate("dlg_confirm_reset_text"), QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes: return
        if self.settings_manager.reset_to_defaults():
            QMessageBox.information(self.main_win, self.translator.translate("dlg_reset_success_title"), self.translator.translate("dlg_reset_success_text"))
            self.main_win.restart_app()
        else:
            QMessageBox.critical(self.main_win, self.translator.translate("shared_error_title"), self.translator.translate("dlg_reset_failed_text"))

    def open_config_folder(self):
        try:
            config_path = str(CONFIG_DIR)
            if platform.system() == "Windows": os.startfile(config_path)
            elif platform.system() == "Darwin": subprocess.run(["open", config_path], check=True)
            else: subprocess.run(["xdg-open", config_path], check=True)
        except Exception as e:
            QMessageBox.warning(self.main_win, self.translator.translate("shared_error_title"), self.translator.translate("dlg_open_folder_failed_text", e=e))