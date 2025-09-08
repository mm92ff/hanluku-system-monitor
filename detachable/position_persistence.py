# detachable/position_persistence.py
import json
import logging
from typing import Dict, Any
from pathlib import Path
from config.config import save_atomic

def save_layout(state: Dict[str, Any], config_dir: str | Path):
    """Speichert den Zustand der detachable Widgets atomar in einer JSON-Datei."""
    # KORREKTUR: Verwendet pathlib für konsistente Pfad-Objekte
    file_path = Path(config_dir) / 'detachable_layout.json'
    if save_atomic(state, file_path):
        logging.debug(f"Detachable-Layout gespeichert in: {file_path}")
    else:
        logging.error(f"Fehler beim Speichern des Detachable-Layouts nach: {file_path}")

def load_layout(config_dir: str | Path) -> Dict[str, Any]:
    """Lädt den Zustand der detachable Widgets aus einer JSON-Datei."""
    file_path = Path(config_dir) / 'detachable_layout.json'
    if not file_path.exists():
        return {}
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            if not content:
                return {}
            state = json.loads(content)
            logging.info(f"Detachable-Layout geladen von: {file_path}")
            return state if isinstance(state, dict) else {}
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logging.warning(f"Konnte Detachable-Layout nicht laden, starte mit Standard: {e}")
        return {}