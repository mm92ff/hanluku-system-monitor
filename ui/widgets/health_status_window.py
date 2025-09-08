# ui/widgets/health_status_window.py
import datetime
import json
import logging
from typing import Any, Dict

from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (QHeaderView, QHBoxLayout, QPushButton,
                               QStackedWidget, QTextEdit, QTreeWidget,
                               QTreeWidgetItem, QVBoxLayout)

from .base_window import SafeWindow

class HealthStatusWindow(SafeWindow):
    """Fenster zur Anzeige des System-Zustands, jetzt mehrsprachig und robuster."""

    def __init__(self, main_app):
        super().__init__(main_app)
        self.main_app = main_app
        self.translator = main_app.translator
        self.setWindowTitle(self.translator.translate("win_title_health"))

        try:
            self.setWindowIcon(self.main_app.tray_icon_manager.tray_icon.icon())
        except AttributeError:
            self.setWindowIcon(QIcon())

        self.setMinimumSize(600, 400)
        self.resize(800, 600)
        self.show_full_details = False
        self.last_data: Dict[str, Any] = {}

        self.init_ui()
        QTimer.singleShot(50, self.update_report)

    def init_ui(self):
        """Initialisiert die Benutzeroberfläche."""
        layout = QVBoxLayout(self)
        self.stacked_widget = QStackedWidget()
        layout.addWidget(self.stacked_widget)

        self.text_area = QTextEdit()
        self.text_area.setReadOnly(True)
        self.text_area.setFont(QFont("Consolas", 9))
        self.stacked_widget.addWidget(self.text_area)

        self.tree_widget = QTreeWidget()
        headers = [self.translator.translate("win_health_setting"), self.translator.translate("win_health_value")]
        self.tree_widget.setHeaderLabels(headers)
        self.tree_widget.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree_widget.setFont(QFont("Consolas", 9))
        self.stacked_widget.addWidget(self.tree_widget)

        button_layout = QHBoxLayout()
        self.detail_toggle_btn = QPushButton()
        self.detail_toggle_btn.clicked.connect(self.toggle_detail_view)
        button_layout.addWidget(self.detail_toggle_btn)
        button_layout.addStretch()

        refresh_btn = QPushButton(self.translator.translate("win_shared_button_refresh"))
        refresh_btn.clicked.connect(self.update_report)
        button_layout.addWidget(refresh_btn)
        close_btn = QPushButton(self.translator.translate("win_shared_button_close"))
        close_btn.clicked.connect(self.close_safely)
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)

        self._update_view_mode()

    def toggle_detail_view(self):
        """Wechselt zwischen vereinfachter und vollständiger Ansicht."""
        self.show_full_details = not self.show_full_details
        self._update_view_mode()

    def _update_view_mode(self):
        """Aktualisiert Button-Text und Ansicht basierend auf dem Modus."""
        text = self.translator.translate("win_health_simplified_details") if self.show_full_details else self.translator.translate("win_health_full_details")
        self.detail_toggle_btn.setText(text)
        self._update_view()

    def update_report(self):
        """Lädt neue Daten und aktualisiert die aktuelle Ansicht."""
        try:
            if not (self.main_app.worker and hasattr(self.main_app.worker, 'get_health_report')):
                self.text_area.setText(self.translator.translate("win_health_worker_unavailable"))
                return
            self.last_data = self.main_app.worker.get_health_report()
            self._update_view()
        except Exception:
            logging.exception("Fehler beim Abrufen des Health-Reports vom Worker.")
            self.text_area.setText(self.translator.translate("win_health_error_fetching"))
            self.last_data = {}

    def _update_view(self):
        """Aktualisiert die Anzeige basierend auf dem aktuellen Modus."""
        if self.show_full_details:
            self.tree_widget.clear()
            self._populate_tree(self.tree_widget, self.last_data)
            self.tree_widget.expandToDepth(1)
            self.stacked_widget.setCurrentWidget(self.tree_widget)
        else:
            report_text = self._create_simplified_report(self.last_data)
            self.text_area.setText(report_text)
            self.stacked_widget.setCurrentWidget(self.text_area)

    def _populate_tree(self, parent_item, data):
        """Füllt den QTreeWidget rekursiv mit Daten."""
        if isinstance(data, dict):
            for key, value in data.items():
                child = QTreeWidgetItem([str(key)])
                parent_item.addChild(child) if isinstance(parent_item, QTreeWidgetItem) else parent_item.addTopLevelItem(child)
                
                # SPEZIALFALL: Empfehlungen übersetzen
                if key == 'recommendations' and isinstance(value, list):
                    for reco_key in value:
                        reco_text = self.translator.translate(reco_key)
                        reco_child = QTreeWidgetItem(["-", reco_text])
                        child.addChild(reco_child)
                elif isinstance(value, (dict, list)):
                    self._populate_tree(child, value)
                else:
                    child.setText(1, str(self._format_value(key, value)))

        elif isinstance(data, list):
            for index, value in enumerate(data):
                child = QTreeWidgetItem([f"[{index}]"])
                parent_item.addChild(child)
                if isinstance(value, (dict, list)): self._populate_tree(child, value)
                else: child.setText(1, str(self._format_value(str(index), value)))

    def _format_value(self, key, value):
        """Formatiert Werte für eine bessere Lesbarkeit."""
        if isinstance(value, bool): return self.translator.translate("shared_yes") if value else self.translator.translate("shared_no")
        if isinstance(value, float):
            if "time_ms" in key: return f"{value:.2f} ms"
            if "_percent" in key: return f"{value:.2f} %"
            if "_mb" in key: return f"{value:.2f} MB"
            return f"{value:.4f}"
        if "runtime_seconds" in key: return str(datetime.timedelta(seconds=int(value)))
        if "time" in key.lower() and isinstance(value, (int, float)) and value > 1_000_000_000:
            try: return datetime.datetime.fromtimestamp(value).strftime('%Y-%m-%d %H:%M:%S')
            except (ValueError, OSError): pass
        return value

    def _create_simplified_report(self, data: dict) -> str:
        """Erstellt einen vereinfachten, lesbaren Bericht."""
        if not data: return self.translator.translate("win_health_no_data")
        
        lines = [f'{self.translator.translate("win_health_report_header")}\n']
        
        if ws := data.get('worker_status'):
            status = self.translator.translate("win_health_running") if ws.get('is_running', False) else self.translator.translate("win_health_stopped")
            lines.append(f"{self.translator.translate('win_health_worker_status'):<17} {status} ({self.translator.translate('win_health_consecutive_errors')} {ws.get('consecutive_errors', 0)})")
        
        if pt := data.get('performance_tracker'):
            if ps := pt.get('performance_stats'): 
                lines.append(f"{self.translator.translate('win_health_performance'):<17} {ps.get('avg_update_time_ms', 0):.1f}ms {self.translator.translate('win_health_per_update')} ({self.translator.translate('win_health_error_rate')} {ps.get('error_rate_percent', 0):.2f}%)")
            if ms := pt.get('memory_stats'):
                increase = ms.get('memory_increase_mb')
                increase_str = f"+{increase:.1f}" if increase and increase >= 0 else f"{increase or 0:.1f}"
                lines.append(f"{self.translator.translate('win_health_memory_usage'):<17} {ms.get('current_memory_mb', 0):.1f} MB ({self.translator.translate('win_health_change')} {increase_str} MB)")

        if sm := data.get('sensor_manager'): 
            lines.append(f"{self.translator.translate('win_health_sensor_status'):<17} {len(sm.get('permanently_failed_sensors', []))} {self.translator.translate('win_health_failed_sensors')} ({self.translator.translate('win_health_success_rate')} {sm.get('success_rate_percent', 0):.1f}%)")
            
        return "\n".join(lines)