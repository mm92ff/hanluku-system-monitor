# detachable/detachable_manager.py
from __future__ import annotations
import logging
import uuid
from typing import TYPE_CHECKING, Dict, Set, Optional, List

from PySide6.QtCore import QObject, Slot, QRect, QPoint, Qt, QTimer, QSize, Signal
from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import QApplication

from detachable.detachable_widget import DetachableWidget
from detachable.magnetic_docking import MagneticDocker, DockingType
from detachable.position_persistence import load_layout, save_layout
from detachable.group_manager import GroupManager, GroupType, GroupInfo
from config.config import CONFIG_DIR
from config.constants import SettingsKey, LayoutSection

if TYPE_CHECKING:
    from core.main_window import SystemMonitor
    from core.monitor_manager import MonitorManager


class DetachableManager(QObject):
    """
    Verwaltet losgelöste Widgets, deren Layout, Gruppierung und
    Interaktion mit dem Monitor-Setup.
    """
    layout_modified = Signal()
    MIN_FONT_SIZE = 6

    def __init__(self, main_window: SystemMonitor, monitor_manager: Optional[MonitorManager] = None):
        super().__init__()
        self.main_win = main_window
        self.ui_manager = main_window.ui_manager
        self.monitor_manager = monitor_manager

        self.active_widgets: Dict[str, DetachableWidget] = {}
        
        gap = self.main_win.settings_manager.get_setting(SettingsKey.DOCKING_GAP.value, 1)
        self.docker = MagneticDocker(gap=gap)
        self.group_manager = GroupManager()
        self.drag_start_positions: Dict[str, QPoint] = {}
        self.layouts = load_layout(CONFIG_DIR)
        self.active_layout_name: Optional[str] = None
        
        self.save_timer = QTimer(self)
        self.save_timer.setSingleShot(True)
        self.save_timer.setInterval(500)
        self.save_timer.timeout.connect(self._save_layout_to_session)
        self.layout_modified.connect(self.save_timer.start)


        if self.monitor_manager:
            logging.info("MonitorManager übergeben - Multimonitor-Unterstützung aktiv.")
        else:
            logging.warning("Kein MonitorManager - Multimonitor-Unterstützung eingeschränkt.")

    @Slot(str, dict)
    def update_widget_display(self, metric_key: str, data: dict):
        """
        Slot, der vom DataHandler-Signal aufgerufen wird.
        Aktualisiert das entsprechende Widget mit den aufbereiteten Daten.
        """
        if widget := self.active_widgets.get(metric_key):
            widget.update_data(data["value_text"], data["percent_value"])
            widget.set_value_style(
                data["is_alarm"], data["normal_color"], data["alarm_color"]
            )

    def are_all_widgets_in_single_stack(self) -> bool:
        """
        Prüft ob alle aktiven Widgets zu einer einzigen Stack-Gruppe gehören.
        """
        if not self.active_widgets:
            return False
        
        all_widget_keys = set(self.active_widgets.keys())
        
        group_ids = set()
        for widget_key in all_widget_keys:
            group_id = self.group_manager.get_group_id(widget_key)
            if not group_id:
                return False
            group_ids.add(group_id)
        
        if len(group_ids) != 1:
            return False
        
        group_id = next(iter(group_ids))
        group_info = self.group_manager.groups.get(group_id)
        if not group_info or group_info.group_type != GroupType.STACK:
            return False
        
        return group_info.members == all_widget_keys

    def start_detached_mode(self):
        """Startet den Detached-Modus mit dem letzten oder einem neuen Layout."""
        self.active_layout_name = "_last_session" if "_last_session" in self.layouts else None
        self.load_layout(self.active_layout_name)

    def update_monitor_configuration(self):
        """Aktualisiert Monitor-Infos und repariert ungültige Widget-Positionen."""
        if self.monitor_manager and self.monitor_manager.update_monitor_info():
            logging.info("Monitor-Konfiguration geändert - validiere Widget-Positionen")
            self._repair_invalid_widget_positions()

    def _repair_invalid_widget_positions(self):
        """Repariert Positionen, die außerhalb sichtbarer Monitore liegen."""
        if not self.monitor_manager:
            return

        positions = {key: w.pos() for key, w in self.active_widgets.items()}
        sizes = {key: w.size() for key, w in self.active_widgets.items()}
        corrected = self.monitor_manager.repair_invalid_positions(positions, sizes)
        
        for key, new_pos in corrected.items():
            if key in self.active_widgets and new_pos != positions[key]:
                self.active_widgets[key].move(new_pos)
                logging.info(f"Widget '{key}' Position korrigiert: {positions[key]} -> {new_pos}")
        
        if corrected:
            QTimer.singleShot(0, self._check_and_resolve_overlaps)

    def get_safe_position_for_new_widget(self, widget_size: QSize = QSize(200, 50)) -> QPoint:
        """Berechnet eine sichere, zentrierte Position für ein neues Widget."""
        if self.monitor_manager:
            return self.monitor_manager.get_safe_position_for_new_window(widget_size)
        
        if screen := QApplication.primaryScreen():
            rect = screen.availableGeometry()
            return QPoint(rect.center().x() - widget_size.width() // 2, rect.top() + 100)
        return QPoint(100, 100)

    def get_cascade_position(self, widget_index: int, widget_size: QSize = QSize(200, 50)) -> QPoint:
        """Berechnet Kaskaden-Position für gestapelte Widgets."""
        if self.monitor_manager:
            return self.monitor_manager.get_cascade_position(widget_index, widget_size)
        
        offset = 30
        base_pos = self.get_safe_position_for_new_widget(widget_size)
        return QPoint(base_pos.x() + widget_index * offset, base_pos.y() + widget_index * offset)

    def validate_widget_position(self, position: QPoint, widget_size: QSize) -> QPoint:
        """Validiert und korrigiert eine Widget-Position."""
        if self.monitor_manager:
            result = self.monitor_manager.validate_position(position, widget_size)
            return result.corrected_position if not result.is_valid and result.corrected_position else position

        if screen := QApplication.primaryScreen():
            s_rect = screen.availableGeometry()
            x = max(s_rect.x(), min(position.x(), s_rect.right() - widget_size.width()))
            y = max(s_rect.y(), min(position.y(), s_rect.bottom() - widget_size.height()))
            return QPoint(x, y)
        return position

    def update_all_widget_labels(self):
        """Aktualisiert die Label-Texte und passt die Widget-Größe an."""
        for key, widget in self.active_widgets.items():
            if item := self.ui_manager.metric_widgets.get(key):
                widget.update_label(item['full_text'])
        
        QTimer.singleShot(0, self._synchronize_group_layout)

    def update_all_window_flags(self):
        """Aktualisiert die Window-Flags aller aktiven Widgets."""
        on_top = self.main_win.settings_manager.get_setting(SettingsKey.ALWAYS_ON_TOP.value, True)
        for widget in self.active_widgets.values():
            flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Tool
            if on_top:
                flags |= Qt.WindowType.WindowStaysOnTopHint
            widget.setWindowFlags(flags)
            widget.show()
        logging.debug(f"Window-Flags aktualisiert (Always on Top: {on_top})")

    def get_available_layout_names(self) -> List[str]:
        """Gibt eine sortierte Liste aller verfügbaren Layout-Namen zurück."""
        return sorted(list(self.layouts.keys()))
    
    @Slot()
    def _save_layout_to_session(self):
        """Slot, der vom save_timer aufgerufen wird, um die Session zu speichern."""
        self.save_layout_as("_last_session")

    def save_layout_as(self, name: str):
        """
        Speichert das aktuelle Layout unter einem bestimmten Namen.
        """
        if not name:
            return
        
        widget_data = {}
        for key, widget in self.active_widgets.items():
            pos = widget.pos()
            group_type = self.group_manager.get_group_type(key)
            entry = {
                "pos": [pos.x(), pos.y()],
                "width": widget.width(),
                "group_id": self.group_manager.get_group_id(key),
                "group_type": group_type.value if group_type else None
            }
            if self.monitor_manager and (monitor_name := self.monitor_manager.get_monitor_at_position(pos)):
                entry["monitor"] = monitor_name
            widget_data[key] = entry

        layout_data = {
            LayoutSection.WIDGETS.value: widget_data,
            **self.main_win.settings_manager.get_complete_layout_settings()
        }
        
        self.layouts[name] = layout_data
        save_layout(self.layouts, CONFIG_DIR)
        self.active_layout_name = name
        logging.info(f"Layout '{name}' mit {len(widget_data)} Widgets gespeichert.")

    def load_layout(self, name: Optional[str]):
        """
        Lädt ein benanntes Layout mit korrekter Initialisierungs-Reihenfolge.
        """
        self._deactivate_view()

        # GEÄNDERT: CPU- und GPU-Auswahl VOR dem Laden der Widgets treffen
        if hasattr(self.main_win, 'hw_manager'):
            cpu_id = self.main_win.settings_manager.get_setting(SettingsKey.SELECTED_CPU_IDENTIFIER.value, "auto")
            self.main_win.hw_manager.update_selected_cpu_sensors(cpu_id)

            gpu_id = self.main_win.settings_manager.get_setting(SettingsKey.SELECTED_GPU_IDENTIFIER.value, "auto")
            self.main_win.hw_manager.update_selected_gpu_sensors(gpu_id)
        
        if not name or name not in self.layouts:
            logging.warning(f"Layout '{name}' nicht gefunden, starte mit Standard-Layout.")
            self.main_win.ui_manager.refresh_metric_definitions()
            self._activate_view_with_data({})
            return

        layout_data = self.layouts[name]
        
        if LayoutSection.WIDGETS.value in layout_data:
            self._load_complete_settings_from_layout(layout_data)
            widget_data = layout_data[LayoutSection.WIDGETS.value]
        else:
            widget_data = layout_data
            logging.info(f"Layout '{name}' im alten Format - nur Positionen werden geladen.")
        
        self.main_win.ui_manager.refresh_metric_definitions()
        
        self.active_layout_name = name
        self._activate_view_with_data(widget_data)

        QTimer.singleShot(0, self._post_layout_load_updates)

    def _load_complete_settings_from_layout(self, layout_data: Dict):
        """Wendet alle Einstellungen aus den Layout-Daten an."""
        settings_manager = self.main_win.settings_manager
        settings_to_apply = {}
        
        for section in LayoutSection:
            if category_settings := layout_data.get(section.value):
                settings_to_apply.update(category_settings)
        
        if settings_to_apply:
            settings_manager.update_settings(settings_to_apply, save_immediately=True)
        
        logging.info(f"Einstellungen aus Layout angewendet: {len(settings_to_apply)} Werte aktualisiert.")

    def _post_layout_load_updates(self):
        """Führt UI-Updates durch, die nach der Widget-Erstellung stattfinden können."""
        try:
            self.main_win.tray_icon_manager.rebuild_menu()
            self.main_win.ui_manager.apply_styles()
            self.main_win.tray_icon_manager.update_tray_icon()
            self.main_win.restart_worker_thread()
            self.update_all_window_flags()
        except Exception as e:
            logging.error(f"Fehler bei Post-Layout-Load-Updates: {e}", exc_info=True)

    def _activate_view_with_data(self, widget_data: Dict):
        """Aktiviert die Detached View mit spezifischen Widget-Daten."""
        metric_order = self.main_win.settings_manager.get_setting(SettingsKey.METRIC_ORDER.value, [])
        is_first_run = not widget_data

        if is_first_run:
            visible_metrics = [k for k in metric_order if self.main_win.settings_manager.get_setting(f"show_{k}", True)]
        else:
            visible_metrics = sorted(widget_data.keys(), key=lambda k: metric_order.index(k) if k in metric_order else 999)

        for i, key in enumerate(visible_metrics):
            if not self.main_win.settings_manager.get_setting(f"show_{key}", True):
                continue
            
            pos_data = widget_data.get(key, {}).get("pos")
            initial_pos = QPoint(*pos_data) if pos_data else self.get_cascade_position(i)
            self.detach_metric(key, initial_pos)
            
            if widget := self.active_widgets.get(key):
                width = widget_data.get(key, {}).get("width")
                if width:
                    widget.setFixedWidth(width)

        if is_first_run and self.active_widgets:
            self._create_initial_vertical_stack()
            self.layout_modified.emit()
        else:
            self._restore_groups(widget_data)
            QTimer.singleShot(0, self._synchronize_group_layout)
        
        if self.monitor_manager:
            QTimer.singleShot(0, self._repair_invalid_widget_positions)
        logging.info(f"View aktiviert mit {len(self.active_widgets)} Widgets")

    def _create_initial_vertical_stack(self):
        """
        Ordnet alle aktiven Widgets in einem vertikalen Stapel an und erstellt eine Gruppe.
        """
        if not self.active_widgets: return

        QApplication.processEvents()
        metric_order = self.main_win.settings_manager.get_setting(SettingsKey.METRIC_ORDER.value, [])
        widgets = sorted(self.active_widgets.values(), key=lambda w: metric_order.index(w.metric_key) if w.metric_key in metric_order else 999)
        if not widgets: return

        for widget in widgets:
            widget.setFixedWidth(250)
        QApplication.processEvents()

        gap = self.docker.gap
        total_height = sum(w.height() for w in widgets) + max(0, len(widgets) - 1) * gap
        
        safe_pos = self.get_safe_position_for_new_widget(QSize(widgets[0].width(), total_height))
        
        current_y = safe_pos.y()
        for widget in widgets:
            widget.move(safe_pos.x(), current_y)
            current_y += widget.height() + gap
            
        if len(widgets) > 1:
            self.group_manager.create_stack_group([w.metric_key for w in widgets])

    def reset_to_default_stack(self):
        """Setzt alle Widgets auf die Standard-Stapel-Anordnung zurück."""
        self.group_manager.groups.clear()
        self.group_manager.widget_to_group.clear()
        for widget in self.active_widgets.values():
            widget.remove_group_border()
        
        self._create_initial_vertical_stack()
        self._synchronize_group_layout()
        
        self.active_layout_name = None
        self.layout_modified.emit()
        logging.info("Widgets auf Standard-Stack zurückgesetzt")

    def _restore_groups(self, layout_data: Dict):
        """Stellt Gruppen aus Layout-Daten wieder her."""
        self.group_manager.groups.clear()
        self.group_manager.widget_to_group.clear()
        
        temp_groups: Dict[str, Dict] = {}
        for key, state in layout_data.items():
            if (group_id := state.get("group_id")) and (group_type_val := state.get("group_type")):
                try:
                    group_type = GroupType(group_type_val)
                    if group_id not in temp_groups:
                        temp_groups[group_id] = {"type": group_type, "members": set()}
                    temp_groups[group_id]["members"].add(key)
                except ValueError:
                    logging.warning(f"Ungültiger Gruppentyp '{group_type_val}' im Layout gefunden.")

        for group_id, data in temp_groups.items():
            group_info = GroupInfo(group_id, data["type"])
            group_info.members = data["members"]
            self.group_manager.groups[group_id] = group_info
            for member in data["members"]:
                self.group_manager.widget_to_group[member] = group_id

    def _deactivate_view(self):
        """Deaktiviert alle aktiven Widgets."""
        for key in list(self.active_widgets.keys()):
            self.attach_metric(key)

    def detach_metric(self, metric_key: str, initial_pos: Optional[QPoint] = None):
        """Löst eine Metrik als eigenes Widget los."""
        if metric_key in self.active_widgets or not (widget_info := self.ui_manager.metric_widgets.get(metric_key)):
            logging.warning(f"detach_metric für '{metric_key}' fehlgeschlagen: Widget nicht im UIManager bekannt.")
            return
        
        pos = self.validate_widget_position(initial_pos, QSize(200, 50)) if initial_pos else self.get_safe_position_for_new_widget()
        
        widget = DetachableWidget(metric_key, {'label_text': widget_info['full_text'], 'has_bar': widget_info["has_bar"]}, self)
        
        widget.wants_to_group.connect(self.handle_group_request)
        widget.wants_to_ungroup.connect(self.handle_ungroup_request)
        widget.wants_to_hide.connect(self._handle_widget_hide_request)
        widget.wants_to_set_width.connect(self.main_win.action_handler.show_set_width_dialog)
        widget.drag_started.connect(self.on_drag_started)
        widget.drag_in_progress.connect(self.on_drag_in_progress)
        widget.drag_finished.connect(self.on_drag_finished)
        
        widget.move(pos)
        self.apply_styles_to_widget(widget)
        widget.show()
        self.active_widgets[metric_key] = widget

    @Slot(str)
    def _handle_widget_hide_request(self, metric_key: str):
        """Behandelt das Ausblenden eines Widgets über das Kontextmenü."""
        self.main_win.action_handler.toggle_metric_visibility(metric_key, False)
        logging.debug(f"Widget '{metric_key}' über Kontextmenü ausgeblendet")

    def attach_metric(self, metric_key: str):
        """Löst ein Widget wieder an und schließt es."""
        self.handle_ungroup_request(metric_key)
        if widget := self.active_widgets.pop(metric_key, None):
            widget.close()
            widget.deleteLater()

    def apply_styles_to_widget(self, widget: DetachableWidget):
        """Wendet alle aktuellen Stil-Einstellungen auf ein Widget an."""
        settings = self.main_win.settings_manager
        font = QFont(settings.get_setting(SettingsKey.FONT_FAMILY.value), max(self.MIN_FONT_SIZE, settings.get_setting(SettingsKey.FONT_SIZE.value)))
        font.setBold(settings.get_setting(SettingsKey.FONT_WEIGHT.value) == "bold")
        
        font_metrics = QFontMetrics(font)
        font_height = font_metrics.height()

        bar_mult = settings.get_setting(SettingsKey.BAR_GRAPH_WIDTH_MULTIPLIER.value, 9)
        bar_width = max(30, font.pointSize() * bar_mult)
        show_bars = settings.get_setting(SettingsKey.SHOW_BAR_GRAPHS.value, True) and widget.bar is not None
        
        bar_height_factor = settings.get_setting(SettingsKey.BAR_GRAPH_HEIGHT_FACTOR.value, 0.65)

        padding_mode = settings.get_setting(SettingsKey.WIDGET_PADDING_MODE.value, "factor")
        if padding_mode == "factor":
            factor = settings.get_setting(SettingsKey.WIDGET_PADDING_FACTOR.value, 0.25)
            p_vert = int(font.pointSize() * factor)
            p_horiz = int(p_vert * 2.5)
            top_pad, bottom_pad = p_vert, p_vert
            widget.update_padding(p_horiz, p_vert, p_horiz, p_vert)
        else: # "pixels"
            top_pad = settings.get_setting(SettingsKey.WIDGET_PADDING_TOP.value, 2)
            bottom_pad = settings.get_setting(SettingsKey.WIDGET_PADDING_BOTTOM.value, 2)
            left_pad = settings.get_setting(SettingsKey.WIDGET_PADDING_LEFT.value, 5)
            right_pad = settings.get_setting(SettingsKey.WIDGET_PADDING_RIGHT.value, 5)
            widget.update_padding(left_pad, top_pad, right_pad, bottom_pad)

        widget.update_style(font, bar_width, show_bars, bar_height_factor, widget.metric_key)
        
        widget.background.set_background_color(settings.get_setting(SettingsKey.BACKGROUND_COLOR.value))
        widget.background.set_background_alpha(settings.get_setting(SettingsKey.BACKGROUND_ALPHA.value, 200))
        
        total_height = font_height + top_pad + bottom_pad
        widget.setFixedHeight(total_height)

        if widget.minimumWidth() != widget.maximumWidth():
            original_text = widget.value.text()
            placeholder_applied = False
            if widget.metric_key == 'net':
                widget.value.setText("▲999.9 ▼999.9 MBit/s")
                placeholder_applied = True
            elif widget.metric_key == 'disk_io':
                widget.value.setText("R:999.9 W:999.9 MB/s")
                placeholder_applied = True
            
            if placeholder_applied:
                widget.adjustSize()
                widget.value.setText(original_text)

    def apply_styles_to_all_active_widgets(self):
        """Wendet Stile auf alle aktiven Widgets an."""
        for widget in self.active_widgets.values():
            self.apply_styles_to_widget(widget)
        
        QTimer.singleShot(0, self._synchronize_group_layout)
        self.layout_modified.emit()

    def set_widget_width(self, metric_key: str, width: int):
        """Setzt die feste Breite für ein Widget und synchronisiert die Gruppe."""
        target_widget = self.active_widgets.get(metric_key)
        if not target_widget:
            return

        group_type = self.group_manager.get_group_type(metric_key)
        
        if group_type == GroupType.STACK:
            group_id = self.group_manager.get_group_id(metric_key)
            if group_id:
                group_members = self.group_manager.get_group_members(group_id)
                for member_key in group_members:
                    if widget := self.active_widgets.get(member_key):
                        widget.setFixedWidth(width)
                logging.info(f"Breite für Stack-Gruppe mit '{metric_key}' auf {width}px gesetzt (alle {len(group_members)} Widgets)")
        else:
            target_widget.setFixedWidth(width)
            logging.info(f"Breite für '{metric_key}' individuell auf {width}px gesetzt")

        QTimer.singleShot(0, self._synchronize_group_layout)
        self.layout_modified.emit()

    def _check_and_resolve_overlaps(self):
        """Prüft auf Überlappungen und gruppiert Widgets bei Bedarf."""
        widgets = list(self.active_widgets.items())
        processed = set()
        for i, (k1, w1) in enumerate(widgets):
            if k1 in processed: continue
            cluster = {k1}
            for j, (k2, w2) in enumerate(widgets[i+1:], i+1):
                if k2 in processed: continue
                if w1.geometry().intersects(w2.geometry()):
                    group1_id = self.group_manager.get_group_id(k1)
                    group2_id = self.group_manager.get_group_id(k2)
                    if group1_id and group1_id == group2_id:
                        continue
                    
                    cluster.add(k2)
            if len(cluster) > 1:
                self._stack_widgets_vertically(list(cluster))
                processed.update(cluster)

    def _stack_widgets_vertically(self, keys: List[str]):
        """Stapelt eine Liste von Widgets vertikal."""
        widgets = [self.active_widgets[k] for k in keys if k in self.active_widgets]
        if not widgets: return
        
        widgets.sort(key=lambda w: w.y())
        anchor = widgets[0]
        y = anchor.y()
        for w in widgets:
            w.move(anchor.x(), y)
            y += w.height() + self.docker.gap
        
        if len(keys) > 1:
            self.group_manager.create_stack_group(keys)
            self._synchronize_group_layout()

    def sync_widgets_with_definitions(self):
        """Entfernt Widgets, deren Metriken nicht mehr verfügbar sind."""
        missing = [k for k in self.active_widgets if k not in self.ui_manager.metric_widgets]
        for key in missing:
            self.attach_metric(key)
        self.update_all_widget_labels()

    @Slot(str)
    def handle_ungroup_request(self, widget_key: str):
        if self.group_manager.is_in_group(widget_key):
            self.group_manager.remove_from_group(widget_key)
            if widget := self.active_widgets.get(widget_key):
                widget.remove_group_border()
                widget.setMinimumWidth(0)
                widget.setMaximumWidth(16777215)
                widget.setMinimumHeight(0)
                widget.setMaximumHeight(16777215)
                self.apply_styles_to_widget(widget)
            self._synchronize_group_layout()

    @Slot(str, str)
    def handle_group_request(self, source_key: str, target_key: str):
        self.group_manager.add_to_group(source_key, target_key, GroupType.NORMAL)
        self._synchronize_group_layout()

    def _synchronize_group_layout(self):
        for group_info in list(self.group_manager.groups.values()):
            if group_info.group_type == GroupType.STACK:
                self._synchronize_stack_group(group_info.members)
            else:
                self._synchronize_normal_group(group_info.members)
        self._update_group_visual_indicators()
        self.layout_modified.emit()

    def _synchronize_stack_group(self, members: Set[str]):
        """Positioniert die Widgets in einem vertikalen Stapel neu und synchronisiert Breiten."""
        widgets = [self.active_widgets[m] for m in members if m in self.active_widgets]
        if not widgets: return
        
        QApplication.processEvents()

        max_width = max(w.width() for w in widgets)
        for widget in widgets:
            widget.setFixedWidth(max_width)

        is_vertical = self._is_vertical_arrangement(widgets)
        widgets.sort(key=lambda w: w.y() if is_vertical else w.x())
        anchor = widgets[0]

        if is_vertical:
            y = anchor.y()
            for i, w in enumerate(widgets):
                w.move(anchor.x(), y)
                y += w.height() + self.docker.gap
        else:
            x = anchor.x()
            for i, w in enumerate(widgets):
                w.move(x, anchor.y())
                x += w.width() + self.docker.gap

    def _synchronize_normal_group(self, members: Set[str]):
        widgets = [self.active_widgets.get(m) for m in members if m in self.active_widgets]
        if not widgets: return

        QApplication.processEvents()
        
        widgets.sort(key=lambda w: w.x())
        anchor = widgets[0]
        x = anchor.x()
        for i, w in enumerate(widgets):
            if i > 0:
                x += widgets[i-1].width() + self.docker.gap
            w.move(x, anchor.y())

    def _is_vertical_arrangement(self, widgets: List[DetachableWidget]) -> bool:
        if len(widgets) < 2: return True
        x_coords = [w.x() for w in widgets]
        y_coords = [w.y() for w in widgets]
        return (max(y_coords) - min(y_coords)) > (max(x_coords) - min(x_coords))

    def _update_group_visual_indicators(self):
        for widget in self.active_widgets.values():
            widget.remove_group_border()

    @Slot(str, QPoint)
    def on_drag_started(self, moving_key: str, start_pos: QPoint):
        self.drag_start_positions.clear()
        members = self.group_manager.get_group_members(self.group_manager.get_group_id(moving_key)) or {moving_key}
        for key in members:
            if widget := self.active_widgets.get(key):
                self.drag_start_positions[key] = widget.pos()

    @Slot(str, QPoint)
    def on_drag_in_progress(self, moving_key: str, mover_potential_pos: QPoint):
        if not self.drag_start_positions: return
        mover = self.active_widgets[moving_key]
        statics = [w.geometry() for k, w in self.active_widgets.items() if k not in self.drag_start_positions]
        snapped = self.docker.calculate_snap_position(QRect(mover_potential_pos, mover.size()), statics)
        validated = self.validate_widget_position(snapped, mover.size())
        delta = validated - self.drag_start_positions[moving_key]
        for key, start_pos in self.drag_start_positions.items():
            if widget := self.active_widgets.get(key):
                widget.move(start_pos + delta)

    @Slot(str)
    def on_drag_finished(self, final_key: str):
        if not self.drag_start_positions: return
        mover = self.active_widgets[final_key]
        statics = [w.geometry() for k, w in self.active_widgets.items() if k not in self.drag_start_positions]
        result = self.docker.calculate_snap_with_type(mover.geometry(), statics)
        
        if result.docking_type != DockingType.NONE and result.target_rect:
            target_key = next((k for k, w in self.active_widgets.items() if w.geometry() == result.target_rect), None)
            if target_key:
                if result.docking_type == DockingType.VERTICAL:
                    self.group_manager.add_to_group(final_key, target_key, GroupType.STACK)
                else: # DockingType.HORIZONTAL
                    self.group_manager.add_to_group(final_key, target_key, GroupType.NORMAL)

                QTimer.singleShot(0, self._synchronize_group_layout)

        self.drag_start_positions.clear()
        self.layout_modified.emit()