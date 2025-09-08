# config/default_values.py
from .constants import (
    DEFAULT_METRIC_ORDER, DEFAULT_GEOMETRY, DEFAULT_UPDATE_INTERVAL_MS,
    DEFAULT_BACKGROUND_ALPHA, NETWORK_INTERFACE_ALL,
    GPU_SELECTION_AUTO, TemperatureUnit,
    NetworkUnit, DiskIOUnit, ValueFormat, DisplayMode, DefaultColors,
    DefaultThresholds, DefaultFont, DefaultTrayIcon, DefaultLogging, FontWeight
)

DEFAULT_SETTINGS_BASE = {
    # Fenster & Layout
    "metric_order": DEFAULT_METRIC_ORDER.copy(),
    "geometry": DEFAULT_GEOMETRY.copy(),
    "background_alpha": DEFAULT_BACKGROUND_ALPHA,
    "background_color": DefaultColors.BACKGROUND,
    "position_fixed": False,
    "always_on_top": True,
    "font_family": "Fira Code",
    "font_size": DefaultFont.SIZE,
    "font_weight": FontWeight.BOLD.value,
    "update_interval_ms": DEFAULT_UPDATE_INTERVAL_MS,
    "docking_gap": 1,
    
    "show_bar_graphs": False,
    "bar_graph_width_multiplier": 9,
    
    "widget_min_width": 50,
    "widget_max_width": 2000,

    "bar_graph_height_factor": 0.65,
    "widget_padding_mode": "factor",
    "widget_padding_top": 2,
    "widget_padding_bottom": 2,
    "widget_padding_left": 5,
    "widget_padding_right": 5,
    "widget_padding_factor": 0.25,

    # Einheiten & Formatierung
    "temperature_unit": TemperatureUnit.CELSIUS.value,
    "network_unit": NetworkUnit.MBIT_S.value,
    "disk_io_unit": DiskIOUnit.MB_S.value,
    "value_format": ValueFormat.DECIMAL.value,
    "disk_io_display_mode": DisplayMode.BOTH.value,
    "network_display_mode": DisplayMode.BOTH.value,
    "custom_labels": {},
    "label_truncate_enabled": True,
    "label_truncate_length": 15,

    # --- GEÄNDERT: Sichtbarkeit der Anzeigen ---
    "show_cpu": True,
    "show_cpu_temp": True,
    "show_ram": True,
    "show_disk": False, # Standardmäßig ausgeblendet
    "show_disk_io": True,
    "show_net": True,
    "show_gpu": True,
    "show_gpu_hotspot": True,
    "show_gpu_memory_temp": True,
    "show_gpu_vram": True,
    "show_gpu_core_clock": True,
    "show_gpu_memory_clock": True,
    "show_gpu_power": True,

    # Hardware-Auswahl
    "selected_network_interface": NETWORK_INTERFACE_ALL,
    "selected_disk_partition": None,
    "selected_disk_io_device": None,
    "selected_gpu_identifier": GPU_SELECTION_AUTO,
    "selected_cpu_identifier": "auto",
    "visible_storage_temp_devices": ["all"],

    # --- GEÄNDERT: Farben ---
    "cpu_color": "#00AAFF",
    "cpu_temp_color": "#00AAFF",
    "ram_color": "#00A8FC",
    "disk_color": "#FF5500",
    "storage_temp_color": "#FF5500",
    "disk_io_color": "#FF5500",
    "net_color": "#00A2F3",
    "gpu_core_temp_color": "#FF5500",
    "gpu_hotspot_color": "#FF5500",
    "gpu_memory_temp_color": "#FF5500",
    "gpu_vram_color": "#FF5500",
    "gpu_core_clock_color": "#FF5500",
    "gpu_memory_clock_color": "#FF5500",
    "gpu_power_color": "#FF5500",

    # --- GEÄNDERT: Alarmfarben ---
    "cpu_alarm_color": "#FF0000",
    "cpu_temp_alarm_color": "#FF0000",
    "ram_alarm_color": "#FF0000",
    "disk_alarm_color": "#FF0000",
    "storage_temp_alarm_color": "#FF0000",
    "gpu_core_temp_alarm_color": "#FF0000",
    "gpu_hotspot_alarm_color": "#FF0000",
    "gpu_memory_temp_alarm_color": "#FF0000",
    "vram_alarm_color": "#FF0000", # Wunschgemäß auf #FF0000 geändert
    "disk_io_alarm_color": "#FF0000",
    "net_alarm_color": "#FF0000",
    "gpu_core_clock_alarm_color": "#FF0000",
    "gpu_memory_clock_alarm_color": "#FF0000",
    "gpu_power_alarm_color": "#FF0000",

    # Schwellenwerte für Alarme
    "cpu_threshold": DefaultThresholds.CPU_PERCENT,
    "cpu_temp_threshold": DefaultThresholds.CPU_TEMP,
    "ram_threshold": DefaultThresholds.RAM_PERCENT,
    "disk_threshold": DefaultThresholds.DISK_PERCENT,
    "storage_temp_threshold": DefaultThresholds.STORAGE_TEMP,
    "gpu_core_temp_threshold": DefaultThresholds.GPU_TEMP,
    "gpu_hotspot_threshold": DefaultThresholds.GPU_HOTSPOT_TEMP,
    "gpu_memory_temp_threshold": DefaultThresholds.GPU_MEMORY_TEMP,
    "vram_threshold": DefaultThresholds.VRAM_PERCENT,
    "disk_read_threshold": DefaultThresholds.DISK_READ_MBPS,
    "disk_write_threshold": DefaultThresholds.DISK_WRITE_MBPS,
    "net_up_threshold": DefaultThresholds.NET_UP_MBPS,
    "net_down_threshold": DefaultThresholds.NET_DOWN_MBPS,
    "gpu_core_clock_threshold": DefaultThresholds.GPU_CORE_CLOCK_MHZ,
    "gpu_memory_clock_threshold": DefaultThresholds.GPU_MEMORY_CLOCK_MHZ,
    "gpu_power_threshold": DefaultThresholds.GPU_POWER_W,

    # Tray Icon
    "tray_shape": DefaultTrayIcon.SHAPE.value,
    "tray_show_text": DefaultTrayIcon.SHOW_TEXT,
    "tray_custom_text": DefaultTrayIcon.TEXT,
    "tray_text_font_size": DefaultTrayIcon.FONT_SIZE,
    "tray_text_color": DefaultTrayIcon.TEXT_COLOR,
    "tray_border_enabled": DefaultTrayIcon.BORDER_ENABLED,
    "tray_icon_color": DefaultTrayIcon.COLOR,
    "tray_border_color": DefaultTrayIcon.BORDER_COLOR,
    "tray_icon_alarm_color": DefaultTrayIcon.ALARM_COLOR,
    "tray_border_thickness": DefaultTrayIcon.BORDER_THICKNESS,
    "tray_blinking_enabled": DefaultTrayIcon.BLINKING_ENABLED,
    "tray_blink_rate_sec": DefaultTrayIcon.BLINK_RATE_SEC,
    "tray_blink_duration_ms": DefaultTrayIcon.BLINK_DURATION_MS,

    # Logging-Einstellungen
    "log_max_size_mb": DefaultLogging.MAX_SIZE_MB,
    "log_backup_count": DefaultLogging.BACKUP_COUNT,

    # Performance Tracker Einstellungen
    "perf_mem_threshold_mb": 50,
    "perf_mem_check_interval_sec": 60,
    "perf_mem_trend_threshold_mb": 10,
    "perf_slow_update_threshold_sec": 5,
    "perf_gc_threshold_updates": 50,
    "perf_mem_baseline_mb": 0.0,
    "perf_show_warnings": True,

    # NEU: Monitoring-Standardwerte
    "monitoring_enabled": False,
    "monitoring_interval_sec": 60,
    "monitoring_max_file_size_mb": 100,
    "monitoring_max_duration_hours": 24
}