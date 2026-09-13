#!/usr/bin/env python3
"""
i18n.py - Übersetzungsmodul für SmartSearch (Deutsch / Englisch).

Funktionsweise:
- Alle Nutzer-sichtbaren Texte liegen hier als Key -> Text in
  TRANSLATIONS["de"] bzw. TRANSLATIONS["en"]. gui.py referenziert nur noch
  t("irgendein.key", ...), nie mehr feste deutsche Strings direkt im
  Widget-Code (interne print()-Meldungen/Kommentare/Docstrings sind davon
  ausgenommen - die sieht nie ein Nutzer, nur du beim Debuggen).
- Die Sprache wird EINMAL beim Programmstart ermittelt:
    1. Manuelle Auswahl aus config.json ("sprache": "de"/"en"), falls
       vorhanden - hat immer Vorrang vor der Systemsprache.
    2. Sonst: Systemsprache des Mac über NSLocale.preferredLanguages()
       (zuverlässiger als Pythons eingebautes locale-Modul, gerade in
       einer gebauten .app).
    3. Fallback: Deutsch.
- Ein Sprachwechsel im Preferences-Fenster (siehe gui.py, Tab "Allgemein")
  schreibt nur die Auswahl nach config.json und wird erst nach einem
  Neustart der App wirksam - bewusst so gehalten, statt im laufenden
  Betrieb jedes einzelne Widget live umzubeschriften, was bei der Menge an
  Widgets sehr fehleranfällig wäre.
"""

import os
import json

try:
    from AppKit import NSLocale
    _NSLOCALE_VERFUEGBAR = True
except ImportError:
    _NSLOCALE_VERFUEGBAR = False

UNTERSTUETZTE_SPRACHEN = ("de", "en")
# Gleiche Ablage wie search.py - siehe pfade.py.
from pfade import CONFIG_FILE  # noqa: F401


def _lade_gespeicherte_sprache():
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
            sprache = config.get("sprache")
            if sprache in UNTERSTUETZTE_SPRACHEN:
                return sprache
    except Exception:
        pass
    return None


def _erkenne_systemsprache():
    if _NSLOCALE_VERFUEGBAR:
        try:
            for code in NSLocale.preferredLanguages():
                kurz = str(code)[:2].lower()
                if kurz in UNTERSTUETZTE_SPRACHEN:
                    return kurz
        except Exception:
            pass
    return "de"


def _ermittle_startsprache():
    return _lade_gespeicherte_sprache() or _erkenne_systemsprache()


# Einmal beim Import ermittelt - siehe Modul-Docstring, warum ein
# Sprachwechsel zur Laufzeit bewusst einen Neustart braucht.
SPRACHE = _ermittle_startsprache()


def aktuelle_sprache():
    return SPRACHE


def setze_sprache(code):
    """Speichert die Sprachwahl dauerhaft in config.json. Wird erst nach
    einem Neustart der App wirksam (SPRACHE oben wird nur beim Modul-Import
    einmal ermittelt)."""
    if code not in UNTERSTUETZTE_SPRACHEN:
        return
    try:
        config = {}
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                config = json.load(f)
        config["sprache"] = code
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
    except Exception:
        pass


def t(key, **kwargs):
    """Liefert den übersetzten Text zu 'key' in der aktuell aktiven Sprache.
    Platzhalter (z.B. {anzahl}) werden über **kwargs befüllt. Fehlt ein Key
    in der aktiven Sprache, wird auf Deutsch zurückgefallen; fehlt er dort
    auch, wird der Key selbst zurückgegeben (auffälliger als ein Absturz,
    falls doch mal eine Übersetzung vergessen wurde)."""
    text = TRANSLATIONS.get(SPRACHE, {}).get(key)
    if text is None:
        text = TRANSLATIONS["de"].get(key, key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text


TRANSLATIONS = {
    "de": {
        # ------------------------------------------------------------------
        # Grundsatz fuer alle Texte in dieser Datei:
        # Sachlich, per Sie, ohne Ausrufezeichen und ohne Symbole in
        # Beschriftungen. Schaltflaechen benennen die Handlung ("Ordner
        # hinzufuegen"), Statusmeldungen berichten einen Zustand
        # ("Index aktualisiert") - sie kommentieren ihn nicht.
        # ------------------------------------------------------------------

        # Seitenleiste
        "sidebar.title": "Aktionen",
        "sidebar.appearance": "Darstellung",
        "sidebar.theme_system": "System",
        "sidebar.theme_light": "Hell",
        "sidebar.theme_dark": "Dunkel",
        "sidebar.quit": "Beenden",
        "sidebar.favorites": "Favoriten",
        "sidebar.add_folder": "Ordner hinzufügen",
        "sidebar.manage_folders": "Ordner verwalten",
        "sidebar.update_index": "Index aktualisieren",
        "sidebar.settings": "Einstellungen …",
        "sidebar.errors_button": "{anzahl} Dateien ohne Text",

        # Suchbereich
        "search.placeholder": "Wonach suchen Sie?",
        "search.button": "Suchen",
        "filter.all_time": "Alle Zeiträume",
        "filter.7_days": "Letzte 7 Tage",
        "filter.this_month": "Dieser Monat",
        "filter.this_year": "Dieses Jahr",
        "welcome.text": "Bereit.\n\nGeben Sie oben ein, wonach Sie suchen.",
        "status.ready": "Bereit",
        "cancel": "Abbrechen",

        # Statusmeldungen
        "status.autoreindex_started": "Änderung erkannt, Index wird aktualisiert",
        "status.autostart_enabled": "Start mit dem Mac aktiviert",
        "status.autostart_disabled": "Start mit dem Mac deaktiviert",
        "status.autostart_error": "Start mit dem Mac konnte nicht eingerichtet werden: {fehler}",
        "status.no_favorites": "Keine Favoriten vorhanden",

        # Trefferkarte
        "card.similar": "Ähnliche",
        "card.preview": "Vorschau",
        "card.finder": "Im Finder",
        "card.open": "Öffnen",
        "similar.query_prefix": "Ähnlich zu: {name}",
        "similar.status_searching": "Ähnliche Dokumente werden gesucht",
        "similar.status_no_vector": "Für diese Datei liegen keine Suchdaten vor. Sie konnte vermutlich nicht gelesen werden.",

        # Indexierung
        "index.status_already_running": "Die Indexierung läuft bereits",
        "index.status_need_folder": "Fügen Sie zunächst einen Ordner hinzu",
        "index.status_starting": "Indexierung gestartet. Sie können bereits suchen.",
        "index.status_cancelling": "Indexierung wird abgebrochen",
        "index.status_done": "Index aktualisiert",
        "index.status_cancelled": "Indexierung abgebrochen",
        "index.status_error": "Die Indexierung ist fehlgeschlagen: {fehler}",
        "index.notification_title": "SmartSearch",
        "index.notification_body": "Die Indexierung ist abgeschlossen.",
        "index.progress_indexing": "Indexiere {n} von {gesamt}: {name} – noch etwa {zeit}",
        "index.progress_calculating": "{text} – noch etwa {zeit}",

        # Nicht lesbare Dateien
        "errors.dialog_title": "Dateien ohne durchsuchbaren Text",
        "errors.dialog_heading": "Aus {anzahl} Dateien ließ sich kein Text gewinnen",
        "errors.dialog_reason": "Das ist meist kein Fehler. Häufig handelt es sich um reine Bilddateien —\nein eingescanntes Foto oder eine Grafik enthält keinen Text, der sich\ndurchsuchen ließe.\n\nSeltenere Ursachen: ein beschädigtes PDF, ein abgebrochener Download,\noder ein Ordner, für den macOS den Zugriff verweigert.",
        "errors.retry_button": "Bei der nächsten Indexierung erneut versuchen",
        "errors.close_button": "Schließen",
        "errors.retry_status": "{anzahl} Dateien werden bei der nächsten Indexierung erneut gelesen",

        # Suche
        "search.status_searching": "Suche läuft",
        "search.status_error": "Die Suche ist fehlgeschlagen: {fehler}",
        "search.status_no_index": "Kein Index vorhanden. Aktualisieren Sie zunächst den Index.",
        "search.status_no_results": "Keine Treffer",
        "search.status_results_loaded": "{anzahl} Treffer",
        "results.none_no_folder": "Es wurde noch kein Ordner hinzugefügt.\n\nWählen Sie links »Ordner hinzufügen«, um festzulegen, was durchsucht werden soll.",
        "results.none_filtered": "Keine Treffer für »{anfrage}« mit den gesetzten Filtern.\n\nMöglicherweise ist der Dateityp des gesuchten Dokuments oben abgewählt.",
        "results.none_never_indexed": "Es wurde noch nicht indexiert.\n\nWählen Sie links »Index aktualisieren«, um die Ordner einzulesen.",
        "results.none_generic": "Keine Treffer für »{anfrage}«.\n\nMögliche Ursachen: Die Datei liegt in keinem der überwachten Ordner, sie wurde noch nicht indexiert, oder ihr Format wird nicht unterstützt.",

        # Ordnerverwaltung
        "folders.dialog_title": "Durchsuchte Ordner",
        "folders.heading": "Durchsuchte Ordner",
        "folders.empty": "Es wurde noch kein Ordner hinzugefügt.",
        "folders.remove_confirm_title": "Ordner entfernen",
        "folders.remove_confirm_body": "Soll dieser Ordner nicht mehr durchsucht werden?\n\n{pfad}\n\nBereits indexierte Inhalte bleiben bis zur nächsten Aktualisierung erhalten.",
        "folders.remove_button": "Entfernen",
        "folders.add_button": "Ordner hinzufügen",
        "folders.close_button": "Schließen",
        "folders.picker_title": "Ordner auswählen",
        "folders.status_added": "Hinzugefügt: {ordner}",

        # Einstellungen
        "settings.window_title": "Einstellungen",
        "settings.tab_general": "Allgemein",
        "settings.tab_help": "Hilfe",
        "settings.tab_backup": "Sicherung",
        "settings.tab_privacy": "Datenschutz",
        "settings.autostart_checkbox": "SmartSearch mit dem Mac starten",
        "settings.version_label": "Version {version}",
        "settings.check_updates_button": "Nach Updates suchen",
        "settings.language_label": "Sprache",

        # Sicherung
        "backup.description": "Sichert die durchsuchten Ordner und Favoriten in einer Datei –\nfür ein Backup oder für die Einrichtung auf einem weiteren Mac.",
        "backup.export_button": "Einstellungen sichern",
        "backup.import_button": "Einstellungen wiederherstellen",
        "backup.export_title": "Einstellungen sichern",
        "backup.export_status": "Einstellungen gesichert: {name}",
        "backup.export_error": "Die Sicherung ist fehlgeschlagen: {fehler}",
        "backup.import_title": "Einstellungen wiederherstellen",
        "backup.import_filetype": "JSON-Datei",
        "backup.import_status": "Wiederhergestellt: {ordner} Ordner, {favoriten} Favoriten. Aktualisieren Sie nun den Index.",
        "backup.import_error": "Die Wiederherstellung ist fehlgeschlagen: {fehler}",

        # Ersteinrichtung: Suchmodell
        "model.download_start": "Suchmodell wird geladen – einmalig, etwa 2,3 GB",
        "model.download_progress": "Suchmodell wird geladen: {geladen} von {gesamt}",
        "model.download_failed_status": "Das Suchmodell konnte nicht geladen werden",
        "model.download_failed_title": "Keine Verbindung",
        "model.download_failed_heading": "Das Suchmodell fehlt noch",
        "model.download_failed_body": "Beim ersten Start lädt SmartSearch einmalig das Suchmodell herunter, etwa 2,3 GB. Dafür wird eine Internetverbindung benötigt. Anschließend arbeitet das Programm dauerhaft ohne Verbindung.\n\nPrüfen Sie Ihre Verbindung und versuchen Sie es erneut. Bereits geladene Teile bleiben erhalten.",
        "model.download_failed_details": "Meldung: {fehler}",
        "model.download_failed_retry": "Erneut versuchen",
        "model.download_failed_close": "Später",
        "model.incomplete_status": "Der Programmteil für die Suche fehlt",
        "model.incomplete_title": "Programm unvollständig",
        "model.incomplete_heading": "Ein Programmteil fehlt",
        "model.incomplete_body": "Dieser Fassung von SmartSearch fehlt ein Bestandteil, der beim Erstellen des Programms hätte mitgeliefert werden müssen. An Ihrer Internetverbindung oder Ihrem Mac liegt es nicht, und ein erneuter Versuch führt zum selben Ergebnis.\n\nBitte laden Sie die aktuelle Fassung herunter. Ist der Fehler dort noch vorhanden, melden Sie ihn bitte mit der Meldung unten.",
        "model.incomplete_report": "Fehler melden",

        # Texterkennung
        "help.ocr_heading": "Eingescannte Dokumente",
        "help.ocr_available": "Texterkennung aktiv über {engine}. Eingescannte PDF-Dateien werden mit durchsucht.",
        "help.ocr_missing": "Auf diesem Mac steht keine Texterkennung zur Verfügung. Eingescannte PDF-Dateien werden übersprungen, alle übrigen Formate normal durchsucht.",

        # Rückmeldung und fehlende Berechtigungen
        "help.feedback_heading": "Etwas funktioniert nicht?",
        "help.feedback_text": "Schildern Sie kurz, was Sie erwartet haben und was stattdessen geschah. Version und Systemangaben werden automatisch eingetragen — Dateinamen oder Inhalte werden nicht übermittelt.",
        "help.feedback_button": "Rückmeldung schreiben",
        "help.feedback_failed": "Das E-Mail-Programm ließ sich nicht öffnen. Schreiben Sie stattdessen an {adresse}",
        "feedback.bar_text": "Kommen Sie mit SmartSearch zurecht? Eine kurze Rückmeldung hilft mir sehr.",
        "feedback.bar_button": "Rückmeldung schreiben",
        "feedback.bar_later": "Nicht jetzt",
        "permission.status": "{anzahl} Ordner ohne Zugriffsberechtigung",
        "permission.dialog_title": "Zugriff verweigert",
        "permission.dialog_heading": "macOS erlaubt den Zugriff auf {anzahl} Ordner nicht",
        "permission.dialog_body": "Diese Ordner konnten nicht gelesen werden. macOS schützt bestimmte Bereiche und fragt normalerweise einmal nach Erlaubnis.\n\nÖffnen Sie Systemeinstellungen › Datenschutz & Sicherheit › Festplattenvollzugriff und setzen Sie dort den Haken bei SmartSearch. Danach genügt ein Klick auf »Index aktualisieren«.",
        "permission.open_settings": "Systemeinstellungen öffnen",

        # Hilfe
        "help.guide_heading": "Einführung",
        "help.guide_text": "Zeigt die Einführung erneut: Suchprinzip, Funktionsumfang, Umgang mit Ihren Daten und Bedienung.",
        "help.guide_button": "Einführung anzeigen",
        "help.trouble_heading": "Wenn nichts gefunden wird",
        "help.trouble_text": "Prüfen Sie der Reihe nach:\n\nIst der betreffende Ordner unter »Ordner verwalten« eingetragen?\nIst die Indexierung abgeschlossen? Der Stand steht unten im Hauptfenster.\nIst der Dateityp in der Filterleiste möglicherweise abgewählt?\n\nGelesen werden PDF, Word, Excel, PowerPoint, Text- und Markdown-Dateien.",

        # Datenschutz
        "privacy.heading": "Ihre Daten bleiben auf Ihrem Mac",
        "privacy.intro": "In durchsuchten Ordnern liegen häufig vertrauliche Unterlagen – Verträge,\nRechnungen, Ausweiskopien. Deshalb im Einzelnen, was mit ihnen geschieht:",
        "privacy.section1_title": "Keine Datei verlässt diesen Mac.",
        "privacy.section1_text": "Jede Datei wird lokal gelesen und lokal durchsucht. Es findet keine Übertragung an einen Server statt.",
        "privacy.section2_title": "Auch die Auswertung erfolgt lokal.",
        "privacy.section2_text": "Das Modell, das Ihre Suchanfragen auswertet, arbeitet vollständig offline auf diesem Mac. Es besteht keine Verbindung, über die Inhalte abfließen könnten.",
        "privacy.section3_title": "Eine Verbindung wird nur einmal benötigt.",
        "privacy.section3_text": "Beim ersten Start wird das Suchmodell heruntergeladen, etwa 2,3 GB. Übertragen wird ausschließlich dieses Modell, keine Dokumente. Danach arbeitet SmartSearch ohne Internetverbindung.",
        "privacy.section4_title": "Der Index bleibt in Ihrer Hand.",
        "privacy.section4_text": "Er liegt als gewöhnliche Datei in Ihrem Benutzerordner und lässt sich jederzeit einsehen oder löschen.",
        "privacy.closing": "SmartSearch sieht Ihre Dateien für Sie durch – und sonst niemand.",

        # ------------------------------------------------------------------
        # Einführung (fünf Schritte)
        # ------------------------------------------------------------------
        "guide.title": "SmartSearch",
        "guide.step_label": "{n} von {gesamt}",
        "guide.back": "Zurück",
        "guide.next": "Weiter",
        "guide.skip": "Überspringen",
        "guide.finish": "Fertig",

        # Schritt 1 – Suchprinzip
        "guide.s1_heading": "Suche nach Inhalten, nicht nach Dateinamen",
        "guide.s1_text": "Die Dateisuche des Systems vergleicht Zeichenketten. SmartSearch wertet\naus, worum es in einem Dokument geht. Sie beschreiben den Inhalt, der\nDateiname spielt keine Rolle.",
        "guide.s1_examples_title": "Beispiele",
        "guide.s1_ex1_query": "Rechnung Autowerkstatt",
        "guide.s1_ex1_hit": "findet  scan_2024_11.pdf",
        "guide.s1_ex2_query": "Kündigung Mobilfunkvertrag",
        "guide.s1_ex2_hit": "findet  Schreiben_final_v3.docx",
        "guide.s1_ex3_query": "Notizen zur Budgetbesprechung",
        "guide.s1_ex3_hit": "findet  Meeting 14.03..md",
        "guide.s1_footer": "Ergänzend läuft eine klassische Stichwortsuche mit, sodass auch exakte\nBegriffe, Namen und Nummern zuverlässig gefunden werden.",

        # Schritt 2 – Funktionsumfang
        "guide.s2_heading": "Funktionsumfang",
        "guide.s2_text": "Ein Überblick über das, was Ihnen zur Verfügung steht.",
        "guide.s2_g1_title": "Suche",
        "guide.s2_g1_items": "Inhaltliche Suche, kombiniert mit Stichwortsuche\nÄhnliche Dokumente zu einem Treffer\nFilter nach Dateityp und Zeitraum\nVerlauf der letzten Suchanfragen\nHervorgehobene Fundstellen in der Trefferliste",
        "guide.s2_g2_title": "Unterstützte Formate",
        "guide.s2_g2_items": "PDF, Word, Excel, PowerPoint\nText- und Markdown-Dateien\nEingescannte PDF-Dateien über Texterkennung",
        "guide.s2_g3_title": "Umgang mit Treffern",
        "guide.s2_g3_items": "Öffnen per Doppelklick\nVorschau ohne Öffnen der Anwendung\nAnzeigen im Finder\nFavoriten für wiederkehrende Dokumente",
        "guide.s2_g4_title": "Index",
        "guide.s2_g4_items": "Beliebig viele Ordner gleichzeitig\nAutomatische Aktualisierung bei Änderungen\nParallele Verarbeitung, Suche bleibt möglich\nÜbersicht nicht lesbarer Dateien",
        "guide.s2_g5_title": "Programm",
        "guide.s2_g5_items": "Aufruf mit Befehl-Umschalt-F aus jeder Anwendung\nStart mit dem Mac\nHelle und dunkle Darstellung\nDeutsch und Englisch\nSicherung und Wiederherstellung der Einstellungen",

        # Schritt 3 – Datenschutz
        "guide.s3_heading": "Ihre Daten bleiben auf Ihrem Mac",
        "guide.s3_text": "In durchsuchten Ordnern liegen häufig vertrauliche Unterlagen. Deshalb\nim Einzelnen, was mit ihnen geschieht:",
        "guide.s3_point1": "Jede Datei wird lokal gelesen. Es findet keine Übertragung an einen Server statt.",
        "guide.s3_point2": "Auch die Auswertung erfolgt lokal. Es besteht keine Verbindung, über die Inhalte abfließen könnten.",
        "guide.s3_point3": "Der Index liegt als gewöhnliche Datei in Ihrem Benutzerordner und lässt sich jederzeit löschen.",
        "guide.s3_download_title": "Einmalige Vorbereitung",
        "guide.s3_download_text": "Beim ersten Start wird das Suchmodell heruntergeladen, etwa 2,3 GB. Je nach\nVerbindung dauert das einige Minuten. Übertragen wird ausschließlich dieses\nModell, keine Dokumente. Danach arbeitet SmartSearch ohne Internetverbindung.",

        # Schritt 4 – Ordner
        "guide.s4_heading": "Zu durchsuchende Ordner",
        "guide.s4_text": "Beginnen Sie mit wenigen Ordnern. Weitere lassen sich jederzeit ergänzen.\nUmfangreiche Ordner benötigen beim ersten Einlesen entsprechend Zeit.",

        # Schritt 5 – Bedienung
        "guide.s5_heading": "Zur Bedienung",
        "guide.s5_text": "Die Ordner werden nun einmalig eingelesen. Der Fortschritt wird im\nHauptfenster angezeigt; suchen können Sie bereits währenddessen.",
        "guide.s5_tips_title": "Drei Hinweise für die tägliche Arbeit",
        "guide.s5_tip1": "Formulieren Sie ganze Sätze. »Wo war der Vertrag mit der langen Kündigungsfrist?« liefert bessere Ergebnisse als ein einzelnes Stichwort.",
        "guide.s5_tip2": "Befehl-Umschalt-F öffnet SmartSearch aus jeder Anwendung heraus, ohne den Arbeitsablauf zu unterbrechen.",
        "guide.s5_tip3": "Neue und geänderte Dateien werden selbsttätig nachgelesen. Ein manuelles Aktualisieren ist nur nach dem Hinzufügen eines Ordners nötig.",
        "guide.s5_footer": "Die Einführung finden Sie jederzeit unter Einstellungen › Hilfe.",

        # Ordnerauswahl (auch im Guide verwendet)
        "onboarding.title": "SmartSearch einrichten",
        "onboarding.heading": "Willkommen bei SmartSearch",
        "onboarding.subtitle": "Wählen Sie, welche Ordner durchsucht werden sollen.",
        "onboarding.documents": "Dokumente",
        "onboarding.downloads": "Downloads",
        "onboarding.desktop": "Schreibtisch",
        "onboarding.add_folder_button": "Weiteren Ordner wählen …",
        "onboarding.picker_title": "Ordner hinzufügen",
        "onboarding.extra_prefix": "Zusätzlich ausgewählt:\n",
        "onboarding.skip": "Überspringen",
        "onboarding.start": "Fertig",
        "onboarding.status_none_selected": "Kein Ordner ausgewählt. Sie können jederzeit über »Ordner hinzufügen« beginnen.",
        "onboarding.status_skipped": "Einrichtung übersprungen. Fügen Sie bei Bedarf über »Ordner hinzufügen« einen Ordner hinzu.",

        # Updates
        "index.rebuild_title": "Suchindex wird neu aufgebaut",
        "index.rebuild_body": "Das Suchmodell hat sich mit dieser Fassung geändert. Der gespeicherte Index passt nicht mehr dazu und wird jetzt neu aufgebaut.\n\nSie können SmartSearch währenddessen weiter benutzen - bis der Aufbau durch ist, findet die Suche allerdings noch nicht alles.",
        "update.check_failed_title": "Update-Prüfung nicht möglich",
        "update.check_failed_body": "Es konnte nicht nach Updates gesucht werden.\n\nMöglich ist eine fehlende Internetverbindung, aber ebenso eine Störung auf unserer Seite. SmartSearch selbst arbeitet unabhängig davon normal weiter.\n\nMeldung: {fehler}",
        "update.up_to_date_title": "Keine neue Version",
        "update.up_to_date_body": "Sie verwenden bereits die aktuelle Version {version}.",
        "update.available_title": "Update verfügbar",
        "update.available_heading": "Version {version} steht bereit",
        "update.available_current": "Installiert ist derzeit Version {version}.",
        "update.later_button": "Später",
        "update.download_button": "Herunterladen",
    },
    "en": {
        # Same principle as the German section: plain, factual wording, no
        # exclamation marks, no symbols inside labels.

        # Sidebar
        "sidebar.title": "Actions",
        "sidebar.appearance": "Appearance",
        "sidebar.theme_system": "System",
        "sidebar.theme_light": "Light",
        "sidebar.theme_dark": "Dark",
        "sidebar.quit": "Quit",
        "sidebar.favorites": "Favorites",
        "sidebar.add_folder": "Add folder",
        "sidebar.manage_folders": "Manage folders",
        "sidebar.update_index": "Update index",
        "sidebar.settings": "Preferences …",
        "sidebar.errors_button": "{anzahl} files without text",

        # Search area
        "search.placeholder": "What are you looking for?",
        "search.button": "Search",
        "filter.all_time": "All dates",
        "filter.7_days": "Last 7 days",
        "filter.this_month": "This month",
        "filter.this_year": "This year",
        "welcome.text": "Ready.\n\nEnter above what you are looking for.",
        "status.ready": "Ready",
        "cancel": "Cancel",

        # Status messages
        "status.autoreindex_started": "Change detected, index is being updated",
        "status.autostart_enabled": "Start with Mac enabled",
        "status.autostart_disabled": "Start with Mac disabled",
        "status.autostart_error": "Start with Mac could not be configured: {fehler}",
        "status.no_favorites": "No favorites saved",

        # Result card
        "card.similar": "Similar",
        "card.preview": "Preview",
        "card.finder": "In Finder",
        "card.open": "Open",
        "similar.query_prefix": "Similar to: {name}",
        "similar.status_searching": "Searching for similar documents",
        "similar.status_no_vector": "No search data available for this file. It could probably not be read.",

        # Indexing
        "index.status_already_running": "Indexing is already running",
        "index.status_need_folder": "Add a folder first",
        "index.status_starting": "Indexing started. You can already search.",
        "index.status_cancelling": "Cancelling indexing",
        "index.status_done": "Index updated",
        "index.status_cancelled": "Indexing cancelled",
        "index.status_error": "Indexing failed: {fehler}",
        "index.notification_title": "SmartSearch",
        "index.notification_body": "Indexing has finished.",
        "index.progress_indexing": "Indexing {n} of {gesamt}: {name} – about {zeit} left",
        "index.progress_calculating": "{text} – about {zeit} left",

        # Unreadable files
        "errors.dialog_title": "Files without searchable text",
        "errors.dialog_heading": "No text could be extracted from {anzahl} files",
        "errors.dialog_reason": "This is usually not an error. Most often these are pure image files —\na scanned photo or a graphic contains no text that could be searched.\n\nRarer causes: a damaged PDF, an incomplete download, or a folder for\nwhich macOS denies access.",
        "errors.retry_button": "Retry during the next indexing run",
        "errors.close_button": "Close",
        "errors.retry_status": "{anzahl} files will be read again during the next indexing run",

        # Search
        "search.status_searching": "Searching",
        "search.status_error": "The search failed: {fehler}",
        "search.status_no_index": "No index available. Update the index first.",
        "search.status_no_results": "No results",
        "search.status_results_loaded": "{anzahl} results",
        "results.none_no_folder": "No folder has been added yet.\n\nChoose “Add folder” on the left to define what should be searched.",
        "results.none_filtered": "No results for “{anfrage}” with the current filters.\n\nThe file type you are looking for may be deselected above.",
        "results.none_never_indexed": "Nothing has been indexed yet.\n\nChoose “Update index” on the left to read in your folders.",
        "results.none_generic": "No results for “{anfrage}”.\n\nPossible reasons: the file is not in any of the monitored folders, it has not been indexed yet, or its format is not supported.",

        # Folder management
        "folders.dialog_title": "Searched folders",
        "folders.heading": "Searched folders",
        "folders.empty": "No folder has been added yet.",
        "folders.remove_confirm_title": "Remove folder",
        "folders.remove_confirm_body": "Should this folder no longer be searched?\n\n{pfad}\n\nAlready indexed content remains until the next update.",
        "folders.remove_button": "Remove",
        "folders.add_button": "Add folder",
        "folders.close_button": "Close",
        "folders.picker_title": "Select folder",
        "folders.status_added": "Added: {ordner}",

        # Preferences
        "settings.window_title": "Preferences",
        "settings.tab_general": "General",
        "settings.tab_help": "Help",
        "settings.tab_backup": "Backup",
        "settings.tab_privacy": "Privacy",
        "settings.autostart_checkbox": "Start SmartSearch with the Mac",
        "settings.version_label": "Version {version}",
        "settings.check_updates_button": "Check for updates",
        "settings.language_label": "Language",

        # Backup
        "backup.description": "Saves the searched folders and favorites to a file –\nfor a backup or to set up another Mac.",
        "backup.export_button": "Save settings",
        "backup.import_button": "Restore settings",
        "backup.export_title": "Save settings",
        "backup.export_status": "Settings saved: {name}",
        "backup.export_error": "Saving failed: {fehler}",
        "backup.import_title": "Restore settings",
        "backup.import_filetype": "JSON file",
        "backup.import_status": "Restored: {ordner} folders, {favoriten} favorites. Update the index now.",
        "backup.import_error": "Restoring failed: {fehler}",

        # First run: search model
        "model.download_start": "Downloading search model – one time, about 2.3 GB",
        "model.download_progress": "Downloading search model: {geladen} of {gesamt}",
        "model.download_failed_status": "The search model could not be downloaded",
        "model.download_failed_title": "No connection",
        "model.download_failed_heading": "The search model is still missing",
        "model.download_failed_body": "On first launch SmartSearch downloads the search model once, about 2.3 GB. This requires an internet connection. Afterwards the application works entirely offline.\n\nCheck your connection and try again. Parts already downloaded are kept.",
        "model.download_failed_details": "Message: {fehler}",
        "model.download_failed_retry": "Try again",
        "model.download_failed_close": "Later",
        "model.incomplete_status": "A component required for searching is missing",
        "model.incomplete_title": "Incomplete installation",
        "model.incomplete_heading": "A component is missing",
        "model.incomplete_body": "This build of SmartSearch is missing a component that should have been included when the application was packaged. This is not caused by your internet connection or your Mac, and trying again will produce the same result.\n\nPlease download the current version. If the error persists there, please report it together with the message below.",
        "model.incomplete_report": "Report problem",

        # Text recognition
        "help.ocr_heading": "Scanned documents",
        "help.ocr_available": "Text recognition active via {engine}. Scanned PDF files are searched as well.",
        "help.ocr_missing": "No text recognition is available on this Mac. Scanned PDF files are skipped, all other formats are searched normally.",

        # Feedback and missing permissions
        "help.feedback_heading": "Something not working?",
        "help.feedback_text": "Briefly describe what you expected and what happened instead. Version and system details are filled in automatically — no file names or contents are transmitted.",
        "help.feedback_button": "Write feedback",
        "help.feedback_failed": "The mail application could not be opened. Please write to {adresse} instead.",
        "feedback.bar_text": "How are you getting on with SmartSearch? A short note would help me a lot.",
        "feedback.bar_button": "Write feedback",
        "feedback.bar_later": "Not now",
        "permission.status": "{anzahl} folders without access permission",
        "permission.dialog_title": "Access denied",
        "permission.dialog_heading": "macOS does not permit access to {anzahl} folders",
        "permission.dialog_body": "These folders could not be read. macOS protects certain areas and normally asks for permission once.\n\nOpen System Settings › Privacy & Security › Full Disk Access and tick the box for SmartSearch. A click on “Update index” is then enough.",
        "permission.open_settings": "Open System Settings",

        # Help
        "help.guide_heading": "Introduction",
        "help.guide_text": "Shows the introduction again: search principle, features, handling of your data, and operation.",
        "help.guide_button": "Show introduction",
        "help.trouble_heading": "If nothing is found",
        "help.trouble_text": "Check in this order:\n\nIs the folder in question listed under “Manage folders”?\nHas indexing finished? The status is shown at the bottom of the main window.\nIs the file type possibly deselected in the filter bar?\n\nSmartSearch reads PDF, Word, Excel, PowerPoint, text and Markdown files.",

        # Privacy
        "privacy.heading": "Your data stays on your Mac",
        "privacy.intro": "Searched folders often hold confidential documents – contracts, invoices,\ncopies of identification. So here is what happens to them in detail:",
        "privacy.section1_title": "No file leaves this Mac.",
        "privacy.section1_text": "Every file is read locally and searched locally. Nothing is transmitted to a server.",
        "privacy.section2_title": "Analysis is local as well.",
        "privacy.section2_text": "The model that interprets your queries runs entirely offline on this Mac. There is no connection through which content could leave.",
        "privacy.section3_title": "A connection is needed only once.",
        "privacy.section3_text": "On first launch the search model is downloaded, about 2.3 GB. Only this model is transferred, no documents. After that SmartSearch works without an internet connection.",
        "privacy.section4_title": "The index remains yours.",
        "privacy.section4_text": "It is an ordinary file in your user folder and can be inspected or deleted at any time.",
        "privacy.closing": "SmartSearch looks through your files for you – and nobody else does.",

        # Introduction (five steps)
        "guide.title": "SmartSearch",
        "guide.step_label": "{n} of {gesamt}",
        "guide.back": "Back",
        "guide.next": "Continue",
        "guide.skip": "Skip",
        "guide.finish": "Done",

        "guide.s1_heading": "Search by content, not by file name",
        "guide.s1_text": "The system's file search compares character strings. SmartSearch evaluates\nwhat a document is about. You describe the content; the file name is\nirrelevant.",
        "guide.s1_examples_title": "Examples",
        "guide.s1_ex1_query": "invoice car repair shop",
        "guide.s1_ex1_hit": "finds  scan_2024_11.pdf",
        "guide.s1_ex2_query": "cancelling my phone contract",
        "guide.s1_ex2_hit": "finds  letter_final_v3.docx",
        "guide.s1_ex3_query": "notes on the budget meeting",
        "guide.s1_ex3_hit": "finds  Meeting 14.03..md",
        "guide.s1_footer": "A conventional keyword search runs alongside, so exact terms, names and\nnumbers are found reliably as well.",

        "guide.s2_heading": "Features",
        "guide.s2_text": "An overview of what is available to you.",
        "guide.s2_g1_title": "Search",
        "guide.s2_g1_items": "Content-based search combined with keyword search\nSimilar documents for any result\nFilters by file type and time range\nHistory of recent queries\nHighlighted matches in the result list",
        "guide.s2_g2_title": "Supported formats",
        "guide.s2_g2_items": "PDF, Word, Excel, PowerPoint\nText and Markdown files\nScanned PDF files via text recognition",
        "guide.s2_g3_title": "Working with results",
        "guide.s2_g3_items": "Open with a double click\nPreview without launching the application\nReveal in Finder\nFavorites for recurring documents",
        "guide.s2_g4_title": "Index",
        "guide.s2_g4_items": "Any number of folders at once\nAutomatic updates when files change\nParallel processing, search stays available\nOverview of unreadable files",
        "guide.s2_g5_title": "Application",
        "guide.s2_g5_items": "Opens with Command-Shift-F from any application\nStarts with the Mac\nLight and dark appearance\nGerman and English\nBackup and restore of settings",

        "guide.s3_heading": "Your data stays on your Mac",
        "guide.s3_text": "Searched folders often hold confidential documents. So here is what\nhappens to them in detail:",
        "guide.s3_point1": "Every file is read locally. Nothing is transmitted to a server.",
        "guide.s3_point2": "Analysis is local as well. There is no connection through which content could leave.",
        "guide.s3_point3": "The index is an ordinary file in your user folder and can be deleted at any time.",
        "guide.s3_download_title": "One-time preparation",
        "guide.s3_download_text": "On first launch the search model is downloaded, about 2.3 GB. Depending on\nyour connection this takes a few minutes. Only this model is transferred, no\ndocuments. Afterwards SmartSearch works without an internet connection.",

        "guide.s4_heading": "Folders to be searched",
        "guide.s4_text": "Start with a few folders. More can be added at any time.\nExtensive folders require a corresponding amount of time on first reading.",

        "guide.s5_heading": "Operation",
        "guide.s5_text": "Your folders will now be read once. Progress is shown in the main window;\nyou can already search while it runs.",
        "guide.s5_tips_title": "Three notes for daily use",
        "guide.s5_tip1": "Phrase full sentences. “Where was the contract with the long notice period?” yields better results than a single keyword.",
        "guide.s5_tip2": "Command-Shift-F opens SmartSearch from any application without interrupting your work.",
        "guide.s5_tip3": "New and changed files are picked up automatically. Manual updating is only required after adding a folder.",
        "guide.s5_footer": "You can find the introduction at any time under Preferences › Help.",

        # Folder selection (also used by the guide)
        "onboarding.title": "Set up SmartSearch",
        "onboarding.heading": "Welcome to SmartSearch",
        "onboarding.subtitle": "Select which folders should be searched.",
        "onboarding.documents": "Documents",
        "onboarding.downloads": "Downloads",
        "onboarding.desktop": "Desktop",
        "onboarding.add_folder_button": "Choose another folder …",
        "onboarding.picker_title": "Add folder",
        "onboarding.extra_prefix": "Additionally selected:\n",
        "onboarding.skip": "Skip",
        "onboarding.start": "Done",
        "onboarding.status_none_selected": "No folder selected. You can start at any time via “Add folder”.",
        "onboarding.status_skipped": "Setup skipped. Add a folder via “Add folder” when needed.",

        # Updates
        "index.rebuild_title": "Rebuilding the search index",
        "index.rebuild_body": "The search model changed with this version. The stored index no longer matches it and is being rebuilt now.\n\nYou can keep using SmartSearch in the meantime - until the rebuild has finished, search will not find everything yet.",
        "update.check_failed_title": "Update check not possible",
        "update.check_failed_body": "Could not check for updates.\n\nThis may be a missing internet connection, but it may equally be a problem on our side. SmartSearch itself continues to work normally either way.\n\nMessage: {fehler}",
        "update.up_to_date_title": "No new version",
        "update.up_to_date_body": "You are already using the current version {version}.",
        "update.available_title": "Update available",
        "update.available_heading": "Version {version} is available",
        "update.available_current": "Version {version} is currently installed.",
        "update.later_button": "Later",
        "update.download_button": "Download",
    },
}
