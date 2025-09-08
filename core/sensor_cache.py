# core/sensor_cache.py
import json
import logging
import time
from typing import Dict, Optional
from pathlib import Path
from config.config import CONFIG_DIR, save_atomic

# KORREKTUR: Verwendet pathlib für konsistente Pfad-Objekte
CACHE_FILE = CONFIG_DIR / 'sensor_cache.json'
CACHE_VERSION = "2.0"  # Version für zukünftige Kompatibilitätsprüfungen

def load_sensor_cache() -> Dict[str, str]:
    """
    Lädt die Zuordnung von internen Sensor-Namen zu Hardware-Identifiern mit verbesserter Validierung.
    """
    if not CACHE_FILE.exists():
        logging.info("Keine Sensor-Cache-Datei gefunden. Wird beim ersten Start erstellt.")
        return _create_empty_cache()
    
    try:
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if not content:
                logging.warning("Sensor-Cache-Datei ist leer, erstelle neuen Cache")
                return _create_empty_cache()
            
            cache = json.loads(content)
            
            if not isinstance(cache, dict):
                logging.warning("Sensor-Cache enthält kein Dictionary, erstelle neuen Cache")
                return _create_empty_cache()
            
            # Cache-Version prüfen und ggf. migrieren
            cache_version = cache.get('_cache_version', '1.0')
            if cache_version != CACHE_VERSION:
                logging.info(f"Migriere Cache von Version {cache_version} auf {CACHE_VERSION}")
                cache = _migrate_cache(cache, cache_version)
            
            # Cache-Validierung
            if not _validate_cache_structure(cache):
                logging.warning("Cache-Struktur ungültig, erstelle neuen Cache")
                return _create_empty_cache()
            
            # Cache-Alter prüfen (Optional: Cache nach 30 Tagen als veraltet betrachten)
            cache_timestamp = cache.get('_created_timestamp', 0)
            if cache_timestamp > 0:
                cache_age_days = (time.time() - cache_timestamp) / (24 * 3600)
                if cache_age_days > 30:
                    logging.info(f"Cache ist {cache_age_days:.1f} Tage alt und wird als veraltet betrachtet")
                    # Behalten, aber mit Warnung - nicht automatisch löschen
            
            sensor_count = len([k for k in cache.keys() if not k.startswith('_')])
            logging.info(f"{sensor_count} Sensor-Identifier aus dem Cache geladen (Version {cache_version})")
            return cache
            
    except json.JSONDecodeError as e:
        logging.error(f"Sensor-Cache JSON-Dekodierung fehlgeschlagen: {e}")
        _backup_corrupted_cache()
        return _create_empty_cache()
    except FileNotFoundError:
        logging.info("Sensor-Cache-Datei nicht gefunden, erstelle neuen Cache")
        return _create_empty_cache()
    except Exception as e:
        logging.error(f"Unerwarteter Fehler beim Laden des Sensor-Cache: {e}")
        _backup_corrupted_cache()
        return _create_empty_cache()

def save_sensor_cache(cache: Dict[str, str]) -> bool:
    """
    Speichert die Zuordnung von internen Sensor-Namen zu Hardware-Identifiern atomar.
    Erweitert um Metadaten und Validierung.
    """
    try:
        # Cache-Metadaten hinzufügen/aktualisieren
        enriched_cache = cache.copy()
        enriched_cache['_cache_version'] = CACHE_VERSION
        enriched_cache['_last_updated'] = time.time()
        
        # Erstelle Timestamp nur beim ersten Mal
        if '_created_timestamp' not in enriched_cache:
            enriched_cache['_created_timestamp'] = time.time()
        
        # Statistiken hinzufügen
        sensor_count = len([k for k in cache.keys() if not k.startswith('_')])
        enriched_cache['_sensor_count'] = sensor_count
        
        # Validierung vor dem Speichern
        if not _validate_cache_structure(enriched_cache):
            logging.error("Cache-Struktur vor dem Speichern ungültig")
            return False
        
        # Atomares Speichern
        success = save_atomic(enriched_cache, CACHE_FILE)
        if success:
            logging.debug(f"Sensor-Cache gespeichert: {sensor_count} Sensoren")
        else:
            logging.error("Atomares Speichern des Sensor-Cache fehlgeschlagen")
        
        return success
        
    except Exception as e:
        logging.error(f"Fehler beim Speichern des Sensor-Cache: {e}")
        return False

def _create_empty_cache() -> Dict[str, str]:
    """Erstellt einen neuen, leeren Cache mit Metadaten."""
    return {
        '_cache_version': CACHE_VERSION,
        '_created_timestamp': time.time(),
        '_last_updated': time.time(),
        '_sensor_count': 0
    }

def _migrate_cache(old_cache: Dict[str, str], old_version: str) -> Dict[str, str]:
    """Migriert einen alten Cache auf die neue Version."""
    migrated_cache = {}
    
    # Kopiere alle Sensor-Einträge (nicht-interne Schlüssel)
    for key, value in old_cache.items():
        if not key.startswith('_'):
            migrated_cache[key] = value
    
    # Füge neue Metadaten hinzu
    migrated_cache['_cache_version'] = CACHE_VERSION
    migrated_cache['_created_timestamp'] = old_cache.get('_created_timestamp', time.time())
    migrated_cache['_last_updated'] = time.time()
    migrated_cache['_sensor_count'] = len(migrated_cache) - 3  # Minus Metadaten
    migrated_cache['_migrated_from'] = old_version
    
    logging.info(f"Cache erfolgreich von Version {old_version} migriert")
    return migrated_cache

def _validate_cache_structure(cache: Dict[str, str]) -> bool:
    """Validiert die Struktur und Integrität des Cache."""
    try:
        # Grundlegende Typ-Prüfung
        if not isinstance(cache, dict):
            return False
        
        # Metadaten-Prüfung
        required_meta_keys = ['_cache_version', '_created_timestamp', '_last_updated']
        for meta_key in required_meta_keys:
            if meta_key not in cache:
                logging.warning(f"Cache-Metadaten fehlen: {meta_key}")
                return False
        
        # Sensor-Einträge validieren
        sensor_entries = {k: v for k, v in cache.items() if not k.startswith('_')}
        
        for key, value in sensor_entries.items():
            # Sensor-Schlüssel sollten bestimmte Muster haben
            if not isinstance(key, str) or not isinstance(value, str):
                logging.warning(f"Ungültiger Cache-Eintrag: {key} -> {value}")
                return False
            
            # Wert sollte wie eine Hardware-Identifier aussehen
            if not value or len(value) < 5:
                logging.warning(f"Verdächtig kurzer Identifier: {key} -> {value}")
                return False
        
        # Sensor-Count validieren
        expected_count = len(sensor_entries)
        stored_count = cache.get('_sensor_count', -1)
        if stored_count != expected_count:
            logging.warning(f"Sensor-Count stimmt nicht überein: erwartet {expected_count}, gespeichert {stored_count}")
            # Nicht kritisch, da Count automatisch korrigiert werden kann
        
        return True
        
    except Exception as e:
        logging.error(f"Fehler bei Cache-Validierung: {e}")
        return False

def _backup_corrupted_cache():
    """Erstellt ein Backup einer korrupten Cache-Datei."""
    if not CACHE_FILE.exists():
        return
        
    try:
        import shutil
        backup_name = f"sensor_cache_corrupted_{int(time.time())}.json.bak"
        backup_path = CONFIG_DIR / backup_name
        shutil.copy2(CACHE_FILE, backup_path)
        logging.info(f"Korrupter Cache gesichert als: {backup_path}")
    except Exception as e:
        logging.error(f"Fehler beim Backup des korrupten Cache: {e}")

def get_cache_statistics() -> Dict[str, any]:
    """Gibt Statistiken über den aktuellen Cache zurück."""
    cache = load_sensor_cache()
    
    stats = {
        'cache_exists': CACHE_FILE.exists(),
        'cache_file_size': CACHE_FILE.stat().st_size if CACHE_FILE.exists() else 0,
        'cache_version': cache.get('_cache_version', 'unknown'),
        'sensor_count': len([k for k in cache.keys() if not k.startswith('_')]),
        'created_timestamp': cache.get('_created_timestamp', 0),
        'last_updated': cache.get('_last_updated', 0),
        'cache_age_days': 0
    }
    
    # Cache-Alter berechnen
    if stats['created_timestamp'] > 0:
        stats['cache_age_days'] = (time.time() - stats['created_timestamp']) / (24 * 3600)
    
    return stats

def clear_cache() -> bool:
    """Löscht die Cache-Datei komplett."""
    try:
        if CACHE_FILE.exists():
            # Backup vor dem Löschen
            _backup_corrupted_cache()
            CACHE_FILE.unlink()
            logging.info("Sensor-Cache erfolgreich gelöscht")
            return True
        else:
            logging.info("Sensor-Cache-Datei existiert nicht")
            return False
    except Exception as e:
        logging.error(f"Fehler beim Löschen des Sensor-Cache: {e}")
        return False

def invalidate_cache_for_hardware(hardware_fingerprint: str) -> bool:
    """Invalidiert den Cache, wenn sich die Hardware-Konfiguration geändert hat."""
    try:
        cache = load_sensor_cache()
        stored_fingerprint = cache.get('_hardware_fingerprint', '')
        
        if stored_fingerprint != hardware_fingerprint:
            logging.info("Hardware-Fingerprint hat sich geändert - Cache wird invalidiert")
            
            # Neuen Cache mit aktuellem Fingerprint erstellen
            new_cache = _create_empty_cache()
            new_cache['_hardware_fingerprint'] = hardware_fingerprint
            new_cache['_invalidated_reason'] = 'hardware_change'
            new_cache['_previous_fingerprint'] = stored_fingerprint
            
            return save_sensor_cache(new_cache)
        
        return False  # Kein Reset nötig
        
    except Exception as e:
        logging.error(f"Fehler bei Hardware-Fingerprint-Validierung: {e}")
        return False