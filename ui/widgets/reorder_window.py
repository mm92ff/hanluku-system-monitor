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

from .base_window import (
    SafeWindow,
    configure_dialog_layout,
    configure_dialog_window,
    style_dialog_button,
    style_list_widget,
)
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

        configure_dialog_window(self, 400, 500)
        self.display_map: Dict[str, str] = {}
        self.clean_to_original_key: Dict[str, str] = {}
        self.original_to_clean_key: Dict[str, str] = {}

        self.init_ui()
        self.populate_mappings_and_load_order()

    def _sanitize_key(self, key: str) -> str:
        """Ersetzt alle nicht-alphanumerischen Zeichen durch einen Unterstrich."""
        return re.sub(r'[^a-zA-Z0-9_]', '_', key)

    def _get_reorderable_original_keys(self) -> List[str]:
        """Gibt nur die aktuell ausgewählten/aktiven Widgets in stabiler Reihenfolge zurück."""
        current_order = self.settings_manager.get_setting(SettingsKey.METRIC_ORDER.value, [])
        active_keys = set(self.main_app.detachable_manager.active_widgets.keys())

        ordered_active_keys = [key for key in current_order if key in active_keys]
        remaining_active_keys = [
            key for key in self.main_app.detachable_manager.active_widgets.keys()
            if key not in ordered_active_keys
        ]
        return ordered_active_keys + remaining_active_keys

    def populate_mappings_and_load_order(self):
        """Erstellt Mappings und lädt die Liste."""
        all_widgets_info = self.main_app.ui_manager.metric_widgets
        for original_key in self._get_reorderable_original_keys():
            info = all_widgets_info.get(original_key)
            if not info:
                continue
            clean_key = self._sanitize_key(original_key)
            display_name = info.get('full_text', original_key).strip().replace(':', '')
            
            self.display_map[clean_key] = display_name
            self.clean_to_original_key[clean_key] = original_key
            self.original_to_clean_key[original_key] = clean_key

        self.load_current_order()

    def init_ui(self):
        """Initialisiert die Benutzeroberfläche."""
        layout = QVBoxLayout(self)
        configure_dialog_layout(layout)
        instruction_label = QLabel(self.translator.translate("win_reorder_info"))
        layout.addWidget(instruction_label)

        self.list_widget = QListWidget(self)
        self.list_widget.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        style_list_widget(self.list_widget, item_margin=5)
        layout.addWidget(self.list_widget)

        button_layout = QHBoxLayout()
        save_button = QPushButton(self.translator.translate("win_shared_button_save_close"))
        save_button.clicked.connect(self.save_order_and_close)
        cancel_button = QPushButton(self.translator.translate("win_shared_button_cancel"))
        cancel_button.clicked.connect(self.close_safely)
        style_dialog_button(save_button, "primary")
        style_dialog_button(cancel_button, "secondary")

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

    def _build_complete_metric_order(self, reordered_visible_keys: List[str]) -> List[str]:
        """Mischt die neue sichtbare Reihenfolge in die vollständige globale Reihenfolge ein."""
        current_order = self.settings_manager.get_setting(SettingsKey.METRIC_ORDER.value, [])
        reorderable_keys = set(self.clean_to_original_key.values())

        full_metric_order: List[str] = []
        seen_keys = set()
        for key in current_order:
            if key not in seen_keys:
                full_metric_order.append(key)
                seen_keys.add(key)

        for key in self.main_app.ui_manager.metric_widgets.keys():
            if key not in seen_keys:
                full_metric_order.append(key)
                seen_keys.add(key)

        reordered_iter = iter(reordered_visible_keys)
        merged_order: List[str] = []
        for key in full_metric_order:
            if key in reorderable_keys:
                next_visible_key = next(reordered_iter, None)
                if next_visible_key is not None:
                    merged_order.append(next_visible_key)
            else:
                merged_order.append(key)

        for remaining_key in reordered_iter:
            if remaining_key not in merged_order:
                merged_order.append(remaining_key)

        return merged_order

    def save_order_and_close(self):
        """Speichert die neue Reihenfolge und aktualisiert das UI robust ohne feste Timer."""
        try:
            # Schritt 1: Neue Reihenfolge aus der UI auslesen
            new_order_of_clean_keys = [self.list_widget.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.list_widget.count())]
            new_visible_order = [self.clean_to_original_key.get(clean_key, clean_key) for clean_key in new_order_of_clean_keys]
            new_original_order = self._build_complete_metric_order(new_visible_order)

            # Schritt 2: Neue Reihenfolge in den Einstellungen speichern
            self.settings_manager.set_setting(SettingsKey.METRIC_ORDER.value, new_original_order)
            
            # Schritt 3: Widgets direkt im UI neu anordnen
            self._reorder_widgets_directly(new_visible_order)
            
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

    def export_language_refresh_state(self) -> dict:
        return {
            "order": [
                self.list_widget.item(i).data(Qt.ItemDataRole.UserRole)
                for i in range(self.list_widget.count())
            ]
        }

    def apply_language_refresh_state(self, state: dict):
        desired_order = state.get("order", [])
        if not desired_order:
            return

        current_items = {}
        while self.list_widget.count():
            item = self.list_widget.takeItem(0)
            current_items[item.data(Qt.ItemDataRole.UserRole)] = item

        for clean_key in desired_order:
            item = current_items.pop(clean_key, None)
            if item is not None:
                self.list_widget.addItem(item)

        for item in current_items.values():
            self.list_widget.addItem(item)
