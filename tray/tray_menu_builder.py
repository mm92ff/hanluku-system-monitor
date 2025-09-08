# tray/tray_menu_builder.py
from __future__ import annotations
import logging
from typing import TYPE_CHECKING, Dict, Optional, Callable
from functools import partial

from PySide6.QtWidgets import QMenu
from PySide6.QtGui import QAction, QActionGroup

from config import config
from config.constants import TrayShape, SettingsKey

if TYPE_CHECKING:
    from core.main_window import SystemMonitor


class TrayMenuBuilder:
    """
    Baut das Tray-Icon-Menü dynamisch und mehrsprachig auf.
    """

    def __init__(self, main_window: SystemMonitor):
        self.main_win = main_window
        self.action_handler = main_window.action_handler
        self.ui_manager = main_window.ui_manager
        self.settings_manager = main_window.settings_manager
        self.translator = main_window.translator

    def build(self) -> QMenu:
        """Baut das vollständige Tray-Menü auf."""
        menu = QMenu()

        self._create_window_menu(menu)
        self._create_visibility_menu(menu)
        self._create_hardware_selection_menu(menu)
        self._create_custom_sensors_menu(menu)
        self._create_tray_icon_menu(menu)
        self._create_config_menu(menu)

        help_action = QAction(self.translator.translate("menu_help"), menu)
        help_action.triggered.connect(self.action_handler.show_help_window)
        menu.addAction(help_action)

        menu.addSeparator()
        quit_action = QAction(self.translator.translate("menu_quit"), menu)
        quit_action.triggered.connect(self.main_win.quit_app)
        menu.addAction(quit_action)

        return menu

    def _create_window_menu(self, menu: QMenu):
        """Erstellt das Fenster-Menü."""
        menu.addSection(self.translator.translate("menu_section_window"))

        show_hide_action = QAction(self.translator.translate("menu_toggle_widgets"), menu)
        show_hide_action.triggered.connect(self.action_handler.toggle_overlay_visibility)
        menu.addAction(show_hide_action)

        layout_menu = menu.addMenu(self.translator.translate("menu_layouts"))
        new_layout_action = QAction(self.translator.translate("menu_layout_new"), layout_menu)
        new_layout_action.triggered.connect(self.action_handler.prompt_and_save_layout)
        layout_menu.addAction(new_layout_action)

        unstack_action = QAction(self.translator.translate("menu_layout_unstacked"), layout_menu)
        unstack_action.triggered.connect(self.action_handler.unstack_all_widgets)
        layout_menu.addAction(unstack_action)
        layout_menu.addSeparator()

        if hasattr(self.main_win, 'detachable_manager'):
            user_layouts = [name for name in self.main_win.detachable_manager.get_available_layout_names() if not name.startswith('_')]
            if user_layouts:
                load_menu = layout_menu.addMenu(self.translator.translate("menu_layout_load"))
                for name in user_layouts:
                    load_action = QAction(name, load_menu)
                    load_action.triggered.connect(partial(self.action_handler.load_named_layout, name))
                    load_menu.addAction(load_action)

        manage_layouts_action = QAction(self.translator.translate("menu_layout_manage"), layout_menu)
        manage_layouts_action.triggered.connect(self.action_handler.manage_layouts)
        layout_menu.addAction(manage_layouts_action)
        layout_menu.addSeparator()

        reset_all_action = QAction(self.translator.translate("menu_reset_all"), layout_menu)
        reset_all_action.triggered.connect(self.action_handler.reset_all_settings)
        layout_menu.addAction(reset_all_action)

        reset_position_action = QAction(self.translator.translate("menu_reset_position"), layout_menu)
        reset_position_action.triggered.connect(self.action_handler.reset_positions_only)
        layout_menu.addAction(reset_position_action)

        menu.addSeparator()

        on_top_action = QAction(self.translator.translate("menu_always_on_top"), menu)
        on_top_action.setCheckable(True)
        on_top_action.setChecked(self.settings_manager.get_setting(SettingsKey.ALWAYS_ON_TOP.value, True))
        on_top_action.toggled.connect(self.action_handler.toggle_always_on_top)
        menu.addAction(on_top_action)

        fix_action = QAction(self.translator.translate("menu_position_fixed"), menu)
        fix_action.setCheckable(True)
        fix_action.setChecked(self.settings_manager.get_setting(SettingsKey.POSITION_FIXED.value, False))
        fix_action.toggled.connect(self.action_handler.toggle_position_lock)
        menu.addAction(fix_action)

        opacity_action = QAction(self.translator.translate("menu_change_opacity"), menu)
        opacity_action.triggered.connect(self.action_handler.show_opacity_dialog)
        menu.addAction(opacity_action)

    def _create_visibility_menu(self, menu: QMenu):
        """Erstellt das Menü zur Sichtbarkeit der Metriken."""
        display_menu = menu.addMenu(self.translator.translate("menu_display"))
        metric_order = self.settings_manager.get_setting(SettingsKey.METRIC_ORDER.value, []) or list(self.ui_manager.metric_widgets.keys())
        
        for key in metric_order:
            if not (widget_info := self.ui_manager.metric_widgets.get(key)):
                continue

            display_text = widget_info.get('full_text', key).strip().replace(':', '')
            action = QAction(display_text, display_menu)
            action.setCheckable(True)
            is_checked = self.settings_manager.get_setting(f"show_{key}", True)
            action.setChecked(is_checked)
            action.triggered.connect(partial(self.action_handler.toggle_metric_visibility, key, not is_checked))
            display_menu.addAction(action)

    def _create_hardware_selection_menu(self, menu: QMenu):
        """Erstellt das Menü zur Hardware-Auswahl."""
        hardware_menu = menu.addMenu(self.translator.translate("menu_hardware_select"))
        hw_manager = self.main_win.hw_manager
        
        cpus = {str(cpu.Identifier): cpu.Name for cpu in hw_manager.cpus}
        if cpus:
            self._create_exclusive_action_group_menu(
                hardware_menu, self.translator.translate("win_color_category_cpu"),
                SettingsKey.SELECTED_CPU_IDENTIFIER.value, cpus, 
                partial(self.action_handler.select_hardware, is_cpu=True, is_gpu=False)
            )
        
        nics = hw_manager.get_available_network_interfaces()
        self._create_exclusive_action_group_menu(hardware_menu, self.translator.translate("menu_nic_select"), SettingsKey.SELECTED_NETWORK_INTERFACE.value, {n: n for n in nics}, partial(self.action_handler.select_hardware, is_gpu=False, is_cpu=False))
        
        partitions = hw_manager.get_available_disk_partitions()
        self._create_exclusive_action_group_menu(hardware_menu, self.translator.translate("menu_disk_usage_select"), SettingsKey.SELECTED_DISK_PARTITION.value, {p: p for p in partitions}, partial(self.action_handler.select_hardware, is_gpu=False, is_cpu=False))
        
        disks = hw_manager.get_available_disks()
        self._create_exclusive_action_group_menu(hardware_menu, self.translator.translate("menu_disk_io_select"), SettingsKey.SELECTED_DISK_IO_DEVICE.value, {d: d for d in disks}, partial(self.action_handler.select_hardware, is_gpu=False, is_cpu=False))
        
        if hw_manager.gpu_supported:
            gpus = {str(gpu.Identifier): gpu.Name for gpu in hw_manager.gpus}
            self._create_exclusive_action_group_menu(hardware_menu, self.translator.translate("menu_gpu_select"), SettingsKey.SELECTED_GPU_IDENTIFIER.value, gpus, partial(self.action_handler.select_hardware, is_gpu=True, is_cpu=False))

    def _create_custom_sensors_menu(self, menu: QMenu):
        """Erstellt das Menü für Custom Sensors."""
        custom_menu = menu.addMenu(self.translator.translate("menu_custom_sensors"))
        
        manage_action = QAction(self.translator.translate("menu_custom_sensors_manage"), custom_menu)
        manage_action.triggered.connect(self.action_handler.show_custom_sensor_management)
        custom_menu.addAction(manage_action)
        
        custom_menu.addSeparator()
        
        custom_sensors = self.settings_manager.get_setting(SettingsKey.CUSTOM_SENSORS.value, {})
        enabled_sensors = {k: v for k, v in custom_sensors.items() if v.get('enabled', True)}
        
        if enabled_sensors:
            for sensor_id, sensor_data in enabled_sensors.items():
                metric_key = f"custom_{sensor_id}"
                display_name = sensor_data.get('display_name', f"Custom {sensor_id}")
                
                action = QAction(display_name, custom_menu)
                action.setCheckable(True)
                is_checked = self.settings_manager.get_setting(f"show_{metric_key}", True)
                action.setChecked(is_checked)
                action.triggered.connect(partial(self.action_handler.toggle_metric_visibility, metric_key, not is_checked))
                custom_menu.addAction(action)
        else:
            no_sensors_action = QAction(self.translator.translate("menu_custom_sensors_none"), custom_menu)
            no_sensors_action.setEnabled(False)
            custom_menu.addAction(no_sensors_action)

    def _create_tray_icon_menu(self, menu: QMenu):
        """Erstellt das Menü für die Tray-Icon-Einstellungen."""
        tray_menu = menu.addMenu(self.translator.translate("menu_tray_icon"))
        shapes = {s.value: self.translator.translate(f"menu_tray_shape_{s.name.lower()}") for s in TrayShape}
        self._create_exclusive_action_group_menu(tray_menu, self.translator.translate("menu_tray_shape"), SettingsKey.TRAY_SHAPE.value, shapes, self.action_handler.set_tray_setting)

        text_menu = tray_menu.addMenu(self.translator.translate("menu_tray_text"))
        is_text_shown = self.settings_manager.get_setting(SettingsKey.TRAY_SHOW_TEXT.value, False)
        show_text = QAction(self.translator.translate("menu_tray_text_show"), text_menu)
        show_text.setCheckable(True)
        show_text.setChecked(is_text_shown)
        show_text.toggled.connect(partial(self.action_handler.set_tray_setting, SettingsKey.TRAY_SHOW_TEXT.value))
        text_menu.addAction(show_text)
        text_menu.addAction(self.translator.translate("menu_tray_text_change"), self.action_handler.show_tray_text_dialog)
        text_menu.addAction(self.translator.translate("menu_tray_font_size"), self.action_handler.show_tray_font_size_dialog)

        is_border_enabled = self.settings_manager.get_setting(SettingsKey.TRAY_BORDER_ENABLED.value, True)
        border_action = QAction(self.translator.translate("menu_tray_border"), tray_menu)
        border_action.setCheckable(True)
        border_action.setChecked(is_border_enabled)
        border_action.toggled.connect(partial(self.action_handler.set_tray_setting, SettingsKey.TRAY_BORDER_ENABLED.value))
        tray_menu.addAction(border_action)
        tray_menu.addAction(self.translator.translate("menu_tray_border_width"), self.action_handler.show_tray_border_width_dialog)

        tray_menu.addSeparator()
        is_blinking_enabled = self.settings_manager.get_setting(SettingsKey.TRAY_BLINKING_ENABLED.value, False)
        blink_action = QAction(self.translator.translate("menu_tray_blinking"), tray_menu)
        blink_action.setCheckable(True)
        blink_action.setChecked(is_blinking_enabled)
        blink_action.toggled.connect(partial(self.action_handler.set_tray_setting, SettingsKey.TRAY_BLINKING_ENABLED.value))
        tray_menu.addAction(blink_action)
        tray_menu.addAction(self.translator.translate("menu_tray_blink_rate"), self.action_handler.show_blink_rate_dialog)
        tray_menu.addAction(self.translator.translate("menu_tray_blink_duration"), self.action_handler.show_blink_duration_dialog)

    def _create_config_menu(self, menu: QMenu):
        """Erstellt das Konfigurations-Hauptmenü."""
        config_menu = menu.addMenu(self.translator.translate("menu_config"))
        self._create_display_settings_menu(config_menu)
        config_menu.addSeparator()
        self._create_system_menu(config_menu)
        config_menu.addSeparator()
        self._create_language_menu(config_menu)
        config_menu.addSeparator()
        self._create_logging_menu(config_menu)
        config_menu.addSeparator()
        self._create_import_export_menu(config_menu)
        config_menu.addAction(self.translator.translate("menu_config_reset"), self.action_handler.reset_settings_to_default)
        config_menu.addAction(self.translator.translate("menu_config_open_folder"), self.action_handler.open_config_folder)

    def _create_display_settings_menu(self, parent_menu: QMenu):
        """Erstellt das Untermenü für Anzeige-Einstellungen."""
        settings_menu = parent_menu.addMenu(self.translator.translate("menu_config_display"))
        bar_graph_action = QAction(self.translator.translate("menu_config_bar_graphs"), settings_menu)
        bar_graph_action.setCheckable(True)
        bar_graph_action.setChecked(self.settings_manager.get_setting(SettingsKey.SHOW_BAR_GRAPHS.value, True))
        bar_graph_action.toggled.connect(self.action_handler.toggle_bar_graphs)
        settings_menu.addAction(bar_graph_action)

        settings_menu.addAction(
            self.translator.translate("menu_config_widget_appearance"),
            self.action_handler.show_widget_settings_window
        )
        settings_menu.addSeparator()

        settings_menu.addAction(self.translator.translate("menu_config_bar_width"), self.action_handler.show_bar_width_dialog)
        settings_menu.addAction(self.translator.translate("menu_config_bar_height"), self.action_handler.show_bar_height_dialog)
        settings_menu.addAction(self.translator.translate("menu_config_reorder"), self.action_handler.show_reorder_window)
        settings_menu.addAction(self.translator.translate("menu_config_font"), self.action_handler.show_font_dialog)
        settings_menu.addAction(self.translator.translate("menu_config_labels"), self.action_handler.show_label_editor_window)
        settings_menu.addSeparator()
        settings_menu.addAction(self.translator.translate("menu_config_misc"), self.action_handler.show_misc_settings_window)

    def _create_system_menu(self, parent_menu: QMenu):
        """Erstellt das Untermenü für System & Diagnose."""
        parent_menu.addAction(self.translator.translate("menu_monitoring_history"), self.action_handler.show_monitoring_window)
        parent_menu.addAction(self.translator.translate("menu_config_system_health"), self.action_handler.show_health_status_window)
        parent_menu.addAction(self.translator.translate("menu_config_sensor_diagnosis"), self.action_handler.show_sensor_diagnosis)
        parent_menu.addAction(self.translator.translate("menu_config_update_interval"), self.action_handler.show_update_interval_dialog)
        parent_menu.addAction(self.translator.translate("menu_config_alarms"), self.action_handler.show_alarm_settings_window)
        parent_menu.addAction(self.translator.translate("menu_config_performance"), self.action_handler.show_performance_settings_window)
        parent_menu.addAction(self.translator.translate("menu_config_colors"), self.action_handler.show_color_management)

    def _create_language_menu(self, parent_menu: QMenu):
        """Erstellt das Sprachauswahl-Menü."""
        languages = self.translator.get_available_languages()
        current_lang = self.settings_manager.get_setting("language", "german")
        options = {lang: lang.capitalize() for lang in languages}
        self._create_exclusive_action_group_menu(
            parent_menu, self.translator.translate("menu_language"),
            None, options, self.action_handler.set_language, current_value=current_lang
        )

    def _create_logging_menu(self, parent_menu: QMenu):
        """Erstellt das Logging-Untermenü."""
        logs_menu = parent_menu.addMenu(self.translator.translate("menu_config_logs"))
        logs_menu.addAction(self.translator.translate("menu_config_log_size"), self.action_handler.show_log_size_dialog)
        logs_menu.addAction(self.translator.translate("menu_config_log_backups"), self.action_handler.show_log_backup_dialog)
        logs_menu.addSeparator()
        self._create_exclusive_action_group_menu(
            logs_menu, self.translator.translate("menu_config_log_level"),
            "log_level", {"INFO": "INFO", "DEBUG": "DEBUG"},
            self.action_handler.set_logging_level
        )

    def _create_import_export_menu(self, parent_menu: QMenu):
        """Erstellt das Import/Export-Untermenü."""
        io_menu = parent_menu.addMenu(self.translator.translate("menu_config_import_export"))
        io_menu.addAction(self.translator.translate("menu_config_export"), self.action_handler.export_settings)
        io_menu.addAction(self.translator.translate("menu_config_import"), self.action_handler.import_settings)

    def _create_exclusive_action_group_menu(self, parent_menu: QMenu, title: str, 
                                          settings_key: Optional[str], options: Dict[str, str], 
                                          callback: Callable, current_value: Optional[str] = None):
        """Hilfsmethode zur Erstellung eines exklusiven Auswahlmenüs."""
        menu = parent_menu.addMenu(title)
        group = QActionGroup(menu)
        group.setExclusive(True)
        
        if current_value is None and settings_key:
            current_value = self.settings_manager.get_setting(settings_key)

        for value, text in options.items():
            action = QAction(text, menu)
            action.setCheckable(True)
            if value == current_value:
                action.setChecked(True)
            
            bound_callback = callback
            if settings_key:
                bound_callback = partial(callback, settings_key, value)
            else:
                bound_callback = partial(callback, value)

            action.triggered.connect(bound_callback)

            group.addAction(action)
            menu.addAction(action)