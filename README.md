# SmartSearch

Lokale Dateisuche für Mac und Windows: findet Dokumente nach ihrem **Inhalt**, nicht nach dem Dateinamen. Alles läuft auf dem eigenen Rechner, ohne Konto und ohne Cloud.

Website: [smartsearch-app.com](https://smartsearch-app.com). Die Website selbst liegt **nicht** in diesem Repository.

## Einrichten

Es braucht **Python 3.13**. Warum genau diese Fassung, steht in `requirements.txt`.

**Mac**

```
python3.13 -m venv venv
venv/bin/python -m pip install -r requirements.txt
```

**Windows**

```
py -3.13 -m venv venv
venv\Scripts\python -m pip install -r requirements.txt
```

Danach einmal das Suchmodell holen (rund 100 MB, liegt nicht im Repository):

```
venv/bin/python -m werkzeuge.modell_holen
```

Unter Windows `venv\Scripts\python -m werkzeuge.modell_holen`. Die fertige App bringt das Modell mit, Nutzer laden nichts herunter.

## Starten

Immer im Projektordner:

| | Mac | Windows |
|---|---|---|
| Programm | `venv/bin/python -m smartsearch` | `venv\Scripts\python -m smartsearch` |
| Wortformen-Test (1 Sekunde) | `venv/bin/python -m tests.test_wortformen` | `venv\Scripts\python -m tests.test_wortformen` |
| Suchqualität messen | `venv/bin/python -m werkzeuge.such_diagnose --testdokumente` | `venv\Scripts\python -m werkzeuge.such_diagnose --testdokumente` |
| Index untersuchen | `venv/bin/python -m werkzeuge.diagnose` | `venv\Scripts\python -m werkzeuge.diagnose` |

Wichtig ist das `-m`. `python smartsearch/start.py` oder `python tests/test_wortformen.py` findet die eigenen Module nicht.

## Wo was liegt

```
smartsearch/              das Programm
├── __main__.py           Startpunkt
├── start.py              Programmstart, nur eine laufende Kopie, Selbsttest
├── version.py            die Versionsnummer, an genau einer Stelle
├── kern/                 GEMEINSAM für alle Systeme, ohne Oberfläche
│   ├── suche.py            Anfrage bewerten, ähnliche Dokumente
│   ├── sprache.py          Suchwörter, deutsche Wortformen, Fundstellen
│   ├── index.py            index.pkl lesen/schreiben/aufräumen
│   ├── indexierung.py      Dateien einlesen, kompletter Indexlauf
│   ├── modell.py           Suchmodell (ONNX) laden
│   ├── dateien.py          Dateien finden, Text auslesen
│   ├── ocr.py              Texterkennung für Scans
│   ├── einstellungen.py    config.json, Favoriten, Suchverlauf
│   ├── ordner.py           Ordner hinzufügen/entfernen
│   ├── ueberwachung.py     Ordner beobachten (watchdog)
│   ├── updates.py          neue Fassung auf GitHub?
│   ├── rueckmeldung.py     Bitte um Rückmeldung, E-Mail-Text
│   ├── einzelinstanz.py    nur eine laufende Kopie
│   └── pfade.py            wo Daten und Symbole liegen
├── oberflaeche/          GEMEINSAM: Fenster, Texte, Farben
│   ├── hauptfenster.py
│   ├── trefferkarte.py
│   ├── dialoge/            Einstellungen, Einführung, Ordner, Fehlerliste, Hinweise
│   ├── i18n.py             alle Texte, Deutsch und Englisch
│   └── farben.py
└── plattform/            UNTERSCHIEDLICH je System
    ├── mac.py
    ├── windows.py
    └── andere.py           nur zum Testen unter Linux
ressourcen/icons/         Programmsymbole
bauen/mac/                Spec, build.sh, Doppelklick-Helfer
bauen/windows/            Spec (später WiX-Installer)
werkzeuge/                Diagnose-Skripte
tests/                    Tests und Testdokumente
docs/                     ARCHITEKTUR.md, RELEASE.md, TESTANLEITUNG.md
```

Wie die Teile zusammenhängen und welche Regeln gelten, steht in [docs/ARCHITEKTUR.md](docs/ARCHITEKTUR.md).

## Zusammenarbeit

Marcel arbeitet am Mac-Teil, sein Kollege am Windows-Teil. Beide arbeiten im selben Repository und am selben Code.

1. `main` ist immer lauffähig. Direkt auf `main` wird nicht gearbeitet.
2. Für jede Aufgabe gibt es einen eigenen, kurzen Zweig:
   ```
   git switch main
   git pull
   git switch -c windows-infobereich
   ```
3. Arbeiten, committen und hochladen:
   ```
   git push -u origin windows-infobereich
   ```
4. Auf GitHub einen **Pull Request** nach `main` stellen. Der andere schaut kurz drüber, dann wird zusammengeführt.
5. Danach bei beiden: `git switch main && git pull`.

Was jeder anfasst:

| Arbeit an … | Dateien |
|---|---|
| Windows | `smartsearch/plattform/windows.py`, `bauen/windows/` |
| Mac | `smartsearch/plattform/mac.py`, `bauen/mac/` |
| beide Systeme | `smartsearch/kern/`, `smartsearch/oberflaeche/` |

Bei den gemeinsamen Dateien vorher kurz absprechen, wer woran sitzt.

Wie eine neue Fassung herausgegeben wird, steht in [docs/RELEASE.md](docs/RELEASE.md).
