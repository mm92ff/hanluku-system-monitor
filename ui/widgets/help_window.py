# ui/widgets/help_window.py
from __future__ import annotations
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QVBoxLayout, QTextEdit, QPushButton, QHBoxLayout
from PySide6.QtGui import QIcon, QFont, QTextCursor
from .base_window import SafeWindow

if TYPE_CHECKING:
    from core.main_window import SystemMonitor

class HelpWindow(SafeWindow):
    """
    Ein Fenster, das detaillierte Hilfe und Erklärungen zu den Funktionen
    der Anwendung anzeigt.
    """
    def __init__(self, main_app: SystemMonitor):
        super().__init__(main_app)
        self.main_app = main_app
        self.translator = main_app.translator
        
        self.setWindowTitle(self.translator.translate("win_title_help"))
        self.setMinimumSize(700, 800)
        
        try:
            self.setWindowIcon(self.main_app.tray_icon_manager.tray_icon.icon())
        except AttributeError:
            self.setWindowIcon(QIcon())
            
        self._setup_ui()
        self._populate_help_text()

    def _setup_ui(self):
        """Erstellt die Benutzeroberfläche des Fensters."""
        layout = QVBoxLayout(self)
        
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setFont(QFont("Segoe UI", 10))
        layout.addWidget(self.text_edit)
        
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        close_button = QPushButton(self.translator.translate("win_shared_button_close"))
        close_button.clicked.connect(self.close_safely)
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)

    def _populate_help_text(self):
        """Füllt das Textfeld mit dem formatierten Hilfe-Inhalt aus dem Übersetzungssystem."""
        
        t = self.translator.translate
        
        content = f"""
        <h1>{t("help_heading")}</h1>
        <p>{t("help_intro")}</p>

        <h2>{t("help_layout_heading")}</h2>
        <p>{t("help_layout_intro")}</p>
        <ul>
            <li><b>{t("help_layout_item1_title")}:</b> {t("help_layout_item1_desc")}</li>
            <li><b>{t("help_layout_item2_title")}:</b> {t("help_layout_item2_desc")}</li>
            <li><b>{t("help_layout_item3_title")}:</b> {t("help_layout_item3_desc")}</li>
            <li><b>{t("help_layout_item4_title")}:</b> {t("help_layout_item4_desc")}</li>
            <li><b>{t("help_layout_item5_title")}:</b> {t("help_layout_item5_desc")}</li>
        </ul>
        
        <h2>{t("help_grouping_heading")}</h2>
        <p>{t("help_grouping_intro")}</p>
        <ul>
            <li><b>{t("help_grouping_item1_title")}:</b> {t("help_grouping_item1_desc")}</li>
            <li><b>{t("help_grouping_item2_title")}:</b> {t("help_grouping_item2_desc")}</li>
            <li><b>{t("help_grouping_item3_title")}:</b> {t("help_grouping_item3_desc")}</li>
        </ul>

        <h2>{t("help_custom_heading")}</h2>
        <p>{t("help_custom_intro")}</p>
        <ol>
            <li>{t("help_custom_step1")}</li>
            <li>{t("help_custom_step2")}</li>
            <li>{t("help_custom_step3")}</li>
            <li>{t("help_custom_step4")}</li>
            <li>{t("help_custom_step5")}</li>
            <li>{t("help_custom_step6")}</li>
        </ol>

        <h2>{t("help_monitoring_heading")}</h2>
        <p>{t("help_monitoring_intro")}</p>
        <ul>
            <li><b>{t("help_monitoring_item1_title")}:</b> {t("help_monitoring_item1_desc")}</li>
            <li><b>{t("help_monitoring_item2_title")}:</b> {t("help_monitoring_item2_desc")}</li>
            <li><b>{t("help_monitoring_item3_title")}:</b> {t("help_monitoring_item3_desc")}</li>
        </ul>

        <h2>{t("help_tray_heading")}</h2>
        <p>{t("help_tray_intro")}</p>
        <ul>
            <li><b>{t("help_tray_item1_title")}:</b> {t("help_tray_item1_desc")}</li>
            <li><b>{t("help_tray_item2_title")}:</b> {t("help_tray_item2_desc")}</li>
            <li><b>{t("help_tray_item3_title")}:</b> {t("help_tray_item3_desc")}</li>
        </ul>
        
        <h2>{t("help_config_heading")}</h2>
        <p>{t("help_config_intro")}</p>
        <ul>
            <li><b>{t("help_config_item1_title")}:</b> {t("help_config_item1_desc")}</li>
            <li><b>{t("help_config_item2_title")}:</b> {t("help_config_item2_desc")}</li>
            <li><b>{t("help_config_item3_title")}:</b> {t("help_config_item3_desc")}</li>
            <li><b>{t("help_config_item4_title")}:</b> {t("help_config_item4_desc")}</li>
        </ul>

        <h2>{t("help_other_heading")}</h2>
        <ul>
            <li><b>{t("help_other_item1_title")}:</b> {t("help_other_item1_desc")}</li>
            <li><b>{t("help_other_item2_title")}:</b> {t("help_other_item2_desc")}</li>
            <li><b>{t("help_other_item3_title")}:</b> {t("help_other_item3_desc")}</li>
            <li><b>{t("help_other_item4_title")}:</b> {t("help_other_item4_desc")}</li>
        </ul>

        <br><hr><br>
        <h2>{t("help_license_heading_libs")}</h2>
        <p>{t("help_license_libs_text_lhm")}<br><br>{t("help_license_libs_text_hidsharp")}<br><br>{t("help_license_libs_text_firacode")}</p>
        
        <h2>{t("help_license_heading_project")}</h2>
        <p>{t("help_license_project_text")}</p>
        """
        
        self.text_edit.setHtml(content)
        self.text_edit.moveCursor(QTextCursor.MoveOperation.Start)