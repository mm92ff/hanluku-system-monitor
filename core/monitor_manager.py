# core/monitor_manager.py
from __future__ import annotations
import logging
from typing import Dict, List, Tuple, Optional, NamedTuple
from dataclasses import dataclass

from PySide6.QtCore import QRect, QSize, QPoint
from PySide6.QtGui import QScreen
from PySide6.QtWidgets import QApplication


@dataclass
class MonitorInfo:
    """Informationen über einen Monitor."""
    name: str
    geometry: QRect  # Absolute Position und Größe
    available_geometry: QRect  # Ohne Taskbar etc.
    is_primary: bool
    device_pixel_ratio: float
    physical_size: QSize  # in mm


class PositionValidationResult(NamedTuple):
    """Ergebnis der Positions-Validierung."""
    is_valid: bool
    corrected_position: Optional[QPoint]
    target_monitor: Optional[str]
    reason: str


class MonitorManager:
    """
    Verwaltet Multimonitor-Unterstützung für das SystemMonitor-Programm.
    Behandelt Monitor-Erkennung, Positions-Validierung und intelligente Repositionierung.
    """
    
    def __init__(self):
        self.monitors: Dict[str, MonitorInfo] = {}
        self.primary_monitor: Optional[str] = None
        self.update_monitor_info()
        
    def update_monitor_info(self) -> bool:
        """
        Aktualisiert die Monitor-Informationen und gibt zurück, ob sich die Konfiguration geändert hat.
        """
        old_monitors = self.monitors
        self.monitors = {}
        
        try:
            app = QApplication.instance()
            if not app:
                logging.error("Keine QApplication-Instanz für Monitor-Erkennung verfügbar.")
                return False
            
            screens = app.screens()
            if not screens:
                logging.warning("Keine Bildschirme durch QApplication gefunden.")
                return len(old_monitors) > 0

            primary_screen = app.primaryScreen()
            for i, screen in enumerate(screens):
                monitor_name = screen.name() or f"Monitor_{i}"
                monitor_info = MonitorInfo(
                    name=monitor_name,
                    geometry=screen.geometry(),
                    available_geometry=screen.availableGeometry(),
                    is_primary=(screen == primary_screen),
                    device_pixel_ratio=screen.devicePixelRatio(),
                    physical_size=screen.physicalSize()
                )
                self.monitors[monitor_name] = monitor_info
                if monitor_info.is_primary:
                    self.primary_monitor = monitor_name
            
            # Prüfe auf relevante Änderungen in Anzahl, Namen oder Geometrie
            configuration_changed = (
                old_monitors.keys() != self.monitors.keys() or
                any(old_monitors[name].geometry != info.geometry for name, info in self.monitors.items())
            )
            
            if configuration_changed:
                self._log_monitor_configuration()
                
            return configuration_changed
            
        except Exception as e:
            logging.error(f"Fehler beim Aktualisieren der Monitor-Info: {e}", exc_info=True)
            return False

    def _get_target_monitor(self, preferred_monitor_name: Optional[str] = None) -> Optional[MonitorInfo]:
        """
        NEUE HILFSMETHODE: Zentralisiert die Logik zur Auswahl des Zielmonitors.
        Sucht nach dem bevorzugten, dann dem primären, dann dem ersten verfügbaren Monitor.
        """
        if not self.monitors:
            return None

        # 1. Bevorzugten Monitor prüfen
        if preferred_monitor_name and preferred_monitor_name in self.monitors:
            return self.monitors[preferred_monitor_name]
        
        # 2. Primären Monitor als Fallback
        if self.primary_monitor and self.primary_monitor in self.monitors:
            return self.monitors[self.primary_monitor]
            
        # 3. Ersten verfügbaren Monitor als letzten Ausweg
        return next(iter(self.monitors.values()))

    def get_monitor_at_position(self, position: QPoint) -> Optional[str]:
        """Findet den Namen des Monitors an der angegebenen Position."""
        for name, monitor in self.monitors.items():
            if monitor.geometry.contains(position):
                return name
        return None
    
    def validate_position(self, position: QPoint, size: Optional[QSize] = None) -> PositionValidationResult:
        """Validiert eine Fensterposition und schlägt bei Bedarf Korrekturen vor."""
        if not self.monitors:
            return PositionValidationResult(False, None, None, "Keine Monitore verfügbar")
        
        target_monitor_name = self.get_monitor_at_position(position)
        
        if target_monitor_name:
            if size:
                window_rect = QRect(position, size)
                monitor_rect = self.monitors[target_monitor_name].available_geometry
                if monitor_rect.contains(window_rect):
                    return PositionValidationResult(True, position, target_monitor_name, "Position ist vollständig sichtbar")
                
                corrected_pos = self._clamp_to_monitor(position, size, target_monitor_name)
                return PositionValidationResult(False, corrected_pos, target_monitor_name, "Position korrigiert, um auf Monitor zu passen")
            return PositionValidationResult(True, position, target_monitor_name, "Position ist auf Monitor sichtbar")
        
        corrected_pos, best_monitor = self._find_best_alternative_position(position, size)
        return PositionValidationResult(False, corrected_pos, best_monitor, "Position war außerhalb aller Monitore")
    
    def get_safe_position_for_new_window(self, size: QSize, preferred_monitor: Optional[str] = None) -> QPoint:
        """
        Findet eine sichere, zentrierte Position für ein neues Fenster.
        ÜBERARBEITET: Nutzt die zentralisierte _get_target_monitor Methode.
        """
        target_monitor = self._get_target_monitor(preferred_monitor)
        if not target_monitor:
            return QPoint(100, 100)  # Notfall-Position
        
        available = target_monitor.available_geometry
        x = available.x() + (available.width() - size.width()) // 2
        y = available.y() + (available.height() - size.height()) // 2
        
        return QPoint(max(available.x(), x), max(available.y(), y))
    
    def get_cascade_position(self, window_index: int, size: QSize, monitor_name: Optional[str] = None) -> QPoint:
        """
        Berechnet eine Kaskaden-Position für gestapelte Fenster.
        ÜBERARBEITET: Nutzt die zentralisierte _get_target_monitor Methode.
        """
        target_monitor = self._get_target_monitor(monitor_name)
        if not target_monitor:
            return QPoint(100 + window_index * 30, 100 + window_index * 30)

        cascade_offset = 30
        available = target_monitor.available_geometry
        
        base_x = available.x() + 50 + window_index * cascade_offset
        base_y = available.y() + 50 + window_index * cascade_offset
        
        # Stelle sicher, dass das Fenster innerhalb des sichtbaren Bereichs bleibt
        final_x = min(base_x, available.right() - size.width())
        final_y = min(base_y, available.bottom() - size.height())
        
        return QPoint(max(available.x(), final_x), max(available.y(), final_y))
    
    def repair_invalid_positions(self, positions: Dict[str, QPoint], sizes: Optional[Dict[str, QSize]] = None) -> Dict[str, QPoint]:
        """Repariert eine Liste von Positionen, die außerhalb sichtbarer Bereiche liegen."""
        corrected_positions = {}
        sizes = sizes or {}
        
        for widget_name, position in positions.items():
            widget_size = sizes.get(widget_name, QSize(200, 50))
            validation_result = self.validate_position(position, widget_size)
            
            if validation_result.is_valid:
                corrected_positions[widget_name] = position
            elif validation_result.corrected_position:
                corrected_pos = validation_result.corrected_position
                corrected_positions[widget_name] = corrected_pos
                logging.info(f"Position für '{widget_name}' korrigiert: {position} -> {corrected_pos}")
            else:
                safe_pos = self.get_safe_position_for_new_window(widget_size)
                corrected_positions[widget_name] = safe_pos
                logging.warning(f"Konnte Position für '{widget_name}' nicht korrigieren, setze auf sichere Position: {safe_pos}")
        
        return corrected_positions
    
    def get_monitor_info(self, monitor_name: Optional[str] = None) -> Optional[MonitorInfo]:
        """
        Gibt Informationen über einen spezifischen Monitor zurück (oder den primären, wenn keiner benannt ist).
        """
        target_monitor = self._get_target_monitor(monitor_name)
        return target_monitor

    def get_all_monitor_names(self) -> List[str]:
        """Gibt eine Liste aller verfügbaren Monitor-Namen zurück."""
        return list(self.monitors.keys())
    
    def _clamp_to_monitor(self, position: QPoint, size: QSize, monitor_name: str) -> QPoint:
        """Passt die Position an, damit das Fenster vollständig auf dem Monitor sichtbar ist."""
        monitor = self.monitors.get(monitor_name)
        if not monitor:
            return position
        
        monitor_rect = monitor.available_geometry
        new_x = max(monitor_rect.x(), min(position.x(), monitor_rect.right() - size.width()))
        new_y = max(monitor_rect.y(), min(position.y(), monitor_rect.bottom() - size.height()))
        
        return QPoint(new_x, new_y)
    
    def _find_best_alternative_position(self, position: QPoint, size: Optional[QSize] = None) -> Tuple[Optional[QPoint], Optional[str]]:
        """Findet die beste alternative Position auf dem nächstgelegenen sichtbaren Monitor."""
        if not self.monitors:
            return None, None
        
        # Finde den Monitor, dessen Zentrum am nächsten zur ungültigen Position liegt
        min_distance = float('inf')
        best_monitor_name = None
        for name, monitor in self.monitors.items():
            center = monitor.geometry.center()
            distance = (position - center).manhattanLength()
            if distance < min_distance:
                min_distance = distance
                best_monitor_name = name
        
        if best_monitor_name:
            safe_size = size or QSize(200, 50)
            return self.get_safe_position_for_new_window(safe_size, best_monitor_name), best_monitor_name
        
        return None, None
    
    def _log_monitor_configuration(self):
        """Loggt die aktuell erkannte Monitor-Konfiguration."""
        logging.info(f"Monitor-Konfiguration aktualisiert: {len(self.monitors)} Monitore gefunden.")
        for name, monitor in self.monitors.items():
            primary_tag = "[PRIMARY]" if monitor.is_primary else ""
            logging.info(
                f"  - {name}: {monitor.geometry.width()}x{monitor.geometry.height()} "
                f"bei ({monitor.geometry.x()},{monitor.geometry.y()}) {primary_tag}"
            )
    
    def __str__(self) -> str:
        return f"MonitorManager({len(self.monitors)} monitors, primary: {self.primary_monitor})"