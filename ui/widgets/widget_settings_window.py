# ui/widgets/widget_settings_window.py
from __future__ import annotations
from typing import TYPE_CHECKING, Optional

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QSlider, QLabel, QHBoxLayout,
    QRadioButton, QDialog, QDialogButtonBox, QDoubleSpinBox, QSpinBox,
    QCheckBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from detachable.detachable_widget import DetachableWidget
from config.constants import SettingsKey

if TYPE_CHECKING:
    from core.main_window import SystemMonitor


class WidgetSettingsWindow(QDialog):
    """
    Ein Einstellungsfenster zur visuellen Anpassung der DetachableWidgets
    mit einer Live-Vorschau.
    """

    def __init__(self, main_window: SystemMonitor):
        super().__init__(main_window)
        self.main_win = main_window
        self.settings_manager = main_window.settings_manager
        self.detachable_manager = main_window.detachable_manager
        self.translator = main_window.translator

        self.setWindowTitle(self.translator.translate("win_title_widget_settings"))
        self.setMinimumWidth(500)

        self._setup_ui()
        self._load_settings()
        self._connect_signals()
        self._update_preview()

    def _setup_ui(self):
        """Erstellt die Benutzeroberfläche des Fensters."""
        layout = QVBoxLayout(self)

        preview_group = QGroupBox(self.translator.translate("widget_settings_preview"))
        preview_layout = QVBoxLayout(preview_group)
        self.preview_widget = DetachableWidget(
            "preview",
            {'label_text': self.translator.translate("color_name_ram") + ":", 'has_bar': True},
            self.detachable_manager
        )
        self.preview_widget.update_data("12.1/127.9 GB", 65)
        self.preview_widget.set_value_style(False, "#00FFFF", "#FF0000")
        preview_layout.addWidget(self.preview_widget)
        layout.addWidget(preview_group)

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
        self.min_width_spinbox.setValue(self.settings_manager.get_setting(SettingsKey.WIDGET_MIN_WIDTH.value, 50))
        self.max_width_spinbox.setValue(self.settings_manager.get_setting(SettingsKey.WIDGET_MAX_WIDTH.value, 2000))

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

    def _connect_signals(self):
        """Verbindet alle Signale mit den entsprechenden Slots."""
        # Allgemeine Einstellungen
        self.font_size_slider.valueChanged.connect(self._update_preview)
        self.bar_width_slider.valueChanged.connect(self._update_preview)
        self.show_bar_checkbox.toggled.connect(self._update_preview)

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

    # GEÄNDERT: Verwendet .setEnabled() statt .setVisible()
    def _on_padding_mode_changed(self):
        """Aktiviert/Deaktiviert die passenden Eingabefelder je nach Padding-Modus."""
        is_factor_mode = self.padding_mode_factor_rb.isChecked()
        self.padding_factor_spinbox.setEnabled(is_factor_mode)
        self.pixel_widgets_container.setEnabled(not is_factor_mode)
        self._update_preview()

    def _update_preview(self):
        """Aktualisiert das Vorschau-Widget direkt mit den Werten aus der UI."""
        font_size = self.font_size_slider.value()
        show_bar = self.show_bar_checkbox.isChecked()
        bar_mult = self.bar_width_slider.value()
        bar_height_factor = self.settings_manager.get_setting(SettingsKey.BAR_GRAPH_HEIGHT_FACTOR.value, 0.65)

        font = QFont(
            self.settings_manager.get_setting(SettingsKey.FONT_FAMILY.value),
            max(6, font_size)
        )
        font.setBold(self.settings_manager.get_setting(SettingsKey.FONT_WEIGHT.value) == "bold")
        bar_width = max(30, font.pointSize() * bar_mult)

        # Padding berechnen und anwenden
        if self.padding_mode_factor_rb.isChecked():
            factor = self.padding_factor_spinbox.value()
            p_vert = int(font.pointSize() * factor)
            p_horiz = int(p_vert * 2.5)
            self.preview_widget.update_padding(p_horiz, p_vert, p_horiz, p_vert)
        else:
            self.preview_widget.update_padding(
                self.padding_left_spin.value(), self.padding_top_spin.value(),
                self.padding_right_spin.value(), self.padding_bottom_spin.value()
            )

        self.preview_widget.update_style(
            font, bar_width, show_bar, bar_height_factor, "preview"
        )
        
        self.adjustSize()

    def _apply_settings(self):
        """Speichert die Einstellungen und wendet sie auf alle Widgets an."""
        padding_mode = "factor" if self.padding_mode_factor_rb.isChecked() else "pixels"
        
        self.settings_manager.update_settings({
            SettingsKey.FONT_SIZE.value: self.font_size_slider.value(),
            SettingsKey.SHOW_BAR_GRAPHS.value: self.show_bar_checkbox.isChecked(),
            SettingsKey.BAR_GRAPH_WIDTH_MULTIPLIER.value: self.bar_width_slider.value(),
            SettingsKey.WIDGET_MIN_WIDTH.value: self.min_width_spinbox.value(),
            SettingsKey.WIDGET_MAX_WIDTH.value: self.max_width_spinbox.value(),
            SettingsKey.WIDGET_PADDING_MODE.value: padding_mode,
            SettingsKey.WIDGET_PADDING_FACTOR.value: self.padding_factor_spinbox.value(),
            SettingsKey.WIDGET_PADDING_LEFT.value: self.padding_left_spin.value(),
            SettingsKey.WIDGET_PADDING_TOP.value: self.padding_top_spin.value(),
            SettingsKey.WIDGET_PADDING_RIGHT.value: self.padding_right_spin.value(),
            SettingsKey.WIDGET_PADDING_BOTTOM.value: self.padding_bottom_spin.value()
        })

        self.detachable_manager.apply_styles_to_all_active_widgets()

    def accept(self):
        """Wendet Einstellungen an und schließt das Fenster."""
        self._apply_settings()
        super().accept()