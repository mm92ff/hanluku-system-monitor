# detachable/detachable_widget.py
from __future__ import annotations
import logging
from typing import TYPE_CHECKING, Optional

from PySide6.QtWidgets import (
    QWidget, QLabel, QHBoxLayout, QApplication, QMenu, QSpacerItem, QSizePolicy
)
from PySide6.QtCore import Qt, Signal, QMimeData, QPoint
from PySide6.QtGui import QFont, QColor, QDrag, QAction

from ui.bar_graph_widget import BarGraphWidget
from core.background_widget import BackgroundWidget
from config.constants import SettingsKey

if TYPE_CHECKING:
    from detachable.detachable_manager import DetachableManager


class DetachableWidget(QWidget):
    """
    Ein losgelöstes Widget für einzelne Hardware-Metriken, das Drag&Drop,
    Gruppierung und ein Kontextmenü unterstützt.
    """
    closing = Signal(str)
    wants_to_group = Signal(str, str)
    wants_to_ungroup = Signal(str)
    wants_to_hide = Signal(str)
    wants_to_set_width = Signal(str)
    drag_started = Signal(str, QPoint)
    drag_in_progress = Signal(str, QPoint)
    drag_finished = Signal(str)

    def __init__(self, metric_key: str, initial_data: dict, manager: DetachableManager):
        super().__init__()
        self.metric_key = metric_key
        self.manager = manager
        self.translator = manager.main_win.translator
        
        self._setup_window_properties()
        self._setup_ui(initial_data)
        self.update_data('...')

    def _setup_window_properties(self):
        """Konfiguriert die Fenstereigenschaften (rahmenlos, transparent etc.)."""
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAcceptDrops(True)
        self.drag_position: Optional[QPoint] = None
        self.is_dragging_for_grouping = False

    def _setup_ui(self, initial_data: dict):
        """Initialisiert die UI-Komponenten des Widgets."""
        self.background = BackgroundWidget(self)
        self.internal_layout = QHBoxLayout(self.background)
        
        outer_layout = QHBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(self.background)
        
        self.label = QLabel(initial_data.get('label_text', ''))
        self.internal_layout.addWidget(self.label)
        
        self.internal_layout.addStretch(1)
        
        self.bar = BarGraphWidget() if initial_data.get('has_bar', False) else None
        if self.bar:
            self.internal_layout.addWidget(self.bar)
        
        self.value = QLabel("...")
        self.value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.internal_layout.addWidget(self.value)

    def update_padding(self, left: int, top: int, right: int, bottom: int):
        """Aktualisiert die inneren Abstände des Widgets."""
        self.internal_layout.setContentsMargins(left, top, right, bottom)

    def update_label(self, new_text: str):
        self.label.setText(new_text)

    def update_data(self, value_text: str, percent_value: Optional[float] = None):
        self.value.setText(value_text)
        if self.bar:
            self.bar.setValue(percent_value)

    def update_style(self, font: QFont, bar_width: int, show_bar: bool, bar_height_factor: float, metric_key: str):
        """Wendet nur noch Stil-Eigenschaften an, keine Grössenänderungen."""
        safe_font = QFont(font)
        if safe_font.pointSize() < 6:
            safe_font.setPointSize(6)
        
        self.label.setFont(safe_font)
        self.value.setFont(safe_font)

        if self.bar:
            self.bar.updateFontHeight(safe_font, bar_height_factor)
            self.bar.setFixedWidth(max(30, bar_width))
            self.bar.setVisible(show_bar)

    def set_value_style(self, is_alarm: bool, normal_color: str, alarm_color: str):
        color = alarm_color if is_alarm else normal_color
        self.label.setStyleSheet(f"color: {normal_color}; background: transparent;")
        self.value.setStyleSheet(f"color: {color}; background: transparent;")
        if self.bar:
            self.bar.setColor(color)

    def set_group_border(self, color: QColor):
        self.background.set_border(color, 2)

    def remove_group_border(self):
        self.background.remove_border()

    def mousePressEvent(self, event):
        is_fixed = self.manager.main_win.settings_manager.get_setting(SettingsKey.POSITION_FIXED.value, False)
        if event.button() != Qt.MouseButton.LeftButton or is_fixed:
            return

        self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        
        if QApplication.keyboardModifiers() == Qt.KeyboardModifier.ShiftModifier:
            self.is_dragging_for_grouping = True
            drag = QDrag(self)
            mime_data = QMimeData()
            mime_data.setData("application/x-metric-widget", self.metric_key.encode())
            drag.setMimeData(mime_data)
            drag.exec()
            self.is_dragging_for_grouping = False
        else:
            self.drag_started.emit(self.metric_key, self.pos())
        event.accept()

    def mouseMoveEvent(self, event):
        is_fixed = self.manager.main_win.settings_manager.get_setting(SettingsKey.POSITION_FIXED.value, False)
        if (event.buttons() == Qt.MouseButton.LeftButton and self.drag_position and 
            not self.is_dragging_for_grouping and not is_fixed):
            
            self.drag_in_progress.emit(self.metric_key, event.globalPosition().toPoint() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        if self.drag_position and not self.is_dragging_for_grouping:
            self.drag_finished.emit(self.metric_key)
        self.drag_position = None

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        if self.manager.group_manager.is_in_group(self.metric_key):
            ungroup_action = QAction(self.translator.translate("widget_ctx_menu_leave_stack"), self)
            ungroup_action.triggered.connect(lambda: self.wants_to_ungroup.emit(self.metric_key))
            menu.addAction(ungroup_action)
        
        menu.addSeparator()

        set_width_action = QAction(self.translator.translate("widget_ctx_menu_set_width"), self)
        set_width_action.triggered.connect(lambda: self.wants_to_set_width.emit(self.metric_key))
        menu.addAction(set_width_action)
            
        hide_action = QAction(self.translator.translate("widget_ctx_menu_hide"), self)
        hide_action.triggered.connect(lambda: self.wants_to_hide.emit(self.metric_key))
        menu.addAction(hide_action)
        menu.exec(event.globalPos())

    def dragEnterEvent(self, event):
        mime_data = event.mimeData()
        source_key = mime_data.data("application/x-metric-widget").data().decode()
        if mime_data.hasFormat("application/x-metric-widget") and source_key != self.metric_key:
            event.acceptProposedAction()

    def dropEvent(self, event):
        source_key = event.mimeData().data("application/x-metric-widget").data().decode()
        self.wants_to_group.emit(source_key, self.metric_key)
        event.acceptProposedAction()