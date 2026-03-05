# ui/widgets/widget_settings_window.py
from __future__ import annotations
from typing import TYPE_CHECKING, Dict, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QSlider, QLabel, QHBoxLayout,
    QRadioButton, QDialogButtonBox, QDoubleSpinBox, QSpinBox,
    QCheckBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent

from config.constants import SettingsKey
from .base_window import SafeDialog, configure_dialog_layout, configure_dialog_window, style_dialog_button

if TYPE_CHECKING:
    from core.main_window import SystemMonitor


class WidgetSettingsWindow(SafeDialog):
    """
    Ein Einstellungsfenster zur visuellen Anpassung der DetachableWidgets
    mit direkter Live-Anwendung auf die aktiven Widgets.
    """

    def __init__(self, main_window: SystemMonitor):
        super().__init__(main_window)
        self.main_win = main_window
        self.settings_manager = main_window.settings_manager
        self.detachable_manager = main_window.detachable_manager
        self.translator = main_window.translator
        self._original_settings: Dict[str, object] = {}
        self._original_widths: Dict[str, int] = {}
        self._preview_width_override: Optional[int] = None
        self._suspend_auto_width_scaling = False
        self._last_font_size_for_auto_width = int(
            self.settings_manager.get_setting(SettingsKey.FONT_SIZE.value, 10)
        )
        self._closing_with_commit = False

        self.setWindowTitle(self.translator.translate("win_title_widget_settings"))
        configure_dialog_window(self, 560, 520, min_width=500, min_height=420)

        self._setup_ui()
        self._load_settings()
        self._original_settings = self._collect_dialog_settings()
        self._original_widths = self.detachable_manager.get_active_widget_widths()
        self._connect_signals()
        self._update_preview()

    def _setup_ui(self):
        """Erstellt die Benutzeroberfläche des Fensters."""
        layout = QVBoxLayout(self)
        configure_dialog_layout(layout)

        settings_group = QGroupBox(self.translator.translate("widget_settings_settings"))
        settings_layout = QVBoxLayout(settings_group)
        settings_layout.setSpacing(10)

        # -- Schrift & Balken --
        self.font_size_slider = self._create_slider(6, 24)
        settings_layout.addLayout(self._create_setting_row(
            self.translator.translate("widget_settings_font_size"), self.font_size_slider
        ))
        
        self.show_bar_checkbox = QCheckBox(self.translator.translate("widget_settings_show_bar_graph"))
        settings_layout.addWidget(self.show_bar_checkbox)

        self.bar_width_slider = self._create_slider(2, 20)
        settings_layout.addLayout(self._create_setting_row(
            self.translator.translate("widget_settings_bar_width"), self.bar_width_slider
        ))

        self.bar_height_spinbox = QDoubleSpinBox()
        self.bar_height_spinbox.setRange(0.1, 2.0)
        self.bar_height_spinbox.setSingleStep(0.05)
        self.bar_height_spinbox.setDecimals(2)
        settings_layout.addLayout(self._create_setting_row(
            self.translator.translate("widget_settings_bar_height"), self.bar_height_spinbox
        ))

        self.widget_width_slider = self._create_slider(50, 2000)
        settings_layout.addLayout(self._create_setting_row(
            self.translator.translate("widget_settings_widget_width"), self.widget_width_slider
        ))

        self.min_width_spinbox = QSpinBox()
        self.min_width_spinbox.setRange(10, 1000)
        settings_layout.addLayout(self._create_setting_row(
            self.translator.translate("widget_settings_min_width"), self.min_width_spinbox
        ))

        self.max_width_spinbox = QSpinBox()
        self.max_width_spinbox.setRange(100, 5000)
        settings_layout.addLayout(self._create_setting_row(
            self.translator.translate("widget_settings_max_width"), self.max_width_spinbox
        ))
        
        # -- Padding Gruppe --
        padding_group = QGroupBox(self.translator.translate("widget_settings_padding_group"))
        padding_main_layout = QVBoxLayout(padding_group)

        # Padding Modus Auswahl
        self.padding_mode_factor_rb = QRadioButton(self.translator.translate("widget_settings_padding_factor"))
        self.padding_mode_pixels_rb = QRadioButton(self.translator.translate("widget_settings_padding_pixels"))
        padding_mode_layout = QHBoxLayout()
        padding_mode_layout.addWidget(QLabel(self.translator.translate("widget_settings_padding_mode")))
        padding_mode_layout.addWidget(self.padding_mode_factor_rb)
        padding_mode_layout.addWidget(self.padding_mode_pixels_rb)
        padding_mode_layout.addStretch()
        padding_main_layout.addLayout(padding_mode_layout)

        # Faktor-Eingabe
        self.padding_factor_spinbox = QDoubleSpinBox()
        self.padding_factor_spinbox.setRange(0.0, 2.0)
        self.padding_factor_spinbox.setSingleStep(0.05)
        self.padding_factor_spinbox.setDecimals(2)
        padding_main_layout.addLayout(self._create_setting_row(
             self.translator.translate("widget_settings_padding_factor_value"), self.padding_factor_spinbox
        ))
        
        # Pixel-Eingaben
        self.pixel_widgets_container = QWidget()
        pixel_layout = QHBoxLayout(self.pixel_widgets_container)
        pixel_layout.setContentsMargins(0,0,0,0)
        self.padding_left_spin = QSpinBox(); self.padding_left_spin.setRange(0, 50)
        self.padding_top_spin = QSpinBox(); self.padding_top_spin.setRange(0, 50)
        self.padding_right_spin = QSpinBox(); self.padding_right_spin.setRange(0, 50)
        self.padding_bottom_spin = QSpinBox(); self.padding_bottom_spin.setRange(0, 50)
        pixel_layout.addWidget(QLabel(self.translator.translate("widget_settings_padding_left")))
        pixel_layout.addWidget(self.padding_left_spin)
        pixel_layout.addWidget(QLabel(self.translator.translate("widget_settings_padding_top")))
        pixel_layout.addWidget(self.padding_top_spin)
        pixel_layout.addWidget(QLabel(self.translator.translate("widget_settings_padding_right")))
        pixel_layout.addWidget(self.padding_right_spin)
        pixel_layout.addWidget(QLabel(self.translator.translate("widget_settings_padding_bottom")))
        pixel_layout.addWidget(self.padding_bottom_spin)
        padding_main_layout.addWidget(self.pixel_widgets_container)

        settings_layout.addWidget(padding_group)
        layout.addWidget(settings_group)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                           QDialogButtonBox.StandardButton.Cancel |
                                           QDialogButtonBox.StandardButton.Apply)
        ok_button = self.button_box.button(QDialogButtonBox.StandardButton.Ok)
        cancel_button = self.button_box.button(QDialogButtonBox.StandardButton.Cancel)
        apply_button = self.button_box.button(QDialogButtonBox.StandardButton.Apply)
        if ok_button is not None:
            style_dialog_button(ok_button, "primary")
        if cancel_button is not None:
            style_dialog_button(cancel_button, "secondary")
        if apply_button is not None:
            style_dialog_button(apply_button, "accent")
        layout.addWidget(self.button_box)

    def _create_slider(self, min_val: int, max_val: int) -> QSlider:
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(min_val, max_val)
        return slider

    def _create_setting_row(self, label_text: str, widget: QWidget | QHBoxLayout) -> QHBoxLayout:
        layout = QHBoxLayout()
        label = QLabel(label_text)
        label.setFixedWidth(150)
        layout.addWidget(label)
        if isinstance(widget, QWidget):
            layout.addWidget(widget)
        else:
            layout.addLayout(widget)
        return layout

    def _load_settings(self):
        """Lädt alle Einstellungen und setzt die UI-Elemente."""
        self.font_size_slider.setValue(self.settings_manager.get_setting(SettingsKey.FONT_SIZE.value, 10))
        self.show_bar_checkbox.setChecked(self.settings_manager.get_setting(SettingsKey.SHOW_BAR_GRAPHS.value, True))
        self.bar_width_slider.setValue(self.settings_manager.get_setting(SettingsKey.BAR_GRAPH_WIDTH_MULTIPLIER.value, 9))
        self.bar_height_spinbox.setValue(
            self.settings_manager.get_setting(SettingsKey.BAR_GRAPH_HEIGHT_FACTOR.value, 0.65)
        )
        self.min_width_spinbox.setValue(self.settings_manager.get_setting(SettingsKey.WIDGET_MIN_WIDTH.value, 50))
        self.max_width_spinbox.setValue(self.settings_manager.get_setting(SettingsKey.WIDGET_MAX_WIDTH.value, 2000))
        self._sync_widget_width_slider_range()
        was_blocked = self.widget_width_slider.blockSignals(True)
        self.widget_width_slider.setValue(self._get_initial_widget_width())
        self.widget_width_slider.blockSignals(was_blocked)

        # Padding-Einstellungen laden
        padding_mode = self.settings_manager.get_setting(SettingsKey.WIDGET_PADDING_MODE.value, "factor")
        if padding_mode == "factor":
            self.padding_mode_factor_rb.setChecked(True)
        else:
            self.padding_mode_pixels_rb.setChecked(True)
        
        self.padding_factor_spinbox.setValue(self.settings_manager.get_setting(SettingsKey.WIDGET_PADDING_FACTOR.value, 0.25))
        self.padding_left_spin.setValue(self.settings_manager.get_setting(SettingsKey.WIDGET_PADDING_LEFT.value, 5))
        self.padding_top_spin.setValue(self.settings_manager.get_setting(SettingsKey.WIDGET_PADDING_TOP.value, 2))
        self.padding_right_spin.setValue(self.settings_manager.get_setting(SettingsKey.WIDGET_PADDING_RIGHT.value, 5))
        self.padding_bottom_spin.setValue(self.settings_manager.get_setting(SettingsKey.WIDGET_PADDING_BOTTOM.value, 2))

        self._on_padding_mode_changed()
        self._last_font_size_for_auto_width = self.font_size_slider.value()

    def _collect_dialog_settings(self) -> Dict[str, object]:
        min_width = self.min_width_spinbox.value()
        max_width = self.max_width_spinbox.value()
        if min_width > max_width:
            max_width = min_width

        return {
            SettingsKey.FONT_SIZE.value: self.font_size_slider.value(),
            SettingsKey.SHOW_BAR_GRAPHS.value: self.show_bar_checkbox.isChecked(),
            SettingsKey.BAR_GRAPH_WIDTH_MULTIPLIER.value: self.bar_width_slider.value(),
            SettingsKey.BAR_GRAPH_HEIGHT_FACTOR.value: self.bar_height_spinbox.value(),
            SettingsKey.WIDGET_MIN_WIDTH.value: min_width,
            SettingsKey.WIDGET_MAX_WIDTH.value: max_width,
            SettingsKey.WIDGET_PADDING_MODE.value: (
                "factor" if self.padding_mode_factor_rb.isChecked() else "pixels"
            ),
            SettingsKey.WIDGET_PADDING_FACTOR.value: self.padding_factor_spinbox.value(),
            SettingsKey.WIDGET_PADDING_LEFT.value: self.padding_left_spin.value(),
            SettingsKey.WIDGET_PADDING_TOP.value: self.padding_top_spin.value(),
            SettingsKey.WIDGET_PADDING_RIGHT.value: self.padding_right_spin.value(),
            SettingsKey.WIDGET_PADDING_BOTTOM.value: self.padding_bottom_spin.value(),
        }

    def _restore_original_live_state(self):
        self.detachable_manager.preview_widget_appearance(self._original_settings)
        self.detachable_manager.preview_widget_widths(self._original_widths)

    def _get_initial_widget_width(self) -> int:
        active_widths = list(self.detachable_manager.get_active_widget_widths().values())
        if active_widths:
            return int(round(sum(active_widths) / len(active_widths)))
        return self.min_width_spinbox.value()

    def _sync_widget_width_slider_range(self):
        min_width = self.min_width_spinbox.value()
        max_width = max(min_width, self.max_width_spinbox.value())
        current_value = max(min_width, min(max_width, self.widget_width_slider.value()))

        was_blocked = self.widget_width_slider.blockSignals(True)
        self.widget_width_slider.setRange(min_width, max_width)
        self.widget_width_slider.setValue(current_value)
        self.widget_width_slider.blockSignals(was_blocked)

        if self._preview_width_override is not None:
            self._preview_width_override = current_value

    def _get_preview_widths(self) -> Dict[str, int]:
        settings = self._collect_dialog_settings()
        min_width = int(settings[SettingsKey.WIDGET_MIN_WIDTH.value])
        max_width = int(settings[SettingsKey.WIDGET_MAX_WIDTH.value])
        if self._preview_width_override is not None:
            uniform_width = max(min_width, min(max_width, self._preview_width_override))
            return {key: uniform_width for key in self._original_widths}
        return {
            key: max(min_width, min(max_width, width))
            for key, width in self._original_widths.items()
        }

    def _clamp_width_to_range(self, width: int) -> int:
        min_width = self.min_width_spinbox.value()
        max_width = max(min_width, self.max_width_spinbox.value())
        return max(min_width, min(max_width, int(width)))

    def _connect_signals(self):
        """Verbindet alle Signale mit den entsprechenden Slots."""
        # Allgemeine Einstellungen
        self.font_size_slider.valueChanged.connect(self._on_font_size_changed)
        self.bar_width_slider.valueChanged.connect(self._update_preview)
        self.bar_height_spinbox.valueChanged.connect(self._update_preview)
        self.widget_width_slider.valueChanged.connect(self._on_widget_width_changed)
        self.show_bar_checkbox.toggled.connect(self._update_preview)
        self.min_width_spinbox.valueChanged.connect(self._on_min_width_changed)
        self.max_width_spinbox.valueChanged.connect(self._on_max_width_changed)

        # Padding-Einstellungen
        self.padding_mode_factor_rb.toggled.connect(self._on_padding_mode_changed)
        self.padding_mode_pixels_rb.toggled.connect(self._on_padding_mode_changed)
        self.padding_factor_spinbox.valueChanged.connect(self._update_preview)
        self.padding_left_spin.valueChanged.connect(self._update_preview)
        self.padding_top_spin.valueChanged.connect(self._update_preview)
        self.padding_right_spin.valueChanged.connect(self._update_preview)
        self.padding_bottom_spin.valueChanged.connect(self._update_preview)

        # Schaltflächen
        self.button_box.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self._apply_settings)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

    def _on_min_width_changed(self, value: int):
        if value > self.max_width_spinbox.value():
            was_blocked = self.max_width_spinbox.blockSignals(True)
            self.max_width_spinbox.setValue(value)
            self.max_width_spinbox.blockSignals(was_blocked)
        self._sync_widget_width_slider_range()
        self._update_preview()

    def _on_max_width_changed(self, value: int):
        if value < self.min_width_spinbox.value():
            was_blocked = self.min_width_spinbox.blockSignals(True)
            self.min_width_spinbox.setValue(value)
            self.min_width_spinbox.blockSignals(was_blocked)
        self._sync_widget_width_slider_range()
        self._update_preview()

    def _on_widget_width_changed(self, value: int):
        self._preview_width_override = value
        self._update_preview()

    def _on_font_size_changed(self, value: int):
        previous_font_size = max(1, int(self._last_font_size_for_auto_width))
        self._last_font_size_for_auto_width = int(value)
        if self._suspend_auto_width_scaling:
            return

        current_width = self.widget_width_slider.value()
        scaled_width = int(round(current_width * (int(value) / previous_font_size)))
        clamped_width = self._clamp_width_to_range(scaled_width)

        was_blocked = self.widget_width_slider.blockSignals(True)
        self.widget_width_slider.setValue(clamped_width)
        self.widget_width_slider.blockSignals(was_blocked)

        self._preview_width_override = clamped_width
        self._update_preview()

    # GEÄNDERT: Verwendet .setEnabled() statt .setVisible()
    def _on_padding_mode_changed(self):
        """Aktiviert/Deaktiviert die passenden Eingabefelder je nach Padding-Modus."""
        is_factor_mode = self.padding_mode_factor_rb.isChecked()
        self.padding_factor_spinbox.setEnabled(is_factor_mode)
        self.pixel_widgets_container.setEnabled(not is_factor_mode)
        self._update_preview()

    def _update_preview(self):
        """Wendet die aktuellen Dialogwerte direkt auf die aktiven Widgets an."""
        live_settings = self._collect_dialog_settings()
        self.detachable_manager.preview_widget_appearance(live_settings)
        self.detachable_manager.preview_widget_widths(self._get_preview_widths())
        self.adjustSize()

    def _apply_settings(self):
        """Speichert die Einstellungen und wendet sie auf alle Widgets an."""
        live_settings = self._collect_dialog_settings()
        self.settings_manager.update_settings(live_settings)
        self.detachable_manager.apply_styles_to_all_active_widgets()
        if self._preview_width_override is not None:
            self.detachable_manager.set_uniform_widget_width(self.widget_width_slider.value())
        self._original_settings = dict(live_settings)
        self._original_widths = self.detachable_manager.get_active_widget_widths()

    def accept(self):
        """Wendet Einstellungen an und schließt das Fenster."""
        self._apply_settings()
        self._closing_with_commit = True
        super().accept()

    def reject(self):
        self._restore_original_live_state()
        super().reject()

    def closeEvent(self, event: QCloseEvent):
        if not self._closing_with_commit:
            self._restore_original_live_state()
        super().closeEvent(event)

    def export_language_refresh_state(self) -> Dict[str, object]:
        return {
            "dialog_settings": self._collect_dialog_settings(),
            "widget_width": self.widget_width_slider.value(),
            "preview_width_override": self._preview_width_override,
            "original_settings": dict(self._original_settings),
            "original_widths": dict(self._original_widths),
        }

    def apply_language_refresh_state(self, state: Dict[str, object]):
        dialog_settings = state.get("dialog_settings", {})

        self._suspend_auto_width_scaling = True
        try:
            self.font_size_slider.setValue(int(dialog_settings.get(SettingsKey.FONT_SIZE.value, self.font_size_slider.value())))
            self.show_bar_checkbox.setChecked(bool(dialog_settings.get(SettingsKey.SHOW_BAR_GRAPHS.value, self.show_bar_checkbox.isChecked())))
            self.bar_width_slider.setValue(int(dialog_settings.get(SettingsKey.BAR_GRAPH_WIDTH_MULTIPLIER.value, self.bar_width_slider.value())))
            self.bar_height_spinbox.setValue(float(dialog_settings.get(SettingsKey.BAR_GRAPH_HEIGHT_FACTOR.value, self.bar_height_spinbox.value())))
            self.min_width_spinbox.setValue(int(dialog_settings.get(SettingsKey.WIDGET_MIN_WIDTH.value, self.min_width_spinbox.value())))
            self.max_width_spinbox.setValue(int(dialog_settings.get(SettingsKey.WIDGET_MAX_WIDTH.value, self.max_width_spinbox.value())))

            padding_mode = dialog_settings.get(SettingsKey.WIDGET_PADDING_MODE.value, "factor")
            self.padding_mode_factor_rb.setChecked(padding_mode == "factor")
            self.padding_mode_pixels_rb.setChecked(padding_mode != "factor")
            self.padding_factor_spinbox.setValue(float(dialog_settings.get(SettingsKey.WIDGET_PADDING_FACTOR.value, self.padding_factor_spinbox.value())))
            self.padding_left_spin.setValue(int(dialog_settings.get(SettingsKey.WIDGET_PADDING_LEFT.value, self.padding_left_spin.value())))
            self.padding_top_spin.setValue(int(dialog_settings.get(SettingsKey.WIDGET_PADDING_TOP.value, self.padding_top_spin.value())))
            self.padding_right_spin.setValue(int(dialog_settings.get(SettingsKey.WIDGET_PADDING_RIGHT.value, self.padding_right_spin.value())))
            self.padding_bottom_spin.setValue(int(dialog_settings.get(SettingsKey.WIDGET_PADDING_BOTTOM.value, self.padding_bottom_spin.value())))
        finally:
            self._suspend_auto_width_scaling = False

        self._sync_widget_width_slider_range()
        self._preview_width_override = state.get("preview_width_override")
        self.widget_width_slider.setValue(int(state.get("widget_width", self.widget_width_slider.value())))
        self._original_settings = dict(state.get("original_settings", self._original_settings))
        self._original_widths = dict(state.get("original_widths", self._original_widths))
        self._update_preview()
