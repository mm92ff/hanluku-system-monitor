# detachable/magnetic_docking.py
from PySide6.QtCore import QRect, QPoint
from enum import Enum
from typing import Optional, Tuple

class DockingType(Enum):
    NONE = "none"
    HORIZONTAL = "horizontal"  # Widgets nebeneinander
    VERTICAL = "vertical"      # Widgets übereinander (Stack)

class DockingResult:
    """Ergebnis einer Docking-Operation mit Position und Typ"""
    def __init__(self, position: QPoint, docking_type: DockingType, target_rect: Optional[QRect] = None):
        self.position = position
        self.docking_type = docking_type
        self.target_rect = target_rect

class MagneticDocker:
    """
    Stellt die Logik zur Verfügung, um ein Rechteck an eine Liste anderer
    Rechtecke magnetisch andocken zu lassen.
    ERWEITERT: Erkennt vertikales und horizontales Docking für Stack-Gruppen.
    """
    def __init__(self, snap_distance: int = 15, gap: int = 1):
        self.snap_distance = snap_distance
        self.gap = gap

    def set_gap(self, new_gap: int):
        """Aktualisiert den Abstand zur Laufzeit."""
        self.gap = new_gap

    def calculate_snap_position(self, moving_rect: QRect, static_rects: list[QRect]) -> QPoint:
        """
        Berechnet die neue "angedockte" Position für das bewegte Rechteck.
        Rückwärtskompatible Methode - verwendet die neue Logik intern.
        """
        result = self.calculate_snap_with_type(moving_rect, static_rects)
        return result.position

    def calculate_snap_with_type(self, moving_rect: QRect, static_rects: list[QRect]) -> DockingResult:
        """
        Berechnet die neue Position UND den Docking-Typ für das bewegte Rechteck.
        """
        snap_x, snap_y = None, None
        min_dist_x, min_dist_y = self.snap_distance, self.snap_distance
        docking_type = DockingType.NONE
        target_rect = None

        original_pos = moving_rect.topLeft()

        for static_rect in static_rects:
            # Horizontales Andocken (nebeneinander) - X-Achse
            horizontal_checks = [
                (moving_rect.right(), static_rect.left() - self.gap, "right_to_left"),
                (moving_rect.left(), static_rect.right() + self.gap, "left_to_right"),
                (moving_rect.left(), static_rect.left(), "align_left"),
                (moving_rect.right(), static_rect.right(), "align_right"),
            ]
            
            for pos1, pos2, dock_side in horizontal_checks:
                dist = abs(pos1 - pos2)
                if dist < min_dist_x:
                    # Prüfe ob Widgets sich vertikal überschneiden (für horizontales Docking)
                    if self._rects_overlap_vertically(moving_rect, static_rect, pos2 - pos1):
                        min_dist_x = dist
                        snap_x = original_pos.x() - (pos1 - pos2)
                        docking_type = DockingType.HORIZONTAL
                        target_rect = static_rect

            # Vertikales Andocken (übereinander) - Y-Achse  
            vertical_checks = [
                (moving_rect.bottom(), static_rect.top() - self.gap, "bottom_to_top"),
                (moving_rect.top(), static_rect.bottom() + self.gap, "top_to_bottom"),
                (moving_rect.top(), static_rect.top(), "align_top"),
                (moving_rect.bottom(), static_rect.bottom(), "align_bottom"),
            ]
            
            for pos1, pos2, dock_side in vertical_checks:
                dist = abs(pos1 - pos2)
                if dist < min_dist_y:
                    # Prüfe ob Widgets sich horizontal überschneiden (für vertikales Docking)
                    if self._rects_overlap_horizontally(moving_rect, static_rect, pos2 - pos1):
                        min_dist_y = dist
                        snap_y = original_pos.y() - (pos1 - pos2)
                        # Vertikales Docking hat Priorität bei gleicher Distanz
                        if min_dist_y <= min_dist_x:
                            docking_type = DockingType.VERTICAL
                            target_rect = static_rect

        final_x = snap_x if snap_x is not None else original_pos.x()
        final_y = snap_y if snap_y is not None else original_pos.y()

        return DockingResult(QPoint(final_x, final_y), docking_type, target_rect)

    def _rects_overlap_vertically(self, rect1: QRect, rect2: QRect, x_offset: int = 0) -> bool:
        """
        Prüft ob zwei Rechtecke sich vertikal überschneiden.
        Wichtig für horizontales Docking - Widgets müssen auf ähnlicher Höhe sein.
        """
        adjusted_rect1 = QRect(rect1)
        adjusted_rect1.translate(x_offset, 0)
        
        return not (adjusted_rect1.bottom() < rect2.top() or adjusted_rect1.top() > rect2.bottom())

    def _rects_overlap_horizontally(self, rect1: QRect, rect2: QRect, y_offset: int = 0) -> bool:
        """
        Prüft ob zwei Rechtecke sich horizontal überschneiden.
        Wichtig für vertikales Docking - Widgets müssen seitlich überlappen.
        """
        adjusted_rect1 = QRect(rect1)
        adjusted_rect1.translate(0, y_offset)
        
        return not (adjusted_rect1.right() < rect2.left() or adjusted_rect1.left() > rect2.right())

    def find_best_docking_target(self, moving_rect: QRect, static_rects: list[QRect]) -> Optional[QRect]:
        """
        Findet das beste Ziel-Rechteck für Docking-Operationen.
        """
        result = self.calculate_snap_with_type(moving_rect, static_rects)
        return result.target_rect if result.docking_type != DockingType.NONE else None