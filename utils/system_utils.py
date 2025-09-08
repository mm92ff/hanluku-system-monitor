# utils/system_utils.py
import logging

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None
    PSUTIL_AVAILABLE = False
    logging.warning(
        "psutil library not found. System metrics (I/O, RAM, etc.) will be unavailable."
    )