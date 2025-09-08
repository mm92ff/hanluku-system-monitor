# core/sensor_mapping.py
import logging
import re
from typing import Dict, Optional, List, Tuple
from difflib import SequenceMatcher

# Erweiterte SENSOR_MAP mit mehreren Suchstrategien und Hardware-spezifischen Begriffen
SENSOR_MAP = {
    # CPU Temperature - erweitert für verschiedene Hersteller
    'CPU_PACKAGE_TEMP': {
        'search_terms': [
            # Intel-spezifisch
            'package', 'paket', 'gehäuse', 'cpu package', 'core package',
            # AMD-spezifisch  
            'tctl', 'tdie', 'core (tctl)', 'core (tdie)', 'core (tctl/tdie)',
            'cpu (tctl)', 'cpu (tdie)', 'amd cpu', 'ryzen',
            # Generisch
            'cpu temp', 'cpu temperature', 'processor', 'prozessor',
            'core temp', 'core temperature', 'cpu die', 'die temp'
        ],
        'exclude_terms': ['core 0', 'core 1', 'core 2', 'core 3', 'core 4', 'core 5', 'core 6', 'core 7'],
        'sensor_type': 'Temperature',
        'hardware_types': ['Cpu', 'CPU'],
        'priority_terms': ['package', 'tctl', 'tdie']  # Bevorzugte Begriffe
    },
    
    # GPU Core Temperature - erweitert für AMD/NVIDIA
    'GPU_CORE_TEMP': {
        'search_terms': [
            # NVIDIA-spezifisch
            'gpu core', 'gpu temperature', 'core temp', 'gpu temp', 'gpu-kern',
            'graphics temperature', 'nvidia',
            # AMD-spezifisch
            'gpu', 'radeon', 'amd gpu', 'graphics core', 'gpu die',
            # Generisch
            'temperature', 'temp', 'core'
        ],
        'exclude_terms': ['junction', 'hotspot', 'memory', 'mem'],
        'sensor_type': 'Temperature',
        'hardware_types': ['Gpu', 'GPU', 'GpuNvidia', 'GpuAmd'],
        'priority_terms': ['gpu core', 'gpu temp', 'gpu']
    },
    
    # GPU Hotspot - für beide Hersteller
    'GPU_HOTSPOT_TEMP': {
        'search_terms': [
            'hot spot', 'hotspot', 'junction', 'verbindungstemperatur',
            'gpu junction', 'tj-max', 'tjunction', 'gpu hotspot'
        ],
        'sensor_type': 'Temperature',
        'hardware_types': ['Gpu', 'GPU', 'GpuNvidia', 'GpuAmd'],
        'priority_terms': ['hotspot', 'junction']
    },
    
    # GPU Memory Temperature
    'GPU_MEMORY_TEMP': {
        'search_terms': [
            'memory junction', 'memory temp', 'mem junction', 'mem temp', 
            'speicherverbindung', 'vram temp', 'gpu memory', 'memory temperature',
            'mem junction temp', 'memory tj'
        ],
        'sensor_type': 'Temperature',
        'hardware_types': ['Gpu', 'GPU', 'GpuNvidia', 'GpuAmd'],
        'priority_terms': ['memory junction', 'mem junction', 'memory temp']
    },
    
    # GPU Core Clock - erweitert
    'GPU_CORE_CLOCK': {
        'search_terms': [
            'gpu core', 'core clock', 'gpu clock', 'gpu-kerntakt', 'kerntakt',
            'graphics clock', 'base clock', 'gpu speed', 'core speed',
            'shader clock', 'cuda clock'  # NVIDIA-spezifisch
        ],
        'exclude_terms': ['memory', 'mem', 'vram'],
        'sensor_type': 'Clock',
        'hardware_types': ['Gpu', 'GPU', 'GpuNvidia', 'GpuAmd'],
        'priority_terms': ['gpu core', 'core clock', 'gpu clock']
    },
    
    # GPU Memory Clock
    'GPU_MEMORY_CLOCK': {
        'search_terms': [
            'gpu memory', 'memory clock', 'mem clock', 'speichertakt',
            'vram clock', 'memory speed', 'mem speed', 'effective memory clock'
        ],
        'sensor_type': 'Clock',
        'hardware_types': ['Gpu', 'GPU', 'GpuNvidia', 'GpuAmd'],
        'priority_terms': ['memory clock', 'mem clock', 'gpu memory']
    },
    
    # GPU Power
    'GPU_POWER': {
        'search_terms': [
            'gpu package', 'gpu power', 'power', 'gpu-leistung', 'leistung',
            'total graphics power', 'board power', 'chip power', 'ppt',
            'power consumption', 'watt', 'w'
        ],
        'sensor_type': 'Power',
        'hardware_types': ['Gpu', 'GPU', 'GpuNvidia', 'GpuAmd'],
        'priority_terms': ['gpu power', 'power', 'gpu package']
    },
    
    # VRAM Usage
    'VRAM_USED': {
        'search_terms': [
            'gpu memory used', 'memory used', 'vram belegt', 'genutzter speicher',
            'dedicated memory used', 'gpu dedicated memory used', 'video memory used'
        ],
        'sensor_type': 'SmallData',
        'hardware_types': ['Gpu', 'GPU', 'GpuNvidia', 'GpuAmd'],
        'priority_terms': ['memory used', 'gpu memory used']
    },
    
    'VRAM_TOTAL': {
        'search_terms': [
            'gpu memory total', 'memory total', 'vram gesamt', 'gesamtspeicher',
            'dedicated memory total', 'gpu dedicated memory total', 'video memory total'
        ],
        'sensor_type': 'SmallData',
        'hardware_types': ['Gpu', 'GPU', 'GpuNvidia', 'GpuAmd'],
        'priority_terms': ['memory total', 'gpu memory total']
    },
    
    # Storage Temperature
    'STORAGE_TEMP': {
        'search_terms': ['temperature', 'temperatur', 'temp'],
        'sensor_type': 'Temperature',
        'hardware_types': ['Storage', 'Hdd', 'SSD', 'NVMe', 'M2']
    }
}

def similarity_score(a: str, b: str) -> float:
    """Berechnet die Ähnlichkeit zwischen zwei Strings (0.0 - 1.0)."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def find_sensor(canonical_name: str, hardware_item, debug_info: Optional[List[str]] = None) -> Optional[object]:
    """
    Findet den besten Sensor für einen kanonischen Namen, indem ein Hardware-Element 
    und dessen Unter-Hardware rekursiv durchsucht werden.
    """
    if debug_info is None:
        debug_info = []

    mapping = SENSOR_MAP.get(canonical_name)
    if not mapping:
        debug_info.append(f"❌ Kein Mapping für '{canonical_name}' in SENSOR_MAP gefunden")
        return None

    search_terms = mapping['search_terms']
    exclude_terms = mapping.get('exclude_terms', [])
    priority_terms = mapping.get('priority_terms', [])
    sensor_type_target = mapping['sensor_type'].lower()
    
    debug_info.append(f"🔍 Starte rekursive Suche nach '{canonical_name}' (Typ: {sensor_type_target}) auf '{hardware_item.Name}'")
    
    candidates = []
    
    def search_recursively(current_hw, depth=0):
        """Sammelt alle potenziellen Sensor-Kandidaten aus dem Hardware-Baum."""
        indent = "  " * depth
        debug_info.append(f"{indent} Lese Sensoren von '{current_hw.Name}'...")

        for sensor in current_hw.Sensors:
            sensor_name = sensor.Name.lower()
            sensor_type = str(sensor.SensorType).lower()

            if sensor_type != sensor_type_target:
                continue
            
            if any(exclude_term.lower() in sensor_name for exclude_term in exclude_terms):
                continue
            
            best_score = 0.0
            matched_term = ""
            is_priority = False
            
            for term in search_terms:
                term_lower = term.lower()
                
                if term_lower in sensor_name:
                    score = 1.0
                    if term in priority_terms:
                        score = 1.2
                        is_priority = True
                else:
                    score = similarity_score(term_lower, sensor_name)
                    if score > 0.6:
                        if term in priority_terms:
                            score += 0.1
                            is_priority = True
                
                if score > best_score:
                    best_score = score
                    matched_term = term
            
            if best_score > 0.3:
                candidates.append({
                    'sensor': sensor, 'score': best_score, 'term': matched_term,
                    'is_priority': is_priority, 'name': sensor.Name
                })
        
        for sub_hw in current_hw.SubHardware:
            sub_hw.Update()
            search_recursively(sub_hw, depth + 1)

    search_recursively(hardware_item)

    if not candidates:
        debug_info.append(f"   ❌ Keine passenden Kandidaten für '{canonical_name}' im gesamten Baum von '{hardware_item.Name}' gefunden.")
        logging.warning(f"Sensor '{canonical_name}' konnte auf '{hardware_item.Name}' oder dessen Unter-Hardware nicht gefunden werden.")
        return None
    
    candidates.sort(key=lambda x: (x['is_priority'], x['score']), reverse=True)
    
    best_candidate = candidates[0]
    debug_info.append(f"   ✅ Bester Kandidat gefunden: '{best_candidate['name']}' (Score: {best_candidate['score']:.2f}, Begriff: '{best_candidate['term']}')")
    
    if len(candidates) > 1:
        debug_info.append(f"   📋 {len(candidates)-1} weitere Kandidaten gefunden, z.B.: '{candidates[1]['name']}' (Score: {candidates[1]['score']:.2f})")

    logging.info(f"Sensor '{canonical_name}' erfolgreich auf '{hardware_item.Name}' gefunden: {best_candidate['name']}")
    return best_candidate['sensor']


def get_available_sensors_for_hardware(hardware_item) -> List[Dict]:
    """
    Hilfsfunktion für Debug: Gibt alle verfügbaren Sensoren einer Hardware zurück.
    """
    sensors = []
    for sensor in hardware_item.Sensors:
        sensors.append({
            'name': sensor.Name,
            'type': str(sensor.SensorType),
            'identifier': str(sensor.Identifier),
            'value': sensor.Value
        })
    return sensors

def diagnose_sensor_matching(canonical_name: str, hardware_item) -> str:
    """
    Detaillierte Diagnose für fehlgeschlagene Sensor-Zuordnungen.
    """
    debug_info = []
    find_sensor(canonical_name, hardware_item, debug_info)
    
    result = f"=== SENSOR DIAGNOSE: {canonical_name} ===\n"
    result += f"Hardware: {hardware_item.Name} ({hardware_item.HardwareType})\n\n"
    
    result += "🔍 Suchvorgang:\n"
    for info in debug_info:
        result += f"{info}\n"
    result += "\n"
    
    available_sensors = get_available_sensors_for_hardware(hardware_item)
    result += f"📋 Verfügbare Sensoren auf '{hardware_item.Name}' ({len(available_sensors)}):\n"
    for sensor in available_sensors:
        value_str = f"{sensor['value']:.2f}" if sensor['value'] is not None else "N/A"
        result += f"  - {sensor['name']} | Typ: {sensor['type']} | Wert: {value_str}\n"
    
    return result