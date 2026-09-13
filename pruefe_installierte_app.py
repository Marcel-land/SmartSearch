#!/usr/bin/env python3
"""Liest aus der INSTALLIERTEN SmartSearch.app aus, welche Update-Adresse
und welche Versionsnummer wirklich im Programm stecken.

Aufruf:  python3 pruefe_installierte_app.py
"""
import os, re, struct, sys, zlib

APP = "/Applications/SmartSearch.app"
EXE = os.path.join(APP, "Contents/MacOS/SmartSearch")

if not os.path.exists(EXE):
    sys.exit("Nicht gefunden: " + EXE)

import datetime
print("Programm:", EXE)
print("Gebaut am:", datetime.datetime.fromtimestamp(os.path.getmtime(EXE)).strftime("%d.%m.%Y %H:%M"))

plist = os.path.join(APP, "Contents/Info.plist")
if os.path.exists(plist):
    txt = open(plist, encoding="utf-8", errors="replace").read()
    m = re.search(r"CFBundleShortVersionString</key>\s*<string>([^<]*)", txt)
    print("Info.plist sagt Version:", m.group(1) if m else "?")

data = open(EXE, "rb").read()
pos = data.rfind(b"MEI\014\013\012\013\016")
if pos < 0:
    sys.exit("Kein PyInstaller-Archiv im Programm gefunden.")

_, laenge, toc, toc_len, _ = struct.unpack("!8sIIII", data[pos:pos + 24])
start = pos + 24 + 64 - laenge
td = data[start + toc: start + toc + toc_len]

p = 0
while p < len(td):
    (elen,) = struct.unpack("!i", td[p:p + 4])
    epos, dlen, _ulen, cflag, typ = struct.unpack("!IIIBc", td[p + 4:p + 18])
    name = td[p + 18:p + elen].rstrip(b"\0").decode("utf-8", "replace")
    if typ == b"s" and name == "gui":
        roh = data[start + epos: start + epos + dlen]
        if cflag:
            roh = zlib.decompress(roh)
        urls = sorted({u.decode("utf-8", "replace")
                       for u in re.findall(rb"https?://[\x20-\x7e]{5,90}", roh)
                       if b"apple.com" not in u})
        print("\n--- Adressen im Programmcode ---")
        for u in urls:
            print("   ", u)
        print("\n--- Versionsnummern im Programmcode ---")
        print("   ", sorted({v.decode() for v in re.findall(rb"\d+\.\d+\.\d+", roh)}))
        break
    p += elen
else:
    print("Hauptskript 'gui' nicht im Archiv gefunden.")
