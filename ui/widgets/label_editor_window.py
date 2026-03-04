# ui/widgets/label_editor_window.py
import logging
from functools import partial
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QScrollArea, QGridLayout,
    QPushButton, QLineEdit, QWidget, QCheckBox, QSpinBox, QDoubleSpinBox,
    QGroupBox, QFormLayout
)
from PySide6.QtGui import QIcon
from .base_window import (
    SafeWindow,
    configure_dialog_layout,
    configure_dialog_window,
    style_dialog_button,
    style_info_label,
)
from config.constants import SettingsKey


class LabelEditorWindow(SafeWindow):
    """
    Fenster zum Bearbeiten aller Labeltexte und Abstandseinstellungen.
    """
    def __init__(self, main_app):
        super().__init__(main_app)
        self.main_app = main_app
        self.translator = main_app.translator
        self.settings_manager = main_app.settings_manager
        self.setWindowTitle(self.translator.translate("win_title_label"))

        try:
            self.setWindowIcon(self.main_app.tray_icon_manager.tray_icon.icon())
        except AttributeError:
            self.setWindowIcon(QIcon())

        configure_dialog_window(self, 550, 600)
        self.input_widgets = {}
        
        self.init_ui()
        self._load_settings()
        self._build_label_list()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        configure_dialog_layout(main_layout)
        
        labels_group = QGroupBox(self.translator.translate("win_label_metric_display_texts"))
        labels_layout = QVBoxLayout(labels_group)
        configure_dialog_layout(labels_layout, margins=(12, 12, 12, 12))
        info_label = QLabel(self.translator.translate("win_label_editor_info"))
        style_info_label(info_label, "muted")
        labels_layout.addWidget(info_label)

        truncate_layout = QHBoxLayout()
        self.truncate_checkbox = QCheckBox(self.translator.translate("win_label_truncate_text"))
        self.length_spinbox = QSpinBox(); self.length_spinbox.setRange(3, 100)
        truncate_layout.addWidget(self.truncate_checkbox)
        truncate_layout.addWidget(self.length_spinbox)
        truncate_layout.addWidget(QLabel(self.translator.translate("win_label_characters"))); truncate_layout.addStretch()
        labels_layout.addLayout(truncate_layout)
        
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel(f'<b>{self.translator.translate("win_label_default_text")}</b>'), 2)
        header_layout.addWidget(QLabel(f'<b>{self.translator.translate("win_label_custom_text")}</b>'), 3)
        header_layout.addWidget(QLabel(f'<b>{self.translator.translate("win_label_action")}</b>'), 1)
        labels_layout.addLayout(header_layout)

        scroll_area = QScrollArea(); scroll_area.setWidgetResizable(True)
        labels_layout.addWidget(scroll_area)
        container = QWidget()
        self.grid_layout = QGridLayout(container)
        scroll_area.setWidget(container)
        main_layout.addWidget(labels_group)
        
        main_layout.addStretch() # Fügt dehnbaren Platz hinzu

        button_layout = QHBoxLayout()
        reset_all_button = QPushButton(self.translator.translate("win_label_reset_all_texts"))
        reset_all_button.clicked.connect(self.reset_all)
        save_button = QPushButton(self.translator.translate("win_shared_button_save_close"))
        save_button.clicked.connect(self.save_and_close)
        cancel_button = QPushButton(self.translator.translate("win_shared_button_cancel"))
        cancel_button.clicked.connect(self.close_safely)
        style_dialog_button(reset_all_button, "compact")
        style_dialog_button(save_button, "primary")
        style_dialog_button(cancel_button, "secondary")
        button_layout.addWidget(reset_all_button); button_layout.addStretch()
        button_layout.addWidget(save_button); button_layout.addWidget(cancel_button)
        main_layout.addLayout(button_layout)

    def _load_settings(self):
        """Lädt alle relevanten Einstellungen für dieses Fenster."""
        self.truncate_checkbox.setChecked(self.settings_manager.get_setting(SettingsKey.LABEL_TRUNCATE_ENABLED.value, False))
        self.length_spinbox.setValue(self.settings_manager.get_setting(SettingsKey.LABEL_TRUNCATE_LENGTH.value, 15))

    def _build_label_list(self):
        """Baut die Liste der Labels aus dem UIManager auf."""
        all_widgets_info = self.main_app.ui_manager.metric_widgets
        custom_labels = self.settings_manager.get_setting(SettingsKey.CUSTOM_LABELS.value, {})
        metric_order = self.settings_manager.get_setting(SettingsKey.METRIC_ORDER.value, list(all_widgets_info.keys()))

        for row, key in enumerate(metric_order):
            if key not in all_widgets_info: continue
            info = all_widgets_info[key]
            default_text = info.get('default_text', 'N/A')
            edit_input = QLineEdit(custom_labels.get(key, "")); edit_input.setPlaceholderText(default_text)
            reset_button = QPushButton(self.translator.translate("win_shared_button_reset")); reset_button.clicked.connect(partial(self.reset_single, key))
            style_dialog_button(reset_button, "compact")
            self.grid_layout.addWidget(QLabel(default_text), row, 0)
            self.grid_layout.addWidget(edit_input, row, 1)
            self.grid_layout.addWidget(reset_button, row, 2)
            self.input_widgets[key] = edit_input

    def reset_single(self, key: str):
        if key in self.input_widgets: self.input_widgets[key].clear()

    def reset_all(self):
        for input_widget in self.input_widgets.values(): input_widget.clear()

    def save_and_close(self):
        """Speichert alle Einstellungen und stößt eine UI-Aktualisierung an."""
        updates = {
            SettingsKey.LABEL_TRUNCATE_ENABLED.value: self.truncate_checkbox.isChecked(),
            SettingsKey.LABEL_TRUNCATE_LENGTH.value: self.length_spinbox.value(),
            SettingsKey.CUSTOM_LABELS.value: {k: w.text().strip() for k, w in self.input_widgets.items() if w.text().strip()}
        }
        
        self.settings_manager.update_settings(updates)
        
        self.main_app.ui_manager.apply_styles()
        self.main_app.tray_icon_manager.rebuild_menu()
        self.close_safely()

    def export_language_refresh_state(self) -> dict:
        return {
            "truncate": self.truncate_checkbox.isChecked(),
            "length": self.length_spinbox.value(),
            "texts": {key: widget.text() for key, widget in self.input_widgets.items()},
        }

    def apply_language_refresh_state(self, state: dict):
        self.truncate_checkbox.setChecked(state.get("truncate", self.truncate_checkbox.isChecked()))
        self.length_spinbox.setValue(state.get("length", self.length_spinbox.value()))
        for key, text in state.get("texts", {}).items():
            if key in self.input_widgets:
                self.input_widgets[key].setText(text)
