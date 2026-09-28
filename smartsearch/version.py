"""Die Versionsnummer - an genau EINER Stelle.

Bei jedem Release von Hand hochzaehlen. Alles andere liest sie von hier:
die Updatepruefung, das Einstellungsfenster, die Rueckmelde-E-Mail, beide
Bau-Dateien (bauen/mac/SmartSearch.spec, bauen/windows/SmartSearch.spec)
und build.sh. Frueher stand sie in gui.py und wurde von dort per Suchmuster
herausgelesen; bis Fassung 1.0.2 stand im Info.plist deshalb durchgehend
"1.0.1", weil sie an einer zweiten Stelle gepflegt wurde.
"""

APP_VERSION = "1.0.6"
