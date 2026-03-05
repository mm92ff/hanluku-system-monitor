# detachable/detachable_widget.py
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import QMimeData, QPoint, Qt, Signal
from PySide6.QtGui import QAction, QColor, QDrag, QFont, QPainter, QPen
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLabel, QMenu, QWidget

from config.constants import DisplayMode, SettingsKey
from core.background_widget import BackgroundWidget
from ui.bar_graph_widget import BarGraphWidget

if TYPE_CHECKING:
    from detachable.detachable_manager import DetachableManager


class WidthAdjustHandle(QWidget):
    """Kleiner Griff zum interaktiven Anpassen der Widget-Breite."""

    def __init__(self, owner: "DetachableWidget"):
        super().__init__(owner.background)
        self.owner = owner
        self.setFixedWidth(22)
        self.setCursor(Qt.CursorShape.SizeHorCursor)
        self.hide()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        handle_rect = self.rect().adjusted(1, 1, -1, -1)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 168, 252, 255))
        painter.drawRoundedRect(handle_rect, 5.0, 5.0)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.grabMouse()
            self.owner.begin_width_adjustment(event.globalPosition().toPoint())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        self.owner.update_width_adjustment(event.globalPosition().toPoint())
        event.accept()

    def mouseReleaseEvent(self, event):
        if self.mouseGrabber() is self:
            self.releaseMouse()
        self.owner.finish_width_adjustment(event.globalPosition().toPoint())
        event.accept()


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

    def __init__(self, metric_key: str, initial_data: dict, manager: "DetachableManager"):
        super().__init__()
        self.metric_key = metric_key
        self.manager = manager
        self.translator = manager.main_win.translator
        self.drag_position: Optional[QPoint] = None
        self.is_dragging_for_grouping = False
        self._width_adjust_mode = False
        self._is_adjusting_width = False
        self._resize_start_pos: Optional[QPoint] = None
        self._resize_start_width = 0

        self._setup_window_properties()
        self._setup_ui(initial_data)
        self.update_data("...")

    def _setup_window_properties(self):
        """Konfiguriert die Fenstereigenschaften."""
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAcceptDrops(True)

    def _setup_ui(self, initial_data: dict):
        """Initialisiert die UI-Komponenten des Widgets."""
        self.background = BackgroundWidget(self)
        self.internal_layout = QHBoxLayout(self.background)

        outer_layout = QHBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(self.background)

        self.label = QLabel(initial_data.get("label_text", ""))
        self.internal_layout.addWidget(self.label)
        self.internal_layout.addStretch(1)

        self.bar = BarGraphWidget() if initial_data.get("has_bar", False) else None
        if self.bar:
            self.internal_layout.addWidget(self.bar)

        self.value = QLabel("...")
        self.value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.internal_layout.addWidget(self.value)

        self.width_adjust_handle = WidthAdjustHandle(self)
        self._update_width_handle_geometry()

    def update_padding(self, left: int, top: int, right: int, bottom: int):
        """Aktualisiert die inneren Abstände des Widgets."""
        self.internal_layout.setContentsMargins(left, top, right, bottom)

    def update_label(self, new_text: str):
        self.label.setText(new_text)

    def update_data(self, value_text: str, percent_value: Optional[float] = None):
        self.value.setText(value_text)
        if self.bar:
            self.bar.setValue(percent_value)

    def get_content_minimum_width(self) -> int:
        label_text = self.label.text() or ""
        value_text = self.value.text() or ""
        reference_value_text = self._get_value_width_reference_text(value_text)

        label_width = self.label.fontMetrics().horizontalAdvance(label_text)
        value_width = self.value.fontMetrics().horizontalAdvance(reference_value_text)

        margins = self.internal_layout.contentsMargins()
        spacing = max(0, self.internal_layout.spacing())
        item_count = self.internal_layout.count()

        bar_width = 0
        if self.bar and self.bar.isVisible():
            bar_width = self.bar.width()

        manual_min = (
            margins.left()
            + margins.right()
            + label_width
            + value_width
            + bar_width
            + max(0, item_count - 1) * spacing
        )
        layout_min = self.internal_layout.minimumSize().width()
        background_min = self.background.minimumSizeHint().width()
        return max(1, int(max(manual_min, layout_min, background_min)))

    def _get_value_width_reference_text(self, current_value_text: str) -> str:
        fallback = current_value_text or "..."
        settings_manager = getattr(
            getattr(self.manager, "main_win", None), "settings_manager", None
        )

        candidate = None
        if self.metric_key == "net":
            unit = "MBit/s"
            mode = DisplayMode.BOTH.value
            if settings_manager is not None:
                unit = str(
                    settings_manager.get_setting(
                        SettingsKey.NETWORK_UNIT.value,
                        unit,
                    )
                )
                mode = str(
                    settings_manager.get_setting(
                        SettingsKey.NETWORK_DISPLAY_MODE.value,
                        mode,
                    )
                ).lower()
            if mode == DisplayMode.UP.value:
                candidate = f"\u25B2999.9 {unit}"
            elif mode == DisplayMode.DOWN.value:
                candidate = f"\u25BC999.9 {unit}"
            else:
                candidate = f"\u25B2999.9 \u25BC999.9 {unit}"
        elif self.metric_key == "disk_io":
            unit = "MB/s"
            mode = DisplayMode.BOTH.value
            if settings_manager is not None:
                unit = str(
                    settings_manager.get_setting(
                        SettingsKey.DISK_IO_UNIT.value,
                        unit,
                    )
                )
                mode = str(
                    settings_manager.get_setting(
                        SettingsKey.DISK_IO_DISPLAY_MODE.value,
                        mode,
                    )
                ).lower()
            if mode == DisplayMode.READ.value:
                candidate = f"R:999.9 {unit}"
            elif mode == DisplayMode.WRITE.value:
                candidate = f"W:999.9 {unit}"
            else:
                candidate = f"R:999.9 W:999.9 {unit}"

        if not candidate:
            return fallback

        current_width = self.value.fontMetrics().horizontalAdvance(fallback)
        candidate_width = self.value.fontMetrics().horizontalAdvance(candidate)
        return candidate if candidate_width > current_width else fallback

    def update_style(
        self,
        font: QFont,
        bar_width: int,
        show_bar: bool,
        bar_height_factor: float,
        metric_key: str,
    ):
        """Wendet Stil-Eigenschaften an, aber keine Breitenlogik."""
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

    def _update_width_handle_geometry(self):
        handle_height = max(12, self.background.height() - 6)
        self.width_adjust_handle.setGeometry(
            max(0, self.background.width() - self.width_adjust_handle.width() - 2),
            3,
            self.width_adjust_handle.width(),
            handle_height,
        )
        self.width_adjust_handle.raise_()

    def show_width_adjust_handle(self):
        self._width_adjust_mode = True
        self._update_width_handle_geometry()
        self.width_adjust_handle.show()
        self.width_adjust_handle.raise_()

    def hide_width_adjust_handle(self):
        self._width_adjust_mode = False
        self._is_adjusting_width = False
        self._resize_start_pos = None
        self.width_adjust_handle.hide()

    def begin_width_adjustment(self, global_pos: QPoint):
        self._width_adjust_mode = True
        self._is_adjusting_width = True
        self._resize_start_pos = global_pos
        self._resize_start_width = self.width()

    def update_width_adjustment(self, global_pos: QPoint):
        if not self._is_adjusting_width or self._resize_start_pos is None:
            return
        requested_width = self._resize_start_width + (global_pos.x() - self._resize_start_pos.x())
        self.manager.preview_widget_width(self.metric_key, requested_width)
        self._update_width_handle_geometry()

    def finish_width_adjustment(self, global_pos: QPoint):
        if not self._is_adjusting_width or self._resize_start_pos is None:
            self.hide_width_adjust_handle()
            return
        requested_width = self._resize_start_width + (global_pos.x() - self._resize_start_pos.x())
        self.manager.set_widget_width(self.metric_key, requested_width)
        self.hide_width_adjust_handle()

    def mousePressEvent(self, event):
        is_fixed = self.manager.main_win.settings_manager.get_setting(
            SettingsKey.POSITION_FIXED.value, False
        )
        if event.button() != Qt.MouseButton.LeftButton or is_fixed:
            return

        if self._width_adjust_mode and not self._is_adjusting_width:
            self.hide_width_adjust_handle()

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
        is_fixed = self.manager.main_win.settings_manager.get_setting(
            SettingsKey.POSITION_FIXED.value, False
        )
        if (
            event.buttons() == Qt.MouseButton.LeftButton
            and self.drag_position
            and not self.is_dragging_for_grouping
            and not is_fixed
        ):
            self.drag_in_progress.emit(
                self.metric_key, event.globalPosition().toPoint() - self.drag_position
            )
            event.accept()

    def mouseReleaseEvent(self, event):
        if self.drag_position and not self.is_dragging_for_grouping:
            self.drag_finished.emit(self.metric_key)
        self.drag_position = None

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        if self.manager.group_manager.is_in_group(self.metric_key):
            ungroup_action = QAction(
                self.translator.translate("widget_ctx_menu_leave_stack"), self
            )
            ungroup_action.triggered.connect(
                lambda: self.wants_to_ungroup.emit(self.metric_key)
            )
            menu.addAction(ungroup_action)

        menu.addSeparator()

        set_width_action = QAction(
            self.translator.translate("widget_ctx_menu_set_width"), self
        )
        set_width_action.triggered.connect(
            lambda: self.wants_to_set_width.emit(self.metric_key)
        )
        menu.addAction(set_width_action)

        show_set_stack_width = getattr(
            getattr(self.manager.main_win, "action_handler", None),
            "show_set_stack_width_dialog",
            None,
        )
        is_horizontal_stack_group = getattr(
            self.manager,
            "is_horizontal_stack_group",
            None,
        )
        if callable(is_horizontal_stack_group):
            show_stack_width_action = bool(
                is_horizontal_stack_group(self.metric_key)
            )
        else:
            show_stack_width_action = self.manager.group_manager.is_stack_group(
                self.metric_key
            )
        if show_stack_width_action and callable(show_set_stack_width):
            set_stack_width_action = QAction(
                self.translator.translate("widget_ctx_menu_set_stack_width"), self
            )
            set_stack_width_action.triggered.connect(
                lambda: show_set_stack_width(self.metric_key)
            )
            menu.addAction(set_stack_width_action)

        show_widget_settings = getattr(
            getattr(self.manager.main_win, "action_handler", None),
            "show_widget_settings_window",
            None,
        )
        if callable(show_widget_settings):
            appearance_action = QAction(
                self.translator.translate("menu_config_widget_appearance"), self
            )
            appearance_action.triggered.connect(show_widget_settings)
            menu.addAction(appearance_action)

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

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._update_width_handle_geometry()
