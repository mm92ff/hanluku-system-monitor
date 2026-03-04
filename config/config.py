# config/config.py
import os
import logging
import json
import tempfile
from pathlib import Path
from logging.handlers import RotatingFileHandler

from config.constants import AppInfo, SettingsKey

def get_config_dir() -> Path:
    """Ermittelt das Konfigurationsverzeichnis im APPDATA-Ordner als Path-Objekt."""
    try:
        appdata = os.environ['APPDATA']
        config_dir = Path(appdata) / AppInfo.CONFIG_FOLDER_NAME
    except KeyError:
        config_dir = Path.home() / '.config' / AppInfo.CONFIG_FOLDER_NAME
    
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir

def save_atomic(data, target_path: str | Path) -> bool:
    """
    Speichert Daten atomar in eine JSON-Datei.
    Akzeptiert sowohl Strings als auch Path-Objekte.
    """
    try:
        # KORREKTUR: Stellt sicher, dass der Pfad immer ein Path-Objekt ist.
        target_path = Path(target_path)
        
        fd, temp_path_str = tempfile.mkstemp(dir=target_path.parent, prefix=".tmp")
        temp_path = Path(temp_path_str)

        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        
        temp_path.replace(target_path)
        return True
    except Exception:
        logging.exception(f"Fehler beim atomaren Speichern nach '{target_path}'.")
        return False

# --- Globale Konstanten ---
CONFIG_DIR = get_config_dir()
LOG_FILE = CONFIG_DIR / 'monitor.log'

def _create_rotating_log_handler(log_file: Path, max_bytes: int, backup_count: int) -> RotatingFileHandler:
    """Erzeugt einen fertig konfigurierten RotatingFileHandler."""
    handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding='utf-8',
    )
    formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(filename)s:%(lineno)d | %(message)s',
        '%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    return handler

def reconfigure_logging(settings: dict):
    """
    Rekonfiguriert den Root-Logger mit Werten aus den Einstellungen.
    """
    max_mb = settings.get(SettingsKey.LOG_MAX_SIZE_MB.value, 20)
    backup_count = settings.get(SettingsKey.LOG_BACKUP_COUNT.value, 5)
    log_level_name = settings.get(SettingsKey.LOG_LEVEL.value, "INFO").upper()
    level = logging.DEBUG if log_level_name == "DEBUG" else logging.INFO

    max_bytes = max_mb * 1024 * 1024
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    old_file_handlers = [
        handler for handler in root_logger.handlers
        if isinstance(handler, logging.FileHandler)
    ]

    try:
        new_handler = _create_rotating_log_handler(LOG_FILE, max_bytes, backup_count)
    except Exception:
        logging.exception(
            "Logging-Rekonfiguration fehlgeschlagen. Bisherige Log-Handler bleiben aktiv."
        )
        return False

    root_logger.addHandler(new_handler)

    for handler in old_file_handlers:
        root_logger.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            logging.debug("Alter Log-Handler konnte nicht sauber geschlossen werden.", exc_info=True)

    logging.info(f"Logging rekonfiguriert: Level={log_level_name}, max_size={max_mb}MB, backups={backup_count}")
    return True

def set_log_level(level_name: str):
    """Setzt das Log-Level zur Laufzeit."""
    level = logging.DEBUG if level_name.upper() == "DEBUG" else logging.INFO
    logging.getLogger().setLevel(level)
    logging.warning(f"Log-Level zur Laufzeit auf {level_name.upper()} geändert.")

def get_log_level_name() -> str:
    """Gibt den Namen des aktuellen Log-Levels zurück."""
    return logging.getLevelName(logging.getLogger().level)
