# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

Note: SmartSearch ships as a native desktop app (Python/customtkinter for macOS, with a Windows port in progress), not a browser app. It is recorded as `web` deliberately: customtkinter draws fully custom-styled widgets rather than native AppKit/Win32 controls, so the app has web-like design freedom and no OS HIG lock-in. Future design work should treat it like a custom-rendered UI, not constrain it to native macOS/Windows conventions. Confirmed with the user during init.

## Users

Everyday, non-technical Mac users (German-speaking primary audience, English supported) who have accumulated personal paperwork as scans or PDFs — contracts, invoices, ID copies, letters — usually with meaningless auto-generated filenames (scanner/phone output like `Scan_20231114_0003.pdf`, `IMG_4471.pdf`). They remember *what* a document is about but not what it's called or where they filed it. No technical setup tolerance: no account, no configuration beyond picking folders.

## Product Purpose

SmartSearch is a local, offline, content-based document search app. Instead of matching filenames or exact strings (like macOS Spotlight/Finder search), it reads what a document is actually about and lets the user find it by describing the content in plain language. It combines semantic (meaning-based) search with classical keyword search so that both a described concept ("Rechnung über den Drucker") and an exact literal term (a model number, invoice number) can surface the same document.

Success = the user types a natural description of a remembered document and the right file appears, even when the filename and folder give no clue.

## Positioning

"Sie wissen, was drinsteht. Nur nicht mehr, wie es heißt." (You know what's in it. Just not anymore what it's called.)

Differentiator versus system search (string/filename matching) and versus cloud AI search tools: SmartSearch understands document *content* semantically, entirely on-device. No file ever leaves the Mac; no account; no server; no cloud processing. This is a hard privacy line, not just a feature — the website devotes a dedicated, explicit section to it because the document corpus (contracts, invoices, ID scans) is inherently sensitive.

## Operating Context

- Lives in the macOS menu bar (a magnifying-glass icon); invoked instantly from any app via ⌘⇧F, or a menu-bar click. Windows port uses a system-tray icon (pystray) and Ctrl+Shift+F.
- First run: short onboarding, user picks folders to index (Downloads is intentionally *not* preselected by default, since it tends to be large and would make first indexing slow).
- Initial indexing takes a few minutes and runs once; after that, new/changed files are picked up automatically in the background. Search is usable while indexing is still in progress.
- One-time ~2.3 GB download of the local embedding model (BAAI/bge-m3) on first launch — the only point at which the app needs internet, aside from occasional update checks. Fully offline afterward.
- Not notarized/signed by Apple (no paid developer account) — first launch triggers a Gatekeeper "can't be opened" warning that the user must clear manually via System Settings → Privacy & Security. This is expected and documented, not a bug signal.
- Reads: PDF, Word (.docx), Excel (.xlsx), PowerPoint (.pptx), text, and Markdown files, including scanned/image PDFs via macOS's built-in Vision OCR (no external OCR tool required).
- Files that can't be read (corrupt/empty PDFs, image-only scans with no extractable text) are surfaced by name to the user, not silently dropped.
- Index and all user data live in a plain file under `~/Library/Application Support/SmartSearch/`, viewable/deletable by the user at any time; deleting it just triggers a rebuild.
- Settings can be exported to a file and restored on another Mac.
- Bilingual UI (German default, English available); language is chosen once (manual override in Preferences, else macOS system language, else German) and takes effect after restart — deliberately not live-switched.

## Capabilities and Constraints

- Combined semantic + keyword scoring (see `search.py`): keyword hits are weighted heavily since exact terms (names, numbers) should reliably surface; semantic score fills the gap when the literal word isn't in the document at all (e.g. searching "Drucker" should find an invoice that only says "Multifunktionssystem").
- "Similar documents" — given one search hit, find other documents that are topically related, to recover a whole matter/case rather than one page of it.
- Filters: file type and time range. Query history. In-text highlighting of the matched passage. Preview without opening the source app (Quick Look on macOS; not yet available cross-platform — `VORSCHAU_VERFUEGBAR` is macOS-only in `plattform.py`).
- Known limitation, stated honestly to users: a document containing only a bare model/part number with nothing semantically connected to the search term will not be found — "no search model of this size has product knowledge like that."
- Free, no account, no license/activation gating, no usage data collection.
- Windows port: in active development, unreleased. `plattform.py` isolates all OS-specific behavior (notifications, preview, "reveal in file manager," autostart) behind one interface so `gui.py` stays platform-agnostic; `menueleiste_windows.py` mirrors `menueleiste_mac.py` (tray icon via pystray, global hotkey via RegisterHotKey) with identical function names. Preview-without-opening (Quick Look) has no confirmed Windows equivalent yet. Linux is mentioned in code comments as a possible future target but is not an active work item.
- Marketing site (`website/`) is a separate, already-built surface (German, with a distinct English-facing consideration) — currently macOS-download-only; no Windows download is offered there yet, consistent with the port being unreleased.

## Brand Commitments

- Name: SmartSearch. Domain: smartsearch-app.com.
- Tone of the existing copy (website, INSTALLATION.md) is calm, precise, and unusually transparent — it explains *why* things happen (the Gatekeeper warning, the model download, the limits of semantic search) rather than hiding complexity. Preserve this voice in any future user-facing copy.
- Price: free (0 €), stated plainly and repeatedly as a reason no Apple notarization exists yet.
- Existing icon assets: `icon.icns`, `icon.ico`, `icon.png`, `icon_rundlos.png`.

## Evidence on Hand

- Live marketing site at `website/` (index.html, legal pages, fonts, screenshots) — already fully designed and written; treat as incumbent visual/voice authority for that surface, not a placeholder.
- Realistic sample corpus at `demo-dokumente/` — scanned documents with cryptic auto-generated filenames, used to demonstrate the "you know the content, not the name" problem.
- Product screenshots: `website/smartsearch-fenster.png`, `website/vorschaubild.png`.
- Demo videos of the app in use: `SmartSearch-Kurzvideo.mp4`, `SmartSearch-Kurzvideo-v2.mp4`, `SmartSearch-Video-final.mp4`, `SmartSearch-Video-ohne-Ton.mp4`.
- No testimonials, press, or third-party benchmarks exist yet — do not fabricate any.

## Product Principles

1. Content over filenames: every feature decision should serve "find it by what it's about," not by name/location.
2. Local-only, always: no design or feature may imply or introduce data leaving the device without an equally explicit, honest disclosure — this product's trust is built on radical transparency about data handling.
3. Zero setup friction: no accounts, no mandatory configuration beyond folder selection; defaults should protect first-run speed (e.g. not preselecting huge folders).
4. Honest about limits: the product states plainly what it can't do (e.g. bare part numbers with no semantic context) rather than overselling AI search.
5. One codebase, OS-specific edges isolated: platform differences (macOS vs. Windows) live behind a single abstraction (`plattform.py`, `menueleiste_*.py`) so the interface and interaction model stay identical across OSes.

## Accessibility & Inclusion

No product-specific accessibility requirement has been established yet.
