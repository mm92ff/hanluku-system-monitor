# config/constants.py
"""
Zentrale Konstanten für die SystemMonitor-Anwendung.
Diese Datei definiert alle verwendeten Enum-Werte und Konstanten,
um "magic strings" zu vermeiden und die Wartbarkeit zu verbessern.
"""

from enum import Enum


# Application Identity
class AppInfo:
    NAME = "Hanluku-system-monitor"
    DISPLAY_NAME = "Hanluku-system-monitor"
    VERSION = "1.0"
    COMPANY = "Hanluku"
    
    # Windows-spezifische IDs
    APP_USER_MODEL_ID = f"{COMPANY}.{NAME}"
    CONFIG_FOLDER_NAME = NAME


class SettingsKey(Enum):
    """Zentralisiert alle Schlüssel für das Settings-Dictionary."""
    METRIC_ORDER = "metric_order"
    GEOMETRY = "geometry"
    BACKGROUND_ALPHA = "background_alpha"
    BACKGROUND_COLOR = "background_color"
    POSITION_FIXED = "position_fixed"
    ALWAYS_ON_TOP = "always_on_top"
    FONT_FAMILY = "font_family"
    FONT_SIZE = "font_size"
    FONT_WEIGHT = "font_weight"
    UPDATE_INTERVAL_MS = "update_interval_ms"
    SHOW_BAR_GRAPHS = "show_bar_graphs"
    BAR_GRAPH_WIDTH_MULTIPLIER = "bar_graph_width_multiplier"
    
    WIDGET_MIN_WIDTH = "widget_min_width"
    WIDGET_MAX_WIDTH = "widget_max_width"
    
    BAR_GRAPH_HEIGHT_FACTOR = "bar_graph_height_factor"
    WIDGET_PADDING_MODE = "widget_padding_mode"
    WIDGET_PADDING_TOP = "widget_padding_top"
    WIDGET_PADDING_BOTTOM = "widget_padding_bottom"
    WIDGET_PADDING_LEFT = "widget_padding_left"
    WIDGET_PADDING_RIGHT = "widget_padding_right"
    WIDGET_PADDING_FACTOR = "widget_padding_factor"
    
    TEMPERATURE_UNIT = "temperature_unit"
    NETWORK_UNIT = "network_unit"
    DISK_IO_UNIT = "disk_io_unit"
    VALUE_FORMAT = "value_format"
    DISK_IO_DISPLAY_MODE = "disk_io_display_mode"
    NETWORK_DISPLAY_MODE = "network_display_mode"
    CUSTOM_LABELS = "custom_labels"
    LABEL_TRUNCATE_ENABLED = "label_truncate_enabled"
    LABEL_TRUNCATE_LENGTH = "label_truncate_length"
    DOCKING_GAP = "docking_gap"
    SELECTED_NETWORK_INTERFACE = "selected_network_interface"
    SELECTED_DISK_PARTITION = "selected_disk_partition"
    SELECTED_DISK_IO_DEVICE = "selected_disk_io_device"
    SELECTED_GPU_IDENTIFIER = "selected_gpu_identifier"
    SELECTED_CPU_IDENTIFIER = "selected_cpu_identifier"
    CUSTOM_SENSORS = "custom_sensors"
    CPU_COLOR = "cpu_color"
    CPU_TEMP_COLOR = "cpu_temp_color"
    RAM_COLOR = "ram_color"
    DISK_COLOR = "disk_color"
    STORAGE_TEMP_COLOR = "storage_temp_color"
    DISK_IO_COLOR = "disk_io_color"
    NET_COLOR = "net_color"
    GPU_CORE_TEMP_COLOR = "gpu_core_temp_color"
    GPU_HOTSPOT_COLOR = "gpu_hotspot_color"
    GPU_MEMORY_TEMP_COLOR = "gpu_memory_temp_color"
    GPU_VRAM_COLOR = "gpu_vram_color"
    GPU_CORE_CLOCK_COLOR = "gpu_core_clock_color"
    GPU_MEMORY_CLOCK_COLOR = "gpu_memory_clock_color"
    GPU_POWER_COLOR = "gpu_power_color"
    CPU_ALARM_COLOR = "cpu_alarm_color"
    CPU_TEMP_ALARM_COLOR = "cpu_temp_alarm_color"
    RAM_ALARM_COLOR = "ram_alarm_color"
    DISK_ALARM_COLOR = "disk_alarm_color"
    STORAGE_TEMP_ALARM_COLOR = "storage_temp_alarm_color"
    GPU_CORE_TEMP_ALARM_COLOR = "gpu_core_temp_alarm_color"
    GPU_HOTSPOT_ALARM_COLOR = "gpu_hotspot_alarm_color"
    GPU_MEMORY_TEMP_ALARM_COLOR = "gpu_memory_temp_alarm_color"
    VRAM_ALARM_COLOR = "vram_alarm_color"
    
    DISK_IO_ALARM_COLOR = "disk_io_alarm_color"
    NET_ALARM_COLOR = "net_alarm_color"
    GPU_CORE_CLOCK_ALARM_COLOR = "gpu_core_clock_alarm_color"
    GPU_MEMORY_CLOCK_ALARM_COLOR = "gpu_memory_clock_alarm_color"
    GPU_POWER_ALARM_COLOR = "gpu_power_alarm_color"

    CPU_THRESHOLD = "cpu_threshold"
    CPU_TEMP_THRESHOLD = "cpu_temp_threshold"
    RAM_THRESHOLD = "ram_threshold"
    DISK_THRESHOLD = "disk_threshold"
    STORAGE_TEMP_THRESHOLD = "storage_temp_threshold"
    GPU_CORE_TEMP_THRESHOLD = "gpu_core_temp_threshold"
    GPU_HOTSPOT_THRESHOLD = "gpu_hotspot_threshold"
    GPU_MEMORY_TEMP_THRESHOLD = "gpu_memory_temp_threshold"
    VRAM_THRESHOLD = "vram_threshold"
    DISK_READ_THRESHOLD = "disk_read_threshold"
    DISK_WRITE_THRESHOLD = "disk_write_threshold"
    NET_UP_THRESHOLD = "net_up_threshold"
    NET_DOWN_THRESHOLD = "net_down_threshold"
    GPU_CORE_CLOCK_THRESHOLD = "gpu_core_clock_threshold"
    GPU_MEMORY_CLOCK_THRESHOLD = "gpu_memory_clock_threshold"
    GPU_POWER_THRESHOLD = "gpu_power_threshold"
    TRAY_SHAPE = "tray_shape"
    TRAY_SHOW_TEXT = "tray_show_text"
    TRAY_CUSTOM_TEXT = "tray_custom_text"
    TRAY_TEXT_FONT_SIZE = "tray_text_font_size"
    TRAY_TEXT_COLOR = "tray_text_color"
    TRAY_BORDER_ENABLED = "tray_border_enabled"
    TRAY_ICON_COLOR = "tray_icon_color"
    TRAY_BORDER_COLOR = "tray_border_color"
    TRAY_ICON_ALARM_COLOR = "tray_icon_alarm_color"
    TRAY_BORDER_THICKNESS = "tray_border_thickness"
    TRAY_BLINKING_ENABLED = "tray_blinking_enabled"
    TRAY_BLINK_RATE_SEC = "tray_blink_rate_sec"
    TRAY_BLINK_DURATION_MS = "tray_blink_duration_ms"
    LOG_MAX_SIZE_MB = "log_max_size_mb"
    LOG_BACKUP_COUNT = "log_backup_count"
    PERF_MEM_THRESHOLD_MB = "perf_mem_threshold_mb"
    PERF_MEM_CHECK_INTERVAL_SEC = "perf_mem_check_interval_sec"
    PERF_MEM_TREND_THRESHOLD_MB = "perf_mem_trend_threshold_mb"
    PERF_SLOW_UPDATE_THRESHOLD_SEC = "perf_slow_update_threshold_sec"
    PERF_GC_THRESHOLD_UPDATES = "perf_gc_threshold_updates"
    PERF_MEM_BASELINE_MB = "perf_mem_baseline_mb"
    PERF_SHOW_WARNINGS = "perf_show_warnings"
    
    # Monitoring-Einstellungen
    MONITORING_ENABLED = "monitoring_enabled"
    MONITORING_INTERVAL_SEC = "monitoring_interval_sec"
    MONITORING_MAX_FILE_SIZE_MB = "monitoring_max_file_size_mb"
    MONITORING_MAX_DURATION_HOURS = "monitoring_max_duration_hours"

    # Show/Hide Settings
    SHOW_CPU = "show_cpu"
    SHOW_CPU_TEMP = "show_cpu_temp"
    SHOW_RAM = "show_ram"
    SHOW_DISK = "show_disk"
    SHOW_DISK_IO = "show_disk_io"
    SHOW_NET = "show_net"
    SHOW_GPU = "show_gpu"
    SHOW_GPU_HOTSPOT = "show_gpu_hotspot"
    SHOW_GPU_MEMORY_TEMP = "show_gpu_memory_temp"
    SHOW_GPU_VRAM = "show_gpu_vram"
    SHOW_GPU_CORE_CLOCK = "show_gpu_core_clock"
    SHOW_GPU_MEMORY_CLOCK = "show_gpu_memory_clock"
    SHOW_GPU_POWER = "show_gpu_power"


# Neue Sensor-Typen für Custom Sensors
class CustomSensorType(Enum):
    TEMPERATURE = "Temperature"
    VOLTAGE = "Voltage" 
    FAN = "Fan"
    CLOCK = "Clock"
    LOAD = "Load"
    POWER = "Power"
    DATA = "Data"
    SMALLDATA = "SmallData"
    FACTOR = "Factor"
    FLOW = "Flow"
    CONTROL = "Control"
    LEVEL = "Level"
    THROUGHPUT = "Throughput"


# ERWEITERT: Layout-Abschnittskonstanten mit allen neuen Kategorien
class LayoutSection(Enum):
    """Definiert die Abschnitte in einem gespeicherten Layout."""
    WIDGETS = "widgets"
    FONT_SETTINGS = "font_settings"
    COLOR_SETTINGS = "color_settings"
    TRAY_SETTINGS = "tray_settings"
    WIDGET_SETTINGS = "widget_settings"
    OPACITY_SETTINGS = "opacity_settings"
    LABEL_SETTINGS = "label_settings"
    VISIBILITY_SETTINGS = "visibility_settings"
    HARDWARE_SETTINGS = "hardware_settings"
    UNIT_SETTINGS = "unit_settings"
    THRESHOLD_SETTINGS = "threshold_settings"
    SYSTEM_SETTINGS = "system_settings"
    WINDOW_SETTINGS = "window_settings"
    CUSTOM_SENSOR_SETTINGS = "custom_sensor_settings" # NEU


# ERWEITERT: Gruppierte Einstellungsschlüssel für das Layout-System
FONT_SETTING_KEYS = [
    SettingsKey.FONT_FAMILY.value,
    SettingsKey.FONT_SIZE.value,
    SettingsKey.FONT_WEIGHT.value
]

COLOR_SETTING_KEYS = [
    SettingsKey.BACKGROUND_COLOR.value,
    SettingsKey.CPU_COLOR.value,
    SettingsKey.CPU_TEMP_COLOR.value,
    SettingsKey.RAM_COLOR.value,
    SettingsKey.DISK_COLOR.value,
    SettingsKey.STORAGE_TEMP_COLOR.value,
    SettingsKey.DISK_IO_COLOR.value,
    SettingsKey.NET_COLOR.value,
    SettingsKey.GPU_CORE_TEMP_COLOR.value,
    SettingsKey.GPU_HOTSPOT_COLOR.value,
    SettingsKey.GPU_MEMORY_TEMP_COLOR.value,
    SettingsKey.GPU_VRAM_COLOR.value,
    SettingsKey.GPU_CORE_CLOCK_COLOR.value,
    SettingsKey.GPU_MEMORY_CLOCK_COLOR.value,
    SettingsKey.GPU_POWER_COLOR.value,
    SettingsKey.CPU_ALARM_COLOR.value,
    SettingsKey.CPU_TEMP_ALARM_COLOR.value,
    SettingsKey.RAM_ALARM_COLOR.value,
    SettingsKey.DISK_ALARM_COLOR.value,
    SettingsKey.STORAGE_TEMP_ALARM_COLOR.value,
    SettingsKey.GPU_CORE_TEMP_ALARM_COLOR.value,
    SettingsKey.GPU_HOTSPOT_ALARM_COLOR.value,
    SettingsKey.GPU_MEMORY_TEMP_ALARM_COLOR.value,
    SettingsKey.VRAM_ALARM_COLOR.value,
    SettingsKey.DISK_IO_ALARM_COLOR.value,
    SettingsKey.NET_ALARM_COLOR.value,
    SettingsKey.GPU_CORE_CLOCK_ALARM_COLOR.value,
    SettingsKey.GPU_MEMORY_CLOCK_ALARM_COLOR.value,
    SettingsKey.GPU_POWER_ALARM_COLOR.value
]

TRAY_SETTING_KEYS = [
    SettingsKey.TRAY_SHAPE.value,
    SettingsKey.TRAY_SHOW_TEXT.value,
    SettingsKey.TRAY_CUSTOM_TEXT.value,
    SettingsKey.TRAY_TEXT_FONT_SIZE.value,
    SettingsKey.TRAY_TEXT_COLOR.value,
    SettingsKey.TRAY_BORDER_ENABLED.value,
    SettingsKey.TRAY_ICON_COLOR.value,
    SettingsKey.TRAY_BORDER_COLOR.value,
    SettingsKey.TRAY_ICON_ALARM_COLOR.value,
    SettingsKey.TRAY_BORDER_THICKNESS.value,
    SettingsKey.TRAY_BLINKING_ENABLED.value,
    SettingsKey.TRAY_BLINK_RATE_SEC.value,
    SettingsKey.TRAY_BLINK_DURATION_MS.value
]

WIDGET_SETTING_KEYS = [
    SettingsKey.SHOW_BAR_GRAPHS.value,
    SettingsKey.BAR_GRAPH_WIDTH_MULTIPLIER.value,
    SettingsKey.BAR_GRAPH_HEIGHT_FACTOR.value,
    SettingsKey.WIDGET_MIN_WIDTH.value,
    SettingsKey.WIDGET_MAX_WIDTH.value,
    SettingsKey.WIDGET_PADDING_MODE.value,
    SettingsKey.WIDGET_PADDING_TOP.value,
    SettingsKey.WIDGET_PADDING_BOTTOM.value,
    SettingsKey.WIDGET_PADDING_LEFT.value,
    SettingsKey.WIDGET_PADDING_RIGHT.value,
    SettingsKey.WIDGET_PADDING_FACTOR.value
]

OPACITY_SETTING_KEYS = [
    SettingsKey.BACKGROUND_ALPHA.value
]

LABEL_SETTING_KEYS = [
    SettingsKey.CUSTOM_LABELS.value,
    SettingsKey.LABEL_TRUNCATE_ENABLED.value,
    SettingsKey.LABEL_TRUNCATE_LENGTH.value
]

VISIBILITY_SETTING_KEYS = [
    SettingsKey.SHOW_CPU.value,
    SettingsKey.SHOW_CPU_TEMP.value,
    SettingsKey.SHOW_RAM.value,
    SettingsKey.SHOW_DISK.value,
    SettingsKey.SHOW_DISK_IO.value,
    SettingsKey.SHOW_NET.value,
    SettingsKey.SHOW_GPU.value,
    SettingsKey.SHOW_GPU_HOTSPOT.value,
    SettingsKey.SHOW_GPU_MEMORY_TEMP.value,
    SettingsKey.SHOW_GPU_VRAM.value,
    SettingsKey.SHOW_GPU_CORE_CLOCK.value,
    SettingsKey.SHOW_GPU_MEMORY_CLOCK.value,
    SettingsKey.SHOW_GPU_POWER.value
]

HARDWARE_SETTING_KEYS = [
    SettingsKey.SELECTED_NETWORK_INTERFACE.value,
    SettingsKey.SELECTED_DISK_PARTITION.value,
    SettingsKey.SELECTED_DISK_IO_DEVICE.value,
    SettingsKey.SELECTED_GPU_IDENTIFIER.value,
    SettingsKey.SELECTED_CPU_IDENTIFIER.value
]

CUSTOM_SENSOR_SETTING_KEYS = [
    SettingsKey.CUSTOM_SENSORS.value
]

UNIT_SETTING_KEYS = [
    SettingsKey.TEMPERATURE_UNIT.value,
    SettingsKey.NETWORK_UNIT.value,
    SettingsKey.DISK_IO_UNIT.value,
    SettingsKey.VALUE_FORMAT.value,
    SettingsKey.DISK_IO_DISPLAY_MODE.value,
    SettingsKey.NETWORK_DISPLAY_MODE.value
]

THRESHOLD_SETTING_KEYS = [
    SettingsKey.CPU_THRESHOLD.value,
    SettingsKey.CPU_TEMP_THRESHOLD.value,
    SettingsKey.RAM_THRESHOLD.value,
    SettingsKey.DISK_THRESHOLD.value,
    SettingsKey.STORAGE_TEMP_THRESHOLD.value,
    SettingsKey.GPU_CORE_TEMP_THRESHOLD.value,
    SettingsKey.GPU_HOTSPOT_THRESHOLD.value,
    SettingsKey.GPU_MEMORY_TEMP_THRESHOLD.value,
    SettingsKey.VRAM_THRESHOLD.value,
    SettingsKey.DISK_READ_THRESHOLD.value,
    SettingsKey.DISK_WRITE_THRESHOLD.value,
    SettingsKey.NET_UP_THRESHOLD.value,
    SettingsKey.NET_DOWN_THRESHOLD.value,
    SettingsKey.GPU_CORE_CLOCK_THRESHOLD.value,
    SettingsKey.GPU_MEMORY_CLOCK_THRESHOLD.value,
    SettingsKey.GPU_POWER_THRESHOLD.value
]

SYSTEM_SETTING_KEYS = [
    SettingsKey.METRIC_ORDER.value,
    SettingsKey.UPDATE_INTERVAL_MS.value,
    SettingsKey.DOCKING_GAP.value
]

WINDOW_SETTING_KEYS = [
    SettingsKey.ALWAYS_ON_TOP.value,
    SettingsKey.POSITION_FIXED.value
]


class TrayShape(Enum):
    ROUND = "rund"
    SQUARE = "quadrat"
    TRIANGLE = "dreieck"
    HEXAGON = "sechseck"
    DIAMOND = "diamant"
    STAR = "stern"


class TemperatureUnit(Enum):
    CELSIUS = "C"
    KELVIN = "K"


class NetworkUnit(Enum):
    MBIT_S = "MBit/s"
    GBIT_S = "GBit/s"


class DiskIOUnit(Enum):
    MB_S = "MB/s"
    GB_S = "GB/s"


class ValueFormat(Enum):
    DECIMAL = "decimal"
    INTEGER = "integer"


class DisplayMode(Enum):
    BOTH = "both"
    UP = "up"
    DOWN = "down"
    READ = "read"
    WRITE = "write"


class FontWeight(Enum):
    NORMAL = "normal"
    BOLD = "bold"


class LogLevel(Enum):
    INFO = "INFO"
    DEBUG = "DEBUG"


DEFAULT_METRIC_ORDER = [
    "cpu", "cpu_temp", "ram", "disk", "disk_io", "net",
    "gpu", "gpu_hotspot", "gpu_memory_temp", "gpu_vram", "gpu_core_clock",
    "gpu_memory_clock", "gpu_power"
]

DEFAULT_GEOMETRY = [100, 100, 250, 200]


class DefaultColors:
    BACKGROUND = "#282828"
    WHITE = "#FFFFFF"
    ORANGE = "#FF8C00"
    CYAN = "#00FFFF"
    YELLOW = "#FFFF00"
    MAGENTA = "#DA70D6"
    PURPLE = "#FF00FF"
    GREEN = "#00FF00"
    RED = "#FF0000"
    ORANGE_RED = "#FF5500"
    LIGHT_ORANGE = "#FFAA00"
    GOLD = "#FFCC00"
    VIOLET = "#A020F0"
    GOLD_YELLOW = "#FFD700"
    ALARM_RED = "#FF4500"


class DefaultThresholds:
    CPU_PERCENT = 90.0
    CPU_TEMP = 95.0
    RAM_PERCENT = 90.0
    DISK_PERCENT = 90.0
    STORAGE_TEMP = 60.0
    GPU_TEMP = 90.0
    GPU_HOTSPOT_TEMP = 100.0
    GPU_MEMORY_TEMP = 100.0
    VRAM_PERCENT = 90.0
    DISK_READ_MBPS = 100.0
    DISK_WRITE_MBPS = 100.0
    NET_UP_MBPS = 100.0
    NET_DOWN_MBPS = 100.0
    GPU_CORE_CLOCK_MHZ = 3000.0
    GPU_MEMORY_CLOCK_MHZ = 20000.0
    GPU_POWER_W = 500.0


class DefaultFont:
    FAMILY = "Consolas"
    SIZE = 9
    WEIGHT = FontWeight.BOLD


class DefaultTrayIcon:
    SHAPE = TrayShape.ROUND
    SHOW_TEXT = False
    TEXT = "CPU"
    FONT_SIZE = 12
    TEXT_COLOR = DefaultColors.WHITE
    BORDER_ENABLED = True
    COLOR = "#FFA500"
    BORDER_COLOR = DefaultColors.WHITE
    ALARM_COLOR = DefaultColors.RED
    BORDER_THICKNESS = 1
    BLINKING_ENABLED = True
    BLINK_RATE_SEC = 1
    BLINK_DURATION_MS = 500


class DefaultLogging:
    MAX_SIZE_MB = 20
    BACKUP_COUNT = 5


DEFAULT_UPDATE_INTERVAL_MS = 2000
DEFAULT_BACKGROUND_ALPHA = 200
NETWORK_INTERFACE_ALL = "all"
GPU_SELECTION_AUTO = "auto"