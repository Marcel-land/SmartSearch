# Neue Fassung herausbringen

Stand: 27.09.2026. Bisher nur für den Mac, Windows folgt.

## Reihenfolge

1. **Versionsnummer** in `smartsearch/version.py` hochsetzen, sonst nirgends.
2. **Versionsnummer auf der Website:** `index.html`, `en/index.html`, `danke.html`, `en/danke.html` und `version.json`, dazu ein Eintrag in `aenderungen.html` und `news.html`. Die Website liegt nicht in diesem Repository.
3. **Bauen:** `bauen/mac/BUILD STARTEN.command` doppelklicken. Das Ergebnis liegt in `dist/`, das DMG im Projektordner.
4. **Prüfen:** `bauen/mac/BUNDLE PRUEFEN.command`, danach auf einem zweiten Mac testen.
5. **Committen und pushen:** über Pull Request auf `main`, siehe README.
6. **Release auf GitHub** anlegen:
   - Tag `vX.Y.Z`, Ziel `main`.
   - Das DMG muss **exakt `SmartSearch.dmg`** heißen. Der Downloadknopf der Website leitet auf `…/releases/latest/download/SmartSearch.dmg` weiter, bei einem anderen Namen läuft er ins Leere.
7. **Website hochladen:** `cd ~/Projekt/SmartSearch/Webseite && npx wrangler@latest pages deploy website --project-name=smartsearch`. Die Website liegt neben dem App-Ordner, nicht im Repository.
8. **Kontrollieren:** Die Website mit angehängtem `?x=1` aufrufen. Ohne das zeigt der Browser eine zwischengespeicherte Fassung.

## Updateprüfung

Die App fragt `api.github.com/repos/smartsearch-app/SmartSearch/releases/latest` ab und vergleicht `tag_name` mit `version.APP_VERSION` (siehe `kern/updates.py`). Deshalb muss das Tag die Form `v1.2.3` haben.

Zum Testen des Hinweisfensters ohne neues Release:

```
venv/bin/python -m tests.test_update_hinweis
```
