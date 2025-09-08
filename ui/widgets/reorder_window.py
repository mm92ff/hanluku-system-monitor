# ui/widgets/reorder_window.py
from __future__ import annotations
import logging
import re
from typing import TYPE_CHECKING, Dict, List

from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QMessageBox
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIcon

from .base_window import SafeWindow
from config.constants import SettingsKey

if TYPE_CHECKING:
    from core.main_window import SystemMonitor


class ReorderWindow(SafeWindow):
    """
    Fenster zum Neuanordnen der Metrik-Anzeigen per Drag & Drop.
    """

    def __init__(self, main_app: SystemMonitor):
        super().__init__(main_app)
        self.main_app = main_app
        self.translator = main_app.translator
        self.settings_manager = main_app.settings_manager
        self.setWindowTitle(self.translator.translate("win_title_reorder"))

        try:
            self.setWindowIcon(self.main_app.tray_icon_manager.tray_icon.icon())
        except AttributeError:
            self.setWindowIcon(QIcon())

        self.setGeometry(400, 400, 400, 500)
        self.display_map: Dict[str, str] = {}
        self.clean_to_original_key: Dict[str, str] = {}
        self.original_to_clean_key: Dict[str, str] = {}

        self.init_ui()
        self.populate_mappings_and_load_order()

    def _sanitize_key(self, key: str) -> str:
        """Ersetzt alle nicht-alphanumerischen Zeichen durch einen Unterstrich."""
        return re.sub(r'[^a-zA-Z0-9_]', '_', key)

    def populate_mappings_and_load_order(self):
        """Erstellt Mappings und lädt die Liste."""
        all_widgets_info = self.main_app.ui_manager.metric_widgets
        for original_key, info in all_widgets_info.items():
            clean_key = self._sanitize_key(original_key)
            display_name = info.get('full_text', original_key).strip().replace(':', '')
            
            self.display_map[clean_key] = display_name
            self.clean_to_original_key[clean_key] = original_key
            self.original_to_clean_key[original_key] = clean_key

        self.load_current_order()

    def init_ui(self):
        """Initialisiert die Benutzeroberfläche."""
        layout = QVBoxLayout(self)
        instruction_label = QLabel(self.translator.translate("win_reorder_info"))
        layout.addWidget(instruction_label)

        self.list_widget = QListWidget(self)
        self.list_widget.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self.list_widget.setStyleSheet("QListWidget::item { margin: 5px; }")
        layout.addWidget(self.list_widget)

        button_layout = QHBoxLayout()
        save_button = QPushButton(self.translator.translate("win_shared_button_save_close"))
        save_button.clicked.connect(self.save_order_and_close)
        cancel_button = QPushButton(self.translator.translate("win_shared_button_cancel"))
        cancel_button.clicked.connect(self.close_safely)

        button_layout.addStretch()
        button_layout.addWidget(save_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)

    def load_current_order(self):
        """Lädt die aktuelle Reihenfolge und füllt die Liste."""
        self.list_widget.clear()
        current_original_order = self.settings_manager.get_setting(SettingsKey.METRIC_ORDER.value, [])
        
        ordered_clean_keys: List[str] = []
        seen_clean_keys = set()

        for original_key in current_original_order:
            clean_key = self.original_to_clean_key.get(original_key)
            if clean_key and clean_key not in seen_clean_keys:
                ordered_clean_keys.append(clean_key)
                seen_clean_keys.add(clean_key)
        
        all_clean_keys = set(self.clean_to_original_key.keys())
        for clean_key in all_clean_keys:
            if clean_key not in seen_clean_keys:
                ordered_clean_keys.append(clean_key)

        for clean_key in ordered_clean_keys:
            display_name = self.display_map.get(clean_key, clean_key)
            item = QListWidgetItem(display_name, self.list_widget)
            item.setData(Qt.ItemDataRole.UserRole, clean_key)

    def save_order_and_close(self):
        """Speichert die neue Reihenfolge und aktualisiert das UI robust ohne feste Timer."""
        try:
            # Schritt 1: Neue Reihenfolge aus der UI auslesen
            new_order_of_clean_keys = [self.list_widget.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.list_widget.count())]
            new_original_order = [self.clean_to_original_key.get(clean_key, clean_key) for clean_key in new_order_of_clean_keys]

            # Schritt 2: Neue Reihenfolge in den Einstellungen speichern
            self.settings_manager.set_setting(SettingsKey.METRIC_ORDER.value, new_original_order)
            
            # Schritt 3: Widgets direkt im UI neu anordnen
            self._reorder_widgets_directly(new_original_order)
            
            # Schritt 4: UI-Definitionen aktualisieren und Tray-Menü neu aufbauen
            self.main_app.ui_manager.refresh_metric_definitions()
            self.main_app.detachable_manager.sync_widgets_with_definitions()
            self.main_app.tray_icon_manager.rebuild_menu()
            
            # Schritt 5: Layout-Synchronisation sicher in den nächsten Event-Loop legen
            QTimer.singleShot(0, self.main_app.detachable_manager._synchronize_group_layout)

            logging.info("Neue Metrik-Reihenfolge erfolgreich angewendet.")
            self.close_safely()
        except Exception as e:
            logging.error(f"Fehler beim Speichern der Reihenfolge: {e}", exc_info=True)
            QMessageBox.warning(self, self.translator.translate("shared_error_title"), self.translator.translate("dlg_error_reorder_failed", error=e))

    def _reorder_widgets_directly(self, new_order: List[str]):
        """Ordnet die Widgets im Stack direkt entsprechend der neuen Reihenfolge an."""
        manager = self.main_app.detachable_manager
        
        if not manager.are_all_widgets_in_single_stack():
            return
        
        widgets_to_reorder = [manager.active_widgets[key] for key in new_order if key in manager.active_widgets]
        if len(widgets_to_reorder) < 2:
            return
        
        is_vertical = manager._is_vertical_arrangement(widgets_to_reorder)
        first_widget = widgets_to_reorder[0]
        start_x, start_y = first_widget.x(), first_widget.y()
        
        if is_vertical:
            current_y = start_y
            for widget in widgets_to_reorder:
                widget.move(start_x, current_y)
                current_y += widget.height() + manager.docker.gap
        else:
            current_x = start_x  
            for widget in widgets_to_reorder:
                widget.move(current_x, start_y)
                current_x += widget.width() + manager.docker.gap