# core/translation_manager.py
import json
import logging
from pathlib import Path
from typing import Dict, List, Any

from config.config import CONFIG_DIR
from core.translations import LANG_DE, LANG_EN


class TranslationManager:
    """
    Verwaltet die Mehrsprachigkeit der Anwendung.

    - Lädt Sprachdateien aus dem `language`-Verzeichnis.
    - Erstellt beim ersten Start Vorlagen für alle hartkodierten Sprachen.
    - Stellt eine zentrale `translate`-Methode zur Verfügung.
    - Ist robust gegen korrupte oder leere JSON-Dateien.
    """
    GERMAN = "german"
    ENGLISH = "english"
    FALLBACK_LANGUAGE = GERMAN

    def __init__(self) -> None:
        """Initialisiert den TranslationManager."""
        self.language_dir = Path(CONFIG_DIR) / "language"
        self.language_dir.mkdir(exist_ok=True)

        self._hardcoded_languages: Dict[str, Dict[str, str]] = {
            self.GERMAN: LANG_DE,
            self.ENGLISH: LANG_EN
        }
        self._file_languages: Dict[str, Dict[str, str]] = {}
        self.current_language: str = self.FALLBACK_LANGUAGE
        self.translations: Dict[str, str] = {}

        self._create_language_templates()
        self.scan_languages()
        # Initial-Sprache setzen nach dem Scannen
        self.set_language(self.FALLBACK_LANGUAGE)

    def _create_language_templates(self) -> None:
        """
        Erstellt für alle hartkodierten Sprachen eine JSON-Datei als Vorlage,
        falls diese noch nicht existiert.
        """
        for lang_name, lang_data in self._hardcoded_languages.items():
            template_file = self.language_dir / f"{lang_name}.json"
            if not template_file.exists():
                try:
                    with open(template_file, 'w', encoding='utf-8') as f:
                        json.dump(lang_data, f, indent=4, ensure_ascii=False)
                    logging.info(f"Sprachvorlage für '{lang_name}' erstellt: {template_file}")
                except IOError as e:
                    logging.exception(f"Konnte Sprachvorlage für '{lang_name}' nicht erstellen.")

    def scan_languages(self) -> None:
        """Sucht und lädt alle verfügbaren Sprachdateien aus dem language-Ordner."""
        self._file_languages = {}
        for file_path in self.language_dir.glob("*.json"):
            lang_name = file_path.stem.lower()
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if not content:
                        logging.warning(f"Sprachdatei '{file_path.name}' ist leer und wird übersprungen.")
                        continue

                    data = json.loads(content)
                    if isinstance(data, dict):
                        self._file_languages[lang_name] = data
                        logging.info(f"Sprache '{lang_name}' aus Datei geladen.")
                    else:
                        logging.warning(f"Sprachdatei '{file_path.name}' enthält kein valides Dictionary.")
            except json.JSONDecodeError:
                logging.exception(f"Sprachdatei '{file_path.name}' ist korrupt. Wird übersprungen.")
            except IOError:
                logging.exception(f"Fehler beim Laden der Sprachdatei '{file_path.name}'.")

    def get_available_languages(self) -> List[str]:
        """Gibt eine Liste aller verfügbaren Sprachen zurück."""
        hardcoded_keys = set(self._hardcoded_languages.keys())
        file_keys = set(self._file_languages.keys())
        return sorted(list(hardcoded_keys.union(file_keys)))

    def set_language(self, language_name: str) -> None:
        """
        Setzt die aktive Sprache der Anwendung.

        Priorisierung: Datei-Sprache > Hardcodierte Sprache > Fallback-Sprache.
        """
        language_name = language_name.lower()
        
        # Merge dictionaries to ensure all keys are present
        base_translations = self._hardcoded_languages.get(language_name, self._hardcoded_languages[self.FALLBACK_LANGUAGE]).copy()
        
        if language_name in self._file_languages:
            base_translations.update(self._file_languages[language_name])
            logging.info(f"Aktive Sprache auf '{language_name}' (aus Datei mit Fallback) gesetzt.")
        elif language_name in self._hardcoded_languages:
            logging.info(f"Aktive Sprache auf '{language_name}' (hardcoded) gesetzt.")
        else:
            language_name = self.FALLBACK_LANGUAGE
            logging.warning(f"Sprache '{language_name}' nicht gefunden, verwende '{self.FALLBACK_LANGUAGE}'.")

        self.translations = base_translations
        self.current_language = language_name

    def translate(self, key: str, **kwargs: Any) -> str:
        """
        Gibt den übersetzten Text für einen Schlüssel zurück. Greift bei
        Fehlschlägen auf die Fallback-Sprache und dann auf den Schlüssel selbst zurück.
        """
        # 1. Versuche, aus der aktuellen Sprache zu übersetzen
        text = self.translations.get(key)
        
        # 2. Wenn nicht erfolgreich, versuche Fallback-Sprache
        if text is None:
            fallback_dict = self._hardcoded_languages[self.FALLBACK_LANGUAGE]
            text = fallback_dict.get(key)
            if text is None:
                logging.warning(f"Übersetzungsschlüssel '{key}' weder in '{self.current_language}' noch im Fallback '{self.FALLBACK_LANGUAGE}' gefunden.")
                return key  # 3. Letzter Ausweg: Schlüssel selbst zurückgeben

        # Formatierung anwenden
        if kwargs:
            try:
                return text.format(**kwargs)
            except (KeyError, IndexError):
                logging.error(f"Fehler beim Formatieren des Texts für Schlüssel '{key}'. Originaltext wird zurückgegeben.")
        
        return text