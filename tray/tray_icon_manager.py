# tray/tray_icon_manager.py
import math
from typing import TYPE_CHECKING
from PySide6.QtWidgets import QSystemTrayIcon
from PySide6.QtGui import (QPixmap, QColor, QPainter, QBrush, QPen, QPolygonF,
                           QPainterPath, QIcon, QFont)
from PySide6.QtCore import Qt, QTimer, QRectF, QPointF
from tray.tray_menu_builder import TrayMenuBuilder
from config.constants import TrayShape, SettingsKey

if TYPE_CHECKING:
    from core.main_window import SystemMonitor

class TrayIconManager:
    """Manages the system tray icon, its appearance, and context menu."""

    def __init__(self, main_window: "SystemMonitor"):
        self.main_win = main_window
        self.settings_manager = main_window.settings_manager
        self.translator = main_window.translator
        self.is_alarm_active = False
        self.blink_state_is_on = False

        self._text_font = QFont()
        self._cached_font_size = 0
        self._update_font_cache()

        # Blink-Timer VOR update_tray_icon() initialisieren
        self.blink_timer = QTimer()
        self.blink_timer.timeout.connect(self._toggle_blink_on)

        self.tray_icon = QSystemTrayIcon(self.main_win)
        self.tray_icon.setToolTip(self.translator.translate("tray_tooltip"))
        self.rebuild_menu()
        self.update_tray_icon()
        self.tray_icon.show()

        if self.main_win.hw_manager.lhm_error:
            error_title = self.translator.translate("lhm_error_title")
            self.tray_icon.showMessage(
                error_title, self.main_win.hw_manager.lhm_error,
                QSystemTrayIcon.MessageIcon.Critical, 15000
            )

    def rebuild_menu(self):
        """Rebuilds the context menu, essential after language changes."""
        builder = TrayMenuBuilder(self.main_win)
        self.tray_icon.setContextMenu(builder.build())

    def update_alarm_state(self, is_active: bool):
        """Updates the alarm status and controls the blinking."""
        if self.is_alarm_active == is_active:
            return
        self.is_alarm_active = is_active
        self._handle_alarm_state()
        self.update_tray_icon()

    def update_tray_icon(self):
        """Draws the tray icon based on current settings with correct alarm logic."""
        # Stelle sicher, dass der Blink-Status aktuell ist
        self._handle_alarm_state()
        
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # KORRIGIERTE FARB-LOGIK - komplett neu gedacht
        fill_hex = self.settings_manager.get_setting(SettingsKey.TRAY_ICON_COLOR.value)  # Standard
        
        if self.is_alarm_active:
            blinking_enabled = self.settings_manager.get_setting(SettingsKey.TRAY_BLINKING_ENABLED.value, False)
            
            if blinking_enabled:
                # Blinken EIN: Verwende Alarmfarbe nur während Blink-Phase
                if self.blink_state_is_on:
                    fill_hex = self.settings_manager.get_setting(SettingsKey.TRAY_ICON_ALARM_COLOR.value)
                # Sonst: Standardfarbe (fill_hex bleibt unverändert)
            else:
                # Blinken AUS: Behalte Standardfarbe (fill_hex bleibt unverändert)
                pass

        fill_color = QColor(fill_hex)
        rect = pixmap.rect().adjusted(2, 2, -2, -2)
        shape_path = self._get_shape_path(self.settings_manager.get_setting(SettingsKey.TRAY_SHAPE.value), rect)
        painter.fillPath(shape_path, QBrush(fill_color))

        if self.settings_manager.get_setting(SettingsKey.TRAY_BORDER_ENABLED.value, True):
            pen = QPen(QColor(self.settings_manager.get_setting(SettingsKey.TRAY_BORDER_COLOR.value)))
            pen.setWidth(self.settings_manager.get_setting(SettingsKey.TRAY_BORDER_THICKNESS.value, 1))
            painter.setPen(pen)
            painter.drawPath(shape_path)

        if self.settings_manager.get_setting(SettingsKey.TRAY_SHOW_TEXT.value, False):
            text = self.settings_manager.get_setting(SettingsKey.TRAY_CUSTOM_TEXT.value, "")
            if text:
                self._update_font_cache()
                painter.setFont(self._text_font)
                pen = QPen(QColor(self.settings_manager.get_setting(SettingsKey.TRAY_TEXT_COLOR.value, "#FFFFFF")))
                painter.setPen(pen)
                painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, text)

        painter.end()
        self.tray_icon.setIcon(QIcon(pixmap))

    def _update_font_cache(self):
        """Creates or updates the cached QFont object only when settings change."""
        font_size = self.settings_manager.get_setting(SettingsKey.TRAY_TEXT_FONT_SIZE.value, 12)
        if font_size != self._cached_font_size:
            self._cached_font_size = font_size
            self._text_font = QFont("Arial", font_size, QFont.Weight.Bold)

    def _get_shape_path(self, shape_value: str, rect: QRectF) -> QPainterPath:
        """Returns a QPainterPath for the chosen shape."""
        path = QPainterPath()
        if shape_value == TrayShape.ROUND.value:
            path.addEllipse(rect)
        elif shape_value == TrayShape.SQUARE.value:
            path.addRect(rect)
        elif shape_value == TrayShape.TRIANGLE.value:
            poly = QPolygonF([
                QPointF(rect.center().x(), rect.top()),
                QPointF(rect.left(), rect.bottom()),
                QPointF(rect.right(), rect.bottom())
            ])
            path.addPolygon(poly)
            path.closeSubpath()
        elif shape_value == TrayShape.HEXAGON.value:
            hw, hh = rect.width() / 2, rect.height() / 2
            cx, cy = rect.center().x(), rect.center().y()
            poly = QPolygonF([
                QPointF(cx + hw, cy), QPointF(cx + hw / 2, cy - hh),
                QPointF(cx - hw / 2, cy - hh), QPointF(cx - hw, cy),
                QPointF(cx - hw / 2, cy + hh), QPointF(cx + hw / 2, cy + hh)
            ])
            path.addPolygon(poly)
            path.closeSubpath()
        elif shape_value == TrayShape.DIAMOND.value:
            poly = QPolygonF([
                QPointF(rect.center().x(), rect.top()),
                QPointF(rect.right(), rect.center().y()),
                QPointF(rect.center().x(), rect.bottom()),
                QPointF(rect.left(), rect.center().y())
            ])
            path.addPolygon(poly)
            path.closeSubpath()
        elif shape_value == TrayShape.STAR.value:
            hw, hh = rect.width() / 2, rect.height() / 2
            cx, cy = rect.center().x(), rect.center().y()
            outer_r, inner_r = min(hw, hh), min(hw, hh) * 0.4
            points = [
                QPointF(
                    cx + (outer_r if i % 2 == 0 else inner_r) * math.cos(math.radians(-90 + i * 36)),
                    cy + (outer_r if i % 2 == 0 else inner_r) * math.sin(math.radians(-90 + i * 36))
                ) for i in range(10)
            ]
            path.addPolygon(QPolygonF(points))
            path.closeSubpath()
        return path

    def _handle_alarm_state(self):
        """Controls the blink timer and ensures proper state management."""
        should_blink = self.is_alarm_active and self.settings_manager.get_setting(SettingsKey.TRAY_BLINKING_ENABLED.value, False)
        
        if should_blink and not self.blink_timer.isActive():
            # Starte Blinken
            interval_ms = int(self.settings_manager.get_setting(SettingsKey.TRAY_BLINK_RATE_SEC.value, 1.0) * 1000)
            self.blink_timer.setInterval(interval_ms)
            self.blink_timer.start()
            # Starte mit "aus"-Zustand, damit das erste Blinken sichtbar ist
            self.blink_state_is_on = False
            self._toggle_blink_on()
        elif not should_blink:
            # Stoppe Blinken komplett
            if self.blink_timer.isActive():
                self.blink_timer.stop()
            self.blink_state_is_on = False

    def _toggle_blink_on(self):
        """Schaltet den Blink-Zustand auf 'an' und plant das Ausschalten."""
        self.blink_state_is_on = True
        self.update_tray_icon()
        duration_ms = self.settings_manager.get_setting(SettingsKey.TRAY_BLINK_DURATION_MS.value, 500)
        QTimer.singleShot(duration_ms, self._toggle_blink_off)

    def _toggle_blink_off(self):
        """Schaltet den Blink-Zustand auf 'aus'."""
        # KORREKTUR: Verhindert, dass ein alter Timer den Zustand stört,
        # nachdem das Blinken bereits deaktiviert wurde.
        if not self.blink_timer.isActive():
            return

        self.blink_state_is_on = False
        self.update_tray_icon()