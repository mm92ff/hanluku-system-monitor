# ui/widgets/graph_widget.py
import time
from typing import Dict, List, Tuple, Optional

from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QColor, QPen, QFont, QFontMetrics, QPolygonF
from PySide6.QtCore import Qt, QPointF

# NEU: Mapping von Metrik-Schlüsseln zu ihren Einheiten
METRIC_UNITS = {
    'cpu': '%',
    'cpu_temp': '°C',
    'ram': '%',
    'disk': '%',
    'gpu': '°C',
    'gpu_hotspot': '°C',
    'gpu_memory_temp': '°C',
    'gpu_vram': '%',
    'gpu_core_clock': 'MHz',
    'gpu_memory_clock': 'MHz',
    'gpu_power': 'W',
    'disk_read': 'MB/s',
    'disk_write': 'MB/s',
    'net_upload': 'Mbit/s', # Angenommen MBit/s für Netzwerk, anpassbar
    'net_download': 'Mbit/s', # Angenommen MBit/s für Netzwerk, anpassbar
    # Custom Sensors und Storage Temps haben keine generische Einheit,
    # können bei Bedarf hier hinzugefügt werden, wenn ihre Schlüssel bekannt sind.
    # z.B. 'storage_temp_SSD': '°C'
}


class GraphWidget(QWidget):
    """Ein Widget zur Darstellung von Sensor-Verlaufsdaten als Liniendiagramm."""

    def __init__(self, parent: QWidget = None, translator=None):
        super().__init__(parent)
        self.setMinimumHeight(200)
        self.translator = translator
        self.data: Dict[str, List[Tuple[float, float]]] = {}
        self.colors = ["#00FFFF", "#FF8C00", "#FF00FF", "#00FF00", "#FFFF00", "#DA70D6", "#FF5500"]
        self.padding = 50  # Rand für Achsenbeschriftungen
        self.current_metric_key: Optional[str] = None # NEU: Für die Einheit

    def set_data(self, data: Dict[str, List[Tuple[float, float]]], current_metric_key: Optional[str] = None):
        """Setzt die anzuzeigenden Daten und fordert eine Neuzeichnung an."""
        self.data = data
        self.current_metric_key = current_metric_key # NEU
        self.update()

    def paintEvent(self, event):
        """Zeichnet das Diagramm."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#282828"))

        if not self.data or not any(self.data.values()):
            self._draw_no_data_text(painter)
            return

        min_val, max_val, min_ts, max_ts = self._get_data_bounds()
        
        self._draw_axes_and_grid(painter, min_val, max_val, min_ts, max_ts)
        self._draw_graphs(painter, min_val, max_val, min_ts, max_ts)

    def _get_data_bounds(self) -> Tuple[float, float, float, float]:
        """Ermittelt die Min/Max-Werte für Werte und Zeitstempel."""
        all_values = [p[1] for points in self.data.values() for p in points]
        all_timestamps = [p[0] for points in self.data.values() for p in points]

        min_val = 0
        max_val = max(all_values) if all_values else 100
        min_ts = min(all_timestamps) if all_timestamps else time.time() - 3600
        max_ts = max(all_timestamps) if all_timestamps else time.time()
        
        # Puffer hinzufügen, damit Graphen nicht am Rand kleben
        if max_val == min_val:
            max_val += 1
        max_val *= 1.1
        if max_ts == min_ts: max_ts += 1

        return min_val, max_val, min_ts, max_ts

    def _draw_axes_and_grid(self, painter: QPainter, min_v: float, max_v: float, min_t: float, max_t: float):
        """Zeichnet die Achsen, das Gitter und die Beschriftungen."""
        painter.setPen(QPen(QColor("#555")))
        font = QFont("Consolas", 8)
        painter.setFont(font)
        fm = QFontMetrics(font)

        # Hol die Einheit für die aktuell ausgewählte Metrik
        unit = METRIC_UNITS.get(self.current_metric_key, '') # NEU

        # Horizontale Gitterlinien und Y-Achsen-Beschriftung
        num_y_labels = 5
        for i in range(num_y_labels + 1):
            val = min_v + (max_v - min_v) * i / num_y_labels
            y = self.height() - self.padding - (val - min_v) / (max_v - min_v) * (self.height() - 2 * self.padding)
            painter.drawLine(self.padding, y, self.width() - self.padding, y)
            
            # NEU: Einheit zur Beschriftung hinzufügen
            label = f"{val:.0f}{unit}" 
            painter.drawText(self.padding - fm.horizontalAdvance(label) - 5, y + fm.height() / 4, label)

        # Vertikale Gitterlinien und X-Achsen-Beschriftung
        num_x_labels = 4
        for i in range(num_x_labels + 1):
            ts = min_t + (max_t - min_t) * i / num_x_labels
            x = self.padding + (ts - min_t) / (max_t - min_t) * (self.width() - 2 * self.padding)
            if i > 0: painter.drawLine(x, self.padding, x, self.height() - self.padding)
            label = time.strftime("%H:%M", time.localtime(ts))
            painter.drawText(x - fm.horizontalAdvance(label) / 2, self.height() - self.padding + fm.height() + 5, label)

    def _draw_graphs(self, painter: QPainter, min_v: float, max_v: float, min_t: float, max_t: float):
        """Zeichnet die eigentlichen Graphen."""
        plot_width = self.width() - 2 * self.padding
        plot_height = self.height() - 2 * self.padding
        
        for i, (metric_key, points) in enumerate(self.data.items()):
            if not points: continue
            
            pen = QPen(QColor(self.colors[i % len(self.colors)]))
            pen.setWidth(2)
            painter.setPen(pen)

            polygon_points = []
            for timestamp, value in points:
                x = self.padding + ((timestamp - min_t) / (max_t - min_t)) * plot_width
                y = self.height() - self.padding - ((value - min_v) / (max_v - min_v)) * plot_height
                polygon_points.append(QPointF(x, y))
            
            if len(polygon_points) > 1:
                poly = QPolygonF(polygon_points)
                painter.drawPolyline(poly)
    
    def _draw_no_data_text(self, painter: QPainter):
        """Zeigt eine Nachricht an, wenn keine Daten vorhanden sind."""
        painter.setPen(Qt.GlobalColor.white)
        painter.setFont(QFont("Arial", 12))
        text = self.translator.translate("graph_no_data") if self.translator else "Select a sensor to display its history."
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, text)