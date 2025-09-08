# ui/widgets/font_settings_window.py
from __future__ import annotations
import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QLabel, QComboBox, 
    QSpinBox, QCheckBox, QPushButton, QGroupBox
)
from PySide6.QtGui import QFont, QIcon, QFontDatabase
from PySide6.QtCore import Qt, QTimer

from .base_window import SafeWindow
from config.constants import SettingsKey

if TYPE_CHECKING:
    from core.main_window import SystemMonitor


class FontSettingsWindow(SafeWindow):
    """
    Eigenes Font-Einstellungen Fenster - STABIL ohne problematische PySide6 Font-Dialogs.
    Unterstützt sowohl System-Fonts als auch lokale TTF-Dateien aus dem assets/fonts/ Ordner.
    """
    
    def __init__(self, main_window: SystemMonitor):
        super().__init__(main_window)
        self.main_app = main_window
        self.settings_manager = main_window.settings_manager
        self.translator = main_window.translator
        
        # Font-Datenbank für das Laden lokaler Fonts
        self.font_database = QFontDatabase()
        self.loaded_fonts = {}  # Font-Name -> Font-Pfad Mapping
        
        self.current_family = self.settings_manager.get_setting(SettingsKey.FONT_FAMILY.value, "Consolas")
        self.current_size = self.settings_manager.get_setting(SettingsKey.FONT_SIZE.value, 9)
        self.current_weight = self.settings_manager.get_setting(SettingsKey.FONT_WEIGHT.value, "normal")
        
        self.setWindowTitle(self.translator.translate("win_title_font"))
        self.setMinimumSize(500, 600)
        self.resize(500, 600)
        
        try:
            self.setWindowIcon(self.main_app.tray_icon_manager.tray_icon.icon())
        except AttributeError:
            self.setWindowIcon(QIcon())
        
        self._load_local_fonts()
        self._setup_ui()
        self._load_current_values()
        self._connect_signals()
        self._update_preview()
    
    def _load_local_fonts(self):
        """Lädt lokale TTF-Dateien aus dem assets/fonts/ Ordner."""
        try:
            # Ermittlung des assets/fonts Pfades relativ zur Anwendung
            app_dir = Path(__file__).parent.parent.parent  # Zurück zu SystemMonitorOverlay/
            fonts_dir = app_dir / "assets" / "fonts"
            
            if not fonts_dir.exists():
                logging.warning(f"Fonts-Ordner nicht gefunden: {fonts_dir}")
                return
            
            # Alle TTF-Dateien im Fonts-Ordner laden
            ttf_files = list(fonts_dir.glob("*.ttf"))
            
            for font_file in ttf_files:
                try:
                    font_id = self.font_database.addApplicationFont(str(font_file))
                    if font_id != -1:
                        # Font-Familie(n) aus der geladenen Datei extrahieren
                        families = self.font_database.applicationFontFamilies(font_id)
                        for family in families:
                            self.loaded_fonts[family] = str(font_file)
                            logging.info(f"Font geladen: {family} aus {font_file.name}")
                    else:
                        logging.warning(f"Konnte Font nicht laden: {font_file}")
                except Exception as e:
                    logging.error(f"Fehler beim Laden von Font {font_file}: {e}")
                    
        except Exception as e:
            logging.error(f"Fehler beim Laden lokaler Fonts: {e}")
    
    def _get_available_fonts(self) -> list[str]:
        """Gibt eine Liste aller verfügbaren Fonts zurück (System + lokale)."""
        # Standard System-Fonts
        system_fonts = [
            "Consolas", "Courier New", "Arial", "Helvetica", "Segoe UI", 
            "Calibri", "Verdana", "Tahoma", "Times New Roman", "Georgia", 
            "Trebuchet MS", "Source Code Pro"
        ]
        
        # Lokale Fonts hinzufügen
        local_fonts = list(self.loaded_fonts.keys())
        
        # Kombinieren und sortieren, Duplikate entfernen
        all_fonts = sorted(set(system_fonts + local_fonts))
        
        # Geladene lokale Fonts an den Anfang setzen (bessere Sichtbarkeit)
        priority_fonts = [font for font in local_fonts if font in all_fonts]
        other_fonts = [font for font in all_fonts if font not in priority_fonts]
        
        return priority_fonts + other_fonts
    
    def _setup_ui(self):
        """Erstellt die Benutzeroberfläche."""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        settings_group = QGroupBox(self.translator.translate("win_font_selection_group"))
        settings_layout = QVBoxLayout(settings_group)
        settings_layout.setSpacing(15)
        
        # Font-Familie mit lokalen Fonts
        family_layout = QHBoxLayout()
        family_label = QLabel(self.translator.translate("win_font_family"))
        self.family_combo = QComboBox()
        self.family_combo.addItems(self._get_available_fonts())
        family_layout.addWidget(family_label)
        family_layout.addWidget(self.family_combo, 1)
        settings_layout.addLayout(family_layout)
        
        # Info-Label für lokale Fonts
        if self.loaded_fonts:
            info_label = QLabel(self.translator.translate("win_font_local_fonts_loaded", count=len(self.loaded_fonts)))
            info_label.setStyleSheet("color: #4CAF50; font-size: 10px;")
            settings_layout.addWidget(info_label)
        
        size_layout = QHBoxLayout()
        size_label = QLabel(self.translator.translate("win_font_size"))
        self.size_spinbox = QSpinBox()
        self.size_spinbox.setRange(6, 72)
        self.size_spinbox.setSuffix(self.translator.translate("win_font_points_suffix"))
        size_layout.addWidget(size_label)
        size_layout.addWidget(self.size_spinbox)
        size_layout.addStretch()
        settings_layout.addLayout(size_layout)
        
        style_layout = QHBoxLayout()
        style_label = QLabel(self.translator.translate("win_font_style"))
        self.bold_checkbox = QCheckBox(self.translator.translate("win_font_bold"))
        style_layout.addWidget(style_label)
        style_layout.addWidget(self.bold_checkbox)
        style_layout.addStretch()
        settings_layout.addLayout(style_layout)
        layout.addWidget(settings_group)
        
        preview_group = QGroupBox(self.translator.translate("win_font_preview_group"))
        preview_layout = QVBoxLayout(preview_group)
        self.preview_label = QLabel() # Text wird in _update_preview gesetzt
        self.preview_label.setStyleSheet("background-color: #2b2b2b; color: #ffffff; padding: 20px; border-radius: 5px;")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_layout.addWidget(self.preview_label)
        layout.addWidget(preview_group)
        layout.addStretch()
        
        button_layout = QHBoxLayout()
        self.reset_button = QPushButton(self.translator.translate("win_shared_button_reset"))
        self.cancel_button = QPushButton(self.translator.translate("win_shared_button_cancel"))
        self.apply_button = QPushButton(self.translator.translate("win_shared_button_apply"))
        button_layout.addStretch()
        button_layout.addWidget(self.reset_button)
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.apply_button)
        layout.addLayout(button_layout)
    
    def _load_current_values(self):
        """Lädt die aktuellen Einstellungen in die UI."""
        if (idx := self.family_combo.findText(self.current_family)) >= 0:
            self.family_combo.setCurrentIndex(idx)
        else:
            # Falls der gespeicherte Font nicht in der Liste ist, hinzufügen
            self.family_combo.insertItem(0, self.current_family)
            self.family_combo.setCurrentIndex(0)
        
        self.size_spinbox.setValue(self.current_size)
        self.bold_checkbox.setChecked(self.current_weight == "bold")
    
    def _connect_signals(self):
        """Verbindet UI-Signale mit Methoden."""
        self.family_combo.currentTextChanged.connect(self._update_preview)
        self.size_spinbox.valueChanged.connect(self._update_preview)
        self.bold_checkbox.toggled.connect(self._update_preview)
        self.reset_button.clicked.connect(self._reset_to_defaults)
        self.cancel_button.clicked.connect(self.close_safely)
        self.apply_button.clicked.connect(self._apply_settings)
    
    def _update_preview(self):
        """Aktualisiert die Schriftart-Vorschau."""
        font_family = self.family_combo.currentText()
        font_size = self.size_spinbox.value()
        is_bold = self.bold_checkbox.isChecked()
        
        # Font erstellen - funktioniert sowohl mit System- als auch geladenen Fonts
        font = QFont(font_family, font_size)
        font.setBold(is_bold)
        
        # Zusätzliche Info für lokale Fonts in der Vorschau
        if font_family in self.loaded_fonts:
            base_text = self.translator.translate("win_font_preview_text")
            local_info = self.translator.translate("win_font_preview_local_font_info", filename=Path(self.loaded_fonts[font_family]).name)
            preview_text = f"{base_text}\n\n{local_info}"
        else:
            preview_text = self.translator.translate("win_font_preview_text")
        
        self.preview_label.setText(preview_text)
        self.preview_label.setFont(font)
    
    def _reset_to_defaults(self):
        """Setzt die Einstellungen auf Standardwerte zurück."""
        # Prüfen ob FiraCode verfügbar ist, ansonsten Consolas
        default_font = "FiraCode" if "FiraCode" in self.loaded_fonts else "Consolas"
        
        self.family_combo.setCurrentText(default_font)
        self.size_spinbox.setValue(9)
        self.bold_checkbox.setChecked(False)
    
    def _apply_settings(self):
        """Wendet die gewählten Einstellungen an."""
        selected_font = self.family_combo.currentText()
        
        updates = {
            SettingsKey.FONT_FAMILY.value: selected_font,
            SettingsKey.FONT_SIZE.value: self.size_spinbox.value(),
            SettingsKey.FONT_WEIGHT.value: "bold" if self.bold_checkbox.isChecked() else "normal"
        }
        
        self.settings_manager.update_settings(updates)
        
        # Zusätzliche Logging-Info für lokale Fonts
        if selected_font in self.loaded_fonts:
            logging.info(f"Lokale Font angewendet: {selected_font} aus {self.loaded_fonts[selected_font]}")
        
        # UI-Update leicht verzögert ausführen, damit die Einstellungen sicher geschrieben sind
        QTimer.singleShot(50, self.main_app.ui_manager.apply_styles)
        self.close_safely()