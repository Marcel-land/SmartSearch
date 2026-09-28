"""
kanzlei.py - 25 Dokumente aus einer Anwaltskanzlei.

Die Zielgruppe von SmartSearch. Kanzlei, Mandanten, Gegner und Aktenzeichen
sind erfunden; Gerichte und Paragraphen sind echt, damit Fachbegriffe so
vorkommen wie in einer echten Akte.

Kanzlei: Kroeger & Petersen Rechtsanwaelte, Bielefeld. Akten:
  118/24  Albers ./. Westfalen Direkt      Verkehrsunfall (Klage, Gutachten,
                                           Vollmacht, Urteil)
  042/24  Wortmann ./. Hofmann Metallbau   Kuendigungsschutz (Klage, Abmahnung,
                                           Aufhebungsvertrag, Ladung, Notiz)
  077/24  Wohnbau Teutoburg ./. Neumann    Raeumung wegen Mietrueckstand
  090/24  Oezdemir                         Mietminderung wegen Schimmel
  101/24  Brinkmann                        Testament, Erbschein
  063/24  Kaya                             Scheidung, Kindesunterhalt
  131/24  Lindenhof Software GmbH          Gruendung, NDA (englisch)
  055/24  Hofmann Metallbau                Mahnverfahren
  024/24  Schulte ./. Autohandel Brandes   Berufung Gebrauchtwagenkauf
  dazu Kanzleiverwaltung: Vorschuss, Kostenrechnung, Fristen,
  Verguetungsvereinbarung, AVV, beA-Schulung.

STOLPERSTEINE: "Versicherung" steht auch in "eidesstattliche Versicherung";
dieselbe Versicherung wie im Haushalt ist hier Gegnerin; das Aktenzeichen
3 C 118/24 steht im Urteil UND im Fristenkalender; ein Autokauf-Streit
konkurriert mit dem privaten Kaufvertrag; "Zeugnis" im Aufhebungsvertrag
konkurriert mit dem echten Arbeitszeugnis.
"""

from .bausteine import Dok

K = "kanzlei/"
KOPF = ["Kröger & Petersen Rechtsanwälte",
        "Am Lindenhof 7 · 33602 Bielefeld · Tel. 0521 000000"]
A118 = K + "Akte 118-24 Albers/"
A042 = K + "Akte 042-24 Wortmann/"
VERW = K + "Verwaltung/"

DOKUMENTE = [
    # ------------------------------------------------------------------
    # Akte 118/24 - Verkehrsunfall
    # ------------------------------------------------------------------
    Dok(A118 + "Klage_Albers_v2.docx", "docx", "Klage", inhalt=KOPF + [
        "",
        "An das Amtsgericht Bielefeld",
        "Gerichtstraße 6, 33602 Bielefeld",
        "",
        "# Klage",
        "des Herrn Jonas Albers, Wittekindstraße 30, 33615 Bielefeld – Kläger –",
        "Prozessbevollmächtigte: Rechtsanwälte Kröger & Petersen",
        "gegen",
        "die Westfalen Direkt Versicherung AG, vertreten durch den Vorstand, – Beklagte –",
        "wegen Schadensersatzes aus einem Verkehrsunfall",
        "Streitwert: 6.915,17 EUR",
        "",
        "Namens und in Vollmacht des Klägers erheben wir Klage und werden beantragen,",
        "die Beklagte zu verurteilen, an den Kläger 6.915,17 EUR nebst Zinsen in Höhe von fünf "
        "Prozentpunkten über dem Basiszinssatz seit dem 12.03.2024 zu zahlen.",
        "",
        "## Begründung",
        "Am 14.01.2024 gegen 7:45 Uhr befuhr der Kläger mit seinem Pkw VW Golf, amtliches "
        "Kennzeichen BI-JA 330, die Stapenhorststraße in Richtung Innenstadt. An der Kreuzung "
        "mit der Wittekindstraße missachtete der Versicherungsnehmer der Beklagten mit seinem "
        "Transporter das Rotlicht der Ampel und stieß in die rechte Fahrzeugseite des Klägers.",
        "Die Beklagte ist der Haftpflichtversicherer des Unfallgegners. Sie haftet nach § 7 StVG, "
        "§ 115 Abs. 1 Nr. 1 VVG als Gesamtschuldnerin in voller Höhe.",
        "Der Schaden setzt sich zusammen aus: Reparaturkosten laut Gutachten netto 5.748,04 EUR, "
        "merkantile Wertminderung 350,00 EUR, Sachverständigenkosten 612,13 EUR, "
        "Nutzungsausfall für 12 Tage à 15,00 EUR = 180,00 EUR sowie Kostenpauschale 25,00 EUR.",
        "Die Beklagte hat mit Schreiben vom 11.03.2024 jede Zahlung abgelehnt und eine "
        "Mithaftung des Klägers wegen überhöhter Geschwindigkeit behauptet. Das ist unzutreffend.",
        "Beweis: Zeugnis der Frau Lena Hartmann; Sachverständigengutachten; Unfallskizze der Polizei",
        "",
        "Rechtsanwalt Dr. Tobias Kröger",
    ]),

    Dok(A118 + "Gutachten_Scan.pdf", "scan", "", stempel="EINGANG|22. JAN. 2024", inhalt=[
        "Ingenieurbüro Rethemeier · Kfz-Sachverständige",
        "Detmolder Str. 480 · 33605 Bielefeld",
        "",
        "# Haftpflichtschadengutachten Nr. 24-0158",
        "Auftraggeber: Jonas Albers, Wittekindstraße 30, 33615 Bielefeld",
        "Besichtigung: 17.01.2024 in der Werkstatt Autohaus Teutoburger Wald",
        "",
        "## Fahrzeug",
        "Hersteller/Typ: VW Golf VII 1.5 TSI · Kennzeichen BI-JA 330",
        "Erstzulassung 03/2019 · Laufleistung 58.212 km · Farbe Uranograu",
        "",
        "## Schadenbeschreibung",
        "Anstoß rechts seitlich im Bereich Beifahrertür und B-Säule.",
        "Tür vorn rechts und hinten rechts eingedrückt, Schweller verformt,",
        "Seitenairbag nicht ausgelöst. Fahrzeug ist fahrfähig und verkehrssicher.",
        "",
        "## Kalkulation",
        "Reparaturkosten netto                          5.748,04 EUR",
        "Reparaturkosten brutto                         6.840,17 EUR",
        "Merkantile Wertminderung                         350,00 EUR",
        "Wiederbeschaffungswert brutto                 18.900,00 EUR",
        "Restwert                                       9.400,00 EUR",
        "Reparaturdauer 5 Arbeitstage, Wiederbeschaffungsdauer 12 Kalendertage",
        "Nutzungsausfall Gruppe D: 15,00 EUR je Tag",
        "",
        "Ergebnis: wirtschaftlicher Reparaturschaden, eine Instandsetzung ist sinnvoll.",
    ]),

    Dok(A118 + "Scan_0042.pdf", "scan", "", stempel=None, inhalt=[
        "# Vollmacht",
        "",
        "Den Rechtsanwälten Kröger & Petersen, Am Lindenhof 7, 33602 Bielefeld,",
        "wird hiermit in Sachen",
        "",
        "Albers ./. Westfalen Direkt Versicherung AG",
        "wegen Verkehrsunfall vom 14.01.2024",
        "",
        "Vollmacht erteilt",
        "1. zur Prozessführung (u. a. nach §§ 81 ff. ZPO) einschließlich der Befugnis",
        "   zur Erhebung und Zurücknahme von Widerklagen;",
        "2. zur Vertretung in sonstigen Verfahren und bei außergerichtlichen Verhandlungen;",
        "3. zur Begründung und Aufhebung von Vertragsverhältnissen;",
        "4. zum Abschluss von Vergleichen, zur Entgegennahme von Geld, Wertsachen",
        "   und Urkunden, insbesondere des Streitgegenstandes;",
        "5. Untervollmacht zu erteilen und Rechtsmittel einzulegen oder zurückzunehmen.",
        "",
        "Bielefeld, den 19.01.2024",
        "",
        "Unterschrift: Jonas Albers",
    ]),

    Dok(A118 + "Scan_Urteil_AG.pdf", "scan", "", stempel="EINGANG|08. JULI 2024", inhalt=[
        "Amtsgericht Bielefeld",
        "Aktenzeichen: 3 C 118/24",
        "Verkündet am 04.07.2024",
        "",
        "# Im Namen des Volkes",
        "# Urteil",
        "",
        "In dem Rechtsstreit",
        "Jonas Albers, Wittekindstraße 30, 33615 Bielefeld, Kläger,",
        "Prozessbevollmächtigte: Rechtsanwälte Kröger & Petersen, Bielefeld,",
        "gegen",
        "Westfalen Direkt Versicherung AG, Beklagte,",
        "",
        "hat das Amtsgericht Bielefeld auf die mündliche Verhandlung vom 20.06.2024",
        "durch den Richter am Amtsgericht Lohmann für Recht erkannt:",
        "",
        "1. Die Beklagte wird verurteilt, an den Kläger 6.855,17 EUR nebst Zinsen",
        "   in Höhe von fünf Prozentpunkten über dem Basiszinssatz seit dem",
        "   12.03.2024 zu zahlen. Im Übrigen wird die Klage abgewiesen.",
        "2. Die Kosten des Rechtsstreits trägt die Beklagte zu 99 %, der Kläger zu 1 %.",
        "3. Das Urteil ist gegen Sicherheitsleistung in Höhe von 110 % des jeweils",
        "   zu vollstreckenden Betrages vorläufig vollstreckbar.",
        "---",
        "## Entscheidungsgründe",
        "Die zulässige Klage ist überwiegend begründet. Der Kläger hat gegen die",
        "Beklagte einen Anspruch aus § 7 Abs. 1 StVG, § 115 Abs. 1 Nr. 1 VVG.",
        "Nach dem Ergebnis der Beweisaufnahme steht fest, dass der Versicherungsnehmer",
        "der Beklagten bei Rotlicht in die Kreuzung eingefahren ist. Die Zeugin Hartmann",
        "hat den Unfallhergang glaubhaft und widerspruchsfrei geschildert.",
        "Ein Mitverschulden des Klägers wegen überhöhter Geschwindigkeit ist nicht bewiesen.",
        "Die Reparaturkosten, die Wertminderung und die Sachverständigenkosten sind",
        "in voller Höhe zu ersetzen. Nutzungsausfall kann der Kläger jedoch nur für",
        "die tatsächliche Reparaturdauer von fünf Arbeitstagen zuzüglich Wochenende und Werkstatttermin,",
        "also für 8 Tage verlangen; insoweit war die Klage abzuweisen.",
        "Die Kostenentscheidung beruht auf § 92 Abs. 2 Nr. 1 ZPO, die Entscheidung",
        "über die vorläufige Vollstreckbarkeit auf § 709 ZPO.",
        "",
        "Rechtsbehelfsbelehrung: Gegen dieses Urteil ist die Berufung statthaft, wenn",
        "der Wert des Beschwerdegegenstandes 600 EUR übersteigt. Die Berufung ist",
        "binnen einer Notfrist von einem Monat bei dem Landgericht Bielefeld einzulegen.",
        "",
        "Lohmann, Richter am Amtsgericht",
    ]),

    # ------------------------------------------------------------------
    # Akte 042/24 - Arbeitsrecht
    # ------------------------------------------------------------------
    Dok(A042 + "KSK_Wortmann.docx", "docx", "Klage ArbG", inhalt=KOPF + [
        "",
        "An das Arbeitsgericht Bielefeld",
        "",
        "# Kündigungsschutzklage",
        "der Frau Sabine Wortmann, Am Brodhagen 12, 33613 Bielefeld – Klägerin –",
        "gegen",
        "die Hofmann Metallbau GmbH, vertreten durch den Geschäftsführer Rolf Hofmann,",
        "Industriestraße 44, 33689 Bielefeld – Beklagte –",
        "",
        "Wir beantragen festzustellen, dass das Arbeitsverhältnis der Parteien durch die "
        "Kündigung der Beklagten vom 29.02.2024, der Klägerin zugegangen am selben Tag, "
        "nicht aufgelöst worden ist.",
        "",
        "## Begründung",
        "Die 51-jährige Klägerin ist seit dem 01.09.2004 bei der Beklagten als Sachbearbeiterin "
        "in der Auftragsabwicklung beschäftigt, zuletzt mit einem Bruttomonatsgehalt von "
        "3.380,00 EUR. Sie ist verheiratet und einem Kind zum Unterhalt verpflichtet.",
        "Die Beklagte beschäftigt regelmäßig mehr als 10 Arbeitnehmer; das "
        "Kündigungsschutzgesetz findet Anwendung. Die Klage wird innerhalb der Frist von drei "
        "Wochen nach § 4 KSchG erhoben.",
        "Die Kündigung ist sozial ungerechtfertigt (§ 1 Abs. 2 KSchG). Die Beklagte beruft sich "
        "auf betriebsbedingte Gründe, nämlich die Zusammenlegung der Auftragsabwicklung mit dem "
        "Einkauf. Ein dauerhafter Wegfall des Arbeitsplatzes wird bestritten.",
        "Jedenfalls ist die Sozialauswahl fehlerhaft (§ 1 Abs. 3 KSchG). Vergleichbare Kollegen "
        "mit deutlich kürzerer Betriebszugehörigkeit und ohne Unterhaltspflichten wurden nicht "
        "gekündigt. Die Beklagte wird aufgefordert, die Gründe der Sozialauswahl mitzuteilen.",
        "Der Betriebsrat wurde nach unserer Kenntnis nicht ordnungsgemäß angehört (§ 102 BetrVG).",
        "",
        "Rechtsanwältin Anna Petersen, Fachanwältin für Arbeitsrecht",
    ]),

    Dok(A042 + "Abmahnung_2023.pdf", "pdf", "Abmahnung", inhalt=[
        "Hofmann Metallbau GmbH · Industriestraße 44 · 33689 Bielefeld",
        "",
        "Frau Sabine Wortmann – persönlich / vertraulich –",
        "",
        "Bielefeld, 06.11.2023",
        "",
        "# Abmahnung",
        "",
        "Sehr geehrte Frau Wortmann,",
        "am 23.10.2023, am 30.10.2023 und am 03.11.2023 haben Sie Ihre Arbeit erst um 8:40 Uhr, "
        "8:55 Uhr bzw. 9:20 Uhr aufgenommen, obwohl Ihre Arbeitszeit nach § 3 Ihres "
        "Arbeitsvertrags um 7:30 Uhr beginnt. Eine Entschuldigung haben Sie nicht vorgebracht, "
        "den Vorgesetzten haben Sie nicht vorab informiert.",
        "Durch Ihre Verspätungen blieben Kundenaufträge unbearbeitet, Kolleginnen mussten Ihre "
        "Telefonvertretung übernehmen.",
        "Wir mahnen Sie wegen dieser Pflichtverletzungen hiermit ab und fordern Sie auf, "
        "künftig pünktlich zu Arbeitsbeginn zu erscheinen.",
        "Wir weisen Sie ausdrücklich darauf hin, dass Sie im Wiederholungsfall mit "
        "arbeitsrechtlichen Konsequenzen bis hin zur Kündigung Ihres Arbeitsverhältnisses "
        "rechnen müssen.",
        "Eine Kopie dieses Schreibens wird zu Ihrer Personalakte genommen.",
        "",
        "Rolf Hofmann, Geschäftsführer",
        "Empfang bestätigt: ____________________",
    ]),

    Dok(A042 + "Aufhebungsvertrag_Entwurf.docx", "docx", "Entwurf", inhalt=[
        "ENTWURF – Stand 18.03.2024 – zur Abstimmung mit der Mandantin",
        "",
        "# Aufhebungsvertrag",
        "zwischen der Hofmann Metallbau GmbH (Arbeitgeberin) und Frau Sabine Wortmann (Arbeitnehmerin)",
        "",
        "## § 1 Beendigung",
        "Die Parteien sind sich einig, dass das Arbeitsverhältnis auf Veranlassung der "
        "Arbeitgeberin aus betriebsbedingten Gründen mit Ablauf des 30.09.2024 endet.",
        "## § 2 Abfindung",
        "Die Arbeitgeberin zahlt der Arbeitnehmerin für den Verlust des Arbeitsplatzes eine "
        "Abfindung in Höhe von 18.500,00 EUR brutto. Die Abfindung ist mit der letzten "
        "Gehaltsabrechnung fällig und vererblich.",
        "## § 3 Freistellung",
        "Die Arbeitnehmerin wird ab 01.05.2024 unter Anrechnung ihres Resturlaubs unwiderruflich "
        "von der Arbeitsleistung freigestellt. Die Vergütung wird bis zum Beendigungszeitpunkt "
        "fortgezahlt.",
        "## § 4 Zeugnis",
        "Die Arbeitnehmerin erhält ein wohlwollendes qualifiziertes Zeugnis mit der Gesamtnote "
        "sehr gut. Sie hat ein Vorschlagsrecht.",
        "## § 5 Erledigung",
        "Mit Erfüllung dieses Vertrags sind alle gegenseitigen Ansprüche aus dem "
        "Arbeitsverhältnis erledigt. Die Kündigungsschutzklage wird zurückgenommen.",
        "",
        "Hinweis an die Mandantin: Ein Aufhebungsvertrag kann eine Sperrzeit beim "
        "Arbeitslosengeld von bis zu 12 Wochen auslösen (§ 159 SGB III). Bitte vor der "
        "Unterschrift mit der Agentur für Arbeit klären. Alternativ Vergleich im Gütetermin.",
    ]),

    Dok(A042 + "Scan_20240610_0001.pdf", "scan", "", stempel="EINGANG|11. JUNI 2024", inhalt=[
        "Arbeitsgericht Bielefeld",
        "Geschäftszeichen: 2 Ca 311/24",
        "",
        "Rechtsanwälte Kröger & Petersen, Am Lindenhof 7, 33602 Bielefeld",
        "",
        "In dem Rechtsstreit Wortmann ./. Hofmann Metallbau GmbH",
        "",
        "# Ladung zum Gütetermin",
        "",
        "Termin zur Güteverhandlung wird bestimmt auf",
        "Dienstag, den 02.07.2024, 09:30 Uhr,",
        "Saal 3, Erdgeschoss, Arbeitsgericht Bielefeld.",
        "",
        "Das persönliche Erscheinen der Klägerin und eines vertretungsberechtigten",
        "Organs der Beklagten wird angeordnet (§ 51 ArbGG).",
        "",
        "Die Güteverhandlung dient der gütlichen Einigung der Parteien (§ 54 ArbGG).",
        "Bleibt sie erfolglos, schließt sich die weitere Verhandlung unmittelbar an",
        "oder es wird ein Kammertermin bestimmt.",
        "",
        "Auf Anordnung · Justizbeschäftigte",
    ]),

    Dok(A042 + "notiz_2024-03-05.md", "md", "Aktennotiz", inhalt=[
        "# Aktennotiz Telefonat",
        "",
        "Akte 042/24 Wortmann ./. Hofmann Metallbau · 05.03.2024 · RAin Petersen",
        "",
        "Mandantin rief an, 14:10–14:35 Uhr.",
        "",
        "- Klage ist raus (eingereicht 04.03.), Mandantin informiert",
        "- Mandantin möchte eigentlich nicht zurück in den Betrieb, Arbeitsklima schlecht",
        "- Wäre mit einer Einigung einverstanden, Vorstellung: mindestens ein halbes "
        "Monatsgehalt je Beschäftigungsjahr (20 Jahre → ca. 33.800 EUR)",
        "- Hat bereits ein Angebot eines anderen Arbeitgebers ab Oktober in Aussicht",
        "- Frage zu Arbeitslosengeld und Sperrzeit: erklärt, Rückruf mit Details",
        "- Abmahnung aus 2023 (Verspätungen) ist ihr bekannt, Gründe waren Pflege der Mutter",
        "",
        "To do: Gegenseite nach Vergleichsbereitschaft fragen, vor dem Gütetermin",
        "Entwurf Aufhebungsvertrag vorbereiten.",
    ]),

    # ------------------------------------------------------------------
    # Mietrecht
    # ------------------------------------------------------------------
    Dok(K + "Akte 077-24 Wohnbau Teutoburg/Klage_Raeumung.docx", "docx", "Klage", inhalt=KOPF + [
        "",
        "An das Amtsgericht Bielefeld",
        "",
        "# Klage auf Räumung und Zahlung",
        "der Wohnbau Teutoburg GmbH, Bahnhofstraße 5, 33602 Bielefeld – Klägerin –",
        "gegen",
        "Herrn Dennis Neumann, Feldstraße 18, 33609 Bielefeld – Beklagter –",
        "",
        "Wir beantragen,",
        "1. den Beklagten zu verurteilen, die Wohnung Feldstraße 18, 1. OG rechts, bestehend aus "
        "drei Zimmern, Küche, Bad und Kellerraum Nr. 4, zu räumen und an die Klägerin herauszugeben;",
        "2. den Beklagten zu verurteilen, an die Klägerin 2.140,00 EUR rückständige Miete nebst "
        "Zinsen zu zahlen.",
        "",
        "## Begründung",
        "Die Parteien verbindet ein Wohnraummietvertrag vom 15.06.2019. Die Bruttomiete beträgt "
        "monatlich 1.070,00 EUR und ist bis zum dritten Werktag eines Monats zu zahlen.",
        "Der Beklagte hat die Mieten für Januar und Februar 2024 nicht gezahlt. Er befand sich "
        "damit an zwei aufeinanderfolgenden Terminen mit der Entrichtung der Miete in Verzug.",
        "Die Klägerin hat das Mietverhältnis deshalb mit Schreiben vom 12.02.2024 fristlos nach "
        "§ 543 Abs. 2 Satz 1 Nr. 3 lit. a BGB und hilfsweise ordentlich nach § 573 Abs. 2 Nr. 1 BGB "
        "gekündigt. Der Beklagte hat die Wohnung bis heute nicht zurückgegeben.",
        "Der Anspruch auf Räumung und Herausgabe folgt aus § 546 Abs. 1 BGB und § 985 BGB.",
        "Auf die Schonfristregelung des § 569 Abs. 3 Nr. 2 BGB wird hingewiesen.",
        "",
        "Rechtsanwalt Dr. Tobias Kröger",
    ]),

    Dok(K + "Akte 090-24 Özdemir/Schreiben_Vermieter.docx", "docx", "Schreiben", inhalt=KOPF + [
        "",
        "Einschreiben mit Rückschein",
        "Immobilien Kessler GmbH, Hausverwaltung, Niedernstraße 3, 33602 Bielefeld",
        "",
        "Bielefeld, 22.04.2024",
        "",
        "Mietverhältnis Özdemir, Sieker Mitte 9, 2. OG",
        "",
        "Sehr geehrte Damen und Herren,",
        "wir zeigen an, dass uns Herr Murat Özdemir und Frau Elif Özdemir mit der Wahrnehmung "
        "ihrer rechtlichen Interessen beauftragt haben.",
        "Unsere Mandanten haben Ihnen bereits am 04.03.2024 schriftlich angezeigt, dass sich im "
        "Schlafzimmer und im Kinderzimmer an den Außenwänden großflächiger Schimmelbefall "
        "gebildet hat. Die befallene Fläche beträgt inzwischen rund 3 m². Ursache ist nach "
        "Einschätzung eines Bausachverständigen eine Wärmebrücke im Bereich der Deckenanschlüsse, "
        "nicht ein falsches Heiz- oder Lüftungsverhalten.",
        "Die Wohnung ist dadurch in ihrer Tauglichkeit zum vertragsgemäßen Gebrauch erheblich "
        "gemindert. Die Miete ist nach § 536 Abs. 1 BGB kraft Gesetzes gemindert; wir halten eine "
        "Minderung von 15 % der Bruttomiete für angemessen. Unsere Mandanten werden die Miete ab "
        "Mai 2024 nur noch unter Vorbehalt und gemindert zahlen.",
        "Wir fordern Sie auf, den Mangel fachgerecht bis zum 31.05.2024 zu beseitigen. Nach "
        "fruchtlosem Fristablauf behalten sich unsere Mandanten die Ersatzvornahme nach "
        "§ 536a Abs. 2 BGB vor.",
        "",
        "Mit freundlichen Grüßen",
        "Rechtsanwältin Anna Petersen",
    ]),

    # ------------------------------------------------------------------
    # Erbrecht
    # ------------------------------------------------------------------
    Dok(K + "Akte 101-24 Brinkmann/Testament_Entwurf_Brinkmann.docx", "docx", "Entwurf", inhalt=[
        "Entwurf zur Besprechung am 12.04.2011 – nicht unterschreiben!",
        "Hinweis: Ein privatschriftliches Testament muss vollständig eigenhändig geschrieben und "
        "unterschrieben werden (§ 2247 BGB). Dieser Text dient nur als Vorlage zum Abschreiben.",
        "",
        "# Gemeinschaftliches Testament",
        "Wir, die Eheleute Heinrich Brinkmann, geb. 02.05.1944, und Gisela Brinkmann, "
        "geb. 17.09.1947, wohnhaft Schildescher Straße 60, 33611 Bielefeld, errichten hiermit "
        "folgendes gemeinschaftliches Testament:",
        "1. Wir setzen uns gegenseitig zu alleinigen Erben ein.",
        "2. Schlusserben nach dem Tod des Längerlebenden sind unsere Kinder Thomas Brinkmann "
        "und Petra Albrecht geb. Brinkmann zu gleichen Teilen (Berliner Testament, § 2269 BGB).",
        "3. Pflichtteilsstrafklausel: Verlangt eines unserer Kinder nach dem Tod des Erstversterbenden "
        "gegen den Willen des Überlebenden seinen Pflichtteil, so ist es mit seinen Abkömmlingen "
        "auch nach dem Tod des Längerlebenden auf den Pflichtteil beschränkt.",
        "4. Der Längerlebende ist berechtigt, die Schlusserbeneinsetzung abzuändern, soweit sie "
        "unsere Kinder und deren Abkömmlinge untereinander betrifft.",
        "5. Die Eigentumswohnung auf Norderney erhält als Vermächtnis unsere Enkelin Lea Albrecht.",
        "",
        "Bielefeld, den ______________",
    ]),

    Dok(K + "Akte 101-24 Brinkmann/Antrag_Nachlassgericht.pdf", "pdf", "Antrag", inhalt=KOPF + [
        "",
        "An das Amtsgericht Bielefeld – Nachlassgericht –",
        "",
        "# Antrag auf Erteilung eines Erbscheins",
        "",
        "In der Nachlasssache Heinrich Brinkmann, zuletzt wohnhaft Schildescher Straße 60,",
        "33611 Bielefeld, verstorben am 03.02.2024 in Bielefeld,",
        "",
        "beantragen wir namens der Witwe, Frau Gisela Brinkmann, die Erteilung eines Erbscheins,",
        "der sie als Alleinerbin des Erblassers ausweist (§ 2353 BGB, § 352 FamFG).",
        "",
        "## Begründung",
        "Die Antragstellerin ist aufgrund des gemeinschaftlichen Testaments vom 30.04.2011",
        "(Aktenzeichen des Nachlassgerichts 16 IV 212/24, eröffnet am 28.02.2024) Alleinerbin.",
        "Weitere Verfügungen von Todes wegen sind nicht vorhanden. Ein Rechtsstreit über das",
        "Erbrecht ist nicht anhängig. Die Erbschaft wurde angenommen.",
        "Der Nachlass besteht im Wesentlichen aus einem Einfamilienhaus, Bankguthaben und",
        "einer Eigentumswohnung. Der Nachlasswert beträgt nach vorläufiger Schätzung 640.000 EUR.",
        "",
        "Die Antragstellerin wird die nach § 352 Abs. 3 FamFG erforderliche eidesstattliche",
        "Versicherung zur Niederschrift des Gerichts oder eines Notars abgeben.",
        "Beigefügt: Sterbeurkunde, Heiratsurkunde, Abschrift des Eröffnungsprotokolls.",
    ]),

    # ------------------------------------------------------------------
    # Familienrecht
    # ------------------------------------------------------------------
    Dok(K + "Akte 063-24 Kaya/Antrag_FamG.docx", "docx", "Antrag", inhalt=KOPF + [
        "",
        "An das Amtsgericht Bielefeld – Familiengericht –",
        "",
        "# Scheidungsantrag",
        "der Frau Aylin Kaya, Friedenstraße 21, 33602 Bielefeld – Antragstellerin –",
        "gegen",
        "Herrn Emre Kaya, Hauptstraße 150, 33647 Bielefeld – Antragsgegner –",
        "",
        "Wir beantragen, die am 14.08.2015 vor dem Standesamt Bielefeld geschlossene Ehe der "
        "Beteiligten zu scheiden.",
        "",
        "## Begründung",
        "Die Beteiligten leben seit dem 01.03.2023 getrennt. Der Antragsgegner ist an diesem Tag "
        "aus der Ehewohnung ausgezogen. Das Trennungsjahr ist abgelaufen; das Scheitern der Ehe "
        "wird nach § 1566 Abs. 1 BGB unwiderlegbar vermutet, da der Antragsgegner der Scheidung "
        "zustimmen wird.",
        "Aus der Ehe sind zwei gemeinsame Kinder hervorgegangen: Mira, geboren am 02.06.2016, und "
        "Can, geboren am 19.11.2019. Die Kinder leben bei der Antragstellerin. Eine Regelung des "
        "Sorgerechts wird nicht beantragt; die Eltern üben die elterliche Sorge weiter gemeinsam aus.",
        "Der Versorgungsausgleich ist von Amts wegen durchzuführen. Beide Beteiligte haben "
        "Anrechte in der gesetzlichen Rentenversicherung erworben.",
        "Über Kindesunterhalt, Ehegattenunterhalt und Zugewinn verhandeln die Beteiligten "
        "außergerichtlich.",
        "",
        "Rechtsanwältin Anna Petersen, Fachanwältin für Familienrecht",
    ]),

    Dok(K + "Akte 063-24 Kaya/Berechnung_KU.xlsx", "xlsx", "Berechnung", inhalt={
        "Berechnung": [
            ["Kindesunterhalt nach Düsseldorfer Tabelle 2024 – Akte 063/24 Kaya", "", "", ""],
            ["Position", "Betrag (EUR)", "", ""],
            ["Nettoeinkommen Pflichtiger (Durchschnitt 12 Monate)", 3180.00, "", ""],
            ["abzgl. berufsbedingte Aufwendungen 5 %", -159.00, "", ""],
            ["abzgl. Kreditrate Pkw (eheprägend)", -210.00, "", ""],
            ["bereinigtes Nettoeinkommen", 2811.00, "", ""],
            ["Einkommensgruppe", "4 (2.701 – 3.100 EUR), 115 %", "", ""],
            ["", "", "", ""],
            ["Kind", "Altersstufe", "Tabellenbetrag", "Zahlbetrag nach hälftigem Kindergeld"],
            ["Mira, geb. 02.06.2016", "2 (6–11 Jahre)", 634, 509],
            ["Can, geb. 19.11.2019", "1 (0–5 Jahre)", 552, 427],
            ["Summe Zahlbeträge monatlich", "", 1186, 936],
            ["", "", "", ""],
            ["Selbstbehalt Erwerbstätiger", 1450, "", ""],
            ["Verbleibt dem Pflichtigen", 1875, "", ""],
            ["Ergebnis", "leistungsfähig, kein Mangelfall", "", ""],
        ],
    }),

    # ------------------------------------------------------------------
    # Gesellschaftsrecht / Wirtschaft
    # ------------------------------------------------------------------
    Dok(K + "Akte 131-24 Lindenhof Software/Satzung_Entwurf.pdf", "pdf", "Entwurf", inhalt=[
        "Entwurf – zur notariellen Beurkundung (§ 2 GmbHG)",
        "",
        "# Gesellschaftsvertrag der Lindenhof Software GmbH",
        "",
        "## § 1 Firma, Sitz",
        "Die Firma der Gesellschaft lautet Lindenhof Software GmbH. Sitz ist Bielefeld.",
        "## § 2 Gegenstand",
        "Gegenstand des Unternehmens ist die Entwicklung und der Vertrieb von Software, "
        "insbesondere für die Dokumentenverwaltung, sowie damit verbundene Beratungsleistungen.",
        "## § 3 Stammkapital",
        "Das Stammkapital beträgt 25.000,00 EUR. Hiervon übernehmen: Julia Lindemann 13.000 "
        "Geschäftsanteile im Nennbetrag von je 1,00 EUR, Kai Stratmann 12.000 Geschäftsanteile "
        "im Nennbetrag von je 1,00 EUR. Die Einlagen sind sofort zur Hälfte in bar zu erbringen.",
        "## § 4 Geschäftsführung und Vertretung",
        "Die Gesellschaft hat einen oder mehrere Geschäftsführer. Ist nur ein Geschäftsführer "
        "bestellt, vertritt er allein. Die Geschäftsführer sind von den Beschränkungen des "
        "§ 181 BGB befreit.",
        "## § 5 Verfügung über Geschäftsanteile",
        "Die Abtretung von Geschäftsanteilen bedarf der Zustimmung der Gesellschafterversammlung.",
        "## § 6 Gründungskosten",
        "Die Gesellschaft trägt die Kosten der Gründung bis zu 2.500 EUR.",
        "",
        "Anmerkung RA Kröger: Nach Beurkundung Anmeldung zum Handelsregister durch den Notar; "
        "Bankbestätigung über die Einzahlung beifügen.",
    ]),

    Dok(K + "Akte 131-24 Lindenhof Software/NDA_Northbridge.docx", "docx", "NDA", inhalt=[
        "# Mutual Non-Disclosure Agreement",
        "between Lindenhof Software GmbH, Bielefeld, Germany (\"Lindenhof\")",
        "and Northbridge Analytics Ltd., Leeds, United Kingdom (\"Northbridge\")",
        "",
        "## 1. Purpose",
        "The parties intend to evaluate a joint development of an AI-based document "
        "classification module (the \"Purpose\"). For this Purpose, each party may disclose "
        "Confidential Information to the other.",
        "## 2. Confidential Information",
        "Confidential Information means all technical and business information, including "
        "source code, customer lists, pricing and product roadmaps, disclosed in any form and "
        "marked or reasonably understood as confidential.",
        "## 3. Obligations",
        "The receiving party shall keep Confidential Information strictly secret, use it solely "
        "for the Purpose and disclose it only to employees and advisers bound by equivalent "
        "confidentiality obligations.",
        "## 4. Exceptions",
        "The obligations do not apply to information that is publicly available, was already "
        "known to the receiving party, or must be disclosed by law or court order.",
        "## 5. Term",
        "This Agreement enters into force upon signature and remains in effect for three (3) "
        "years. The obligations survive for a further two (2) years after termination.",
        "## 6. Contractual penalty",
        "For each culpable breach, the breaching party shall pay a contractual penalty of "
        "EUR 10,000, without prejudice to further damages.",
        "## 7. Governing law",
        "This Agreement is governed by German law. Place of jurisdiction is Bielefeld, Germany.",
    ]),

    Dok(K + "Akte 055-24 Hofmann Metallbau/Scan_20240506_0007.pdf", "scan", "",
        stempel="EINGANG|07. MAI 2024", inhalt=[
            "Amtsgericht Hagen – Zentrales Mahngericht Nordrhein-Westfalen",
            "Geschäftsnummer: 24-1188421-0-3",
            "",
            "# Mahnbescheid",
            "",
            "Antragsteller: Hofmann Metallbau GmbH, Industriestraße 44, 33689 Bielefeld",
            "Prozessbevollmächtigte: Rechtsanwälte Kröger & Petersen, Bielefeld",
            "",
            "Antragsgegner: Bauunternehmung Richter KG, Paderborner Str. 77, 33689 Bielefeld",
            "",
            "Der Antragsteller macht gegen Sie folgenden Anspruch geltend:",
            "Hauptforderung: Werklohn aus Rechnung Nr. 2023-1142 vom 14.12.2023",
            "für Lieferung und Montage einer Stahltreppe            14.270,00 EUR",
            "Zinsen 9 Prozentpunkte über dem Basiszinssatz seit 15.01.2024",
            "Mahnkosten                                                 15,00 EUR",
            "Kosten des Verfahrens                                     691,25 EUR",
            "",
            "Das Gericht hat nicht geprüft, ob dem Antragsteller der Anspruch zusteht.",
            "Sie müssen binnen zwei Wochen seit der Zustellung entweder die Forderung",
            "begleichen oder dem Gericht mitteilen, ob und in welchem Umfang Sie dem",
            "Anspruch widersprechen. Andernfalls kann ein Vollstreckungsbescheid ergehen.",
        ]),

    Dok(K + "Akte 024-24 Schulte/Berufungsbegruendung.pdf", "pdf", "Schriftsatz", inhalt=KOPF + [
        "",
        "An das Landgericht Bielefeld – Berufungskammer –",
        "Az. LG: 21 S 44/24 · Az. AG: 4 C 902/23",
        "",
        "# Berufungsbegründung",
        "In dem Rechtsstreit Marco Schulte ./. Autohandel Brandes e.K.",
        "",
        "begründen wir die mit Schriftsatz vom 02.04.2024 eingelegte Berufung des Klägers",
        "gegen das Urteil des Amtsgerichts Bielefeld vom 07.03.2024 und beantragen,",
        "unter Abänderung des angefochtenen Urteils die Beklagte zu verurteilen, an den",
        "Kläger 11.400,00 EUR nebst Zinsen Zug um Zug gegen Rückgabe des Fahrzeugs zu zahlen.",
        "",
        "## I. Sachverhalt",
        "Der Kläger erwarb von der Beklagten mit Vertrag vom 18.08.2023 einen gebrauchten",
        "Kombi, Erstzulassung 2017, Laufleistung 94.000 km, zum Preis von 11.400,00 EUR.",
        "Im Vertrag ist angekreuzt: \"Dem Verkäufer sind keine Unfallschäden bekannt.\"",
        "Das Amtsgericht hat die Klage abgewiesen, weil der Kläger nicht habe beweisen",
        "können, dass die Beklagte von einem Vorschaden Kenntnis hatte.",
        "Das Amtsgericht hat den Vortrag des Klägers zum Zustand des Fahrzeugs bei",
        "Übergabe nur unvollständig gewürdigt und Beweisangebote übergangen.",
        "---",
        "## II. Rechtsfehler des Amtsgerichts",
        "1. Das Amtsgericht hat die Anforderungen an die Darlegung der Kenntnis",
        "überspannt. Die Beklagte ist gewerbliche Händlerin. Sie hat das Fahrzeug nach",
        "eigenem Vortrag vor dem Verkauf in ihrer Werkstatt aufbereitet und auf der",
        "Hebebühne untersucht (§ 529 Abs. 1 Nr. 1 ZPO).",
        "2. Das Amtsgericht hat den Beweisantrag auf Vernehmung des Zeugen Kemper,",
        "des Werkstattmeisters der Beklagten, übergangen. Darin liegt eine Verletzung",
        "des Anspruchs auf rechtliches Gehör (Art. 103 Abs. 1 GG).",
        "3. Die Beweiswürdigung ist lückenhaft (§ 286 ZPO). Das Gericht hat sich mit",
        "dem vorgelegten Privatgutachten nicht auseinandergesetzt.",
        "---",
        "## III. Anspruch des Klägers",
        "Das Fahrzeug hatte bei Übergabe einen erheblichen, unsachgemäß reparierten",
        "Unfallschaden: Der rechte Längsträger und das Radhaus hinten rechts wurden",
        "nach einem Heckaufprall gerichtet, gespachtelt und überlackiert. Die",
        "Lackschichtdicke beträgt dort bis zu 480 µm. Dies ist bei einer Untersuchung",
        "auf der Hebebühne für einen Kfz-Meister ohne Weiteres erkennbar.",
        "Die Beklagte hat den Unfallschaden damit arglistig verschwiegen. Auf den",
        "vereinbarten Gewährleistungsausschluss kann sie sich nach § 444 BGB nicht",
        "berufen. Der Kläger ist nach §§ 437 Nr. 2, 323, 326 Abs. 5 BGB wirksam vom",
        "Kaufvertrag zurückgetreten; einer Fristsetzung zur Nacherfüllung bedurfte es",
        "wegen der Arglist nicht. Die Beklagte hat den Kaufpreis Zug um Zug gegen",
        "Rückgabe des Fahrzeugs zu erstatten (§ 346 Abs. 1 BGB).",
        "",
        "Rechtsanwalt Dr. Tobias Kröger",
    ]),

    # ------------------------------------------------------------------
    # Kanzleiverwaltung
    # ------------------------------------------------------------------
    Dok(VERW + "Brief_Mandant_0314.docx", "docx", "Brief", inhalt=KOPF + [
        "",
        "Herrn Jonas Albers, Wittekindstraße 30, 33615 Bielefeld",
        "",
        "Bielefeld, 14.03.2024 · Unser Zeichen: 118/24 Kr",
        "",
        "Ihre Angelegenheit: Verkehrsunfall vom 14.01.2024",
        "",
        "Sehr geehrter Herr Albers,",
        "die gegnerische Versicherung hat die Regulierung vollständig abgelehnt. Wir empfehlen, "
        "Ihre Ansprüche nunmehr gerichtlich geltend zu machen. Die Klageschrift ist vorbereitet.",
        "Das Gericht wird die Klage erst zustellen, wenn der Gerichtskostenvorschuss eingezahlt "
        "ist. Zugleich bitten wir Sie gemäß § 9 RVG um einen angemessenen Vorschuss auf unsere "
        "Vergütung.",
        "Bitte überweisen Sie bis zum 28.03.2024 einen Betrag von 1.200,00 EUR auf unser "
        "Kanzleikonto unter Angabe des Aktenzeichens 118/24.",
        "Ist eine Rechtsschutzversicherung vorhanden, teilen Sie uns bitte die Versicherungsnummer "
        "mit; wir holen dann die Deckungszusage für Sie ein.",
        "",
        "Mit freundlichen Grüßen",
        "Dr. Tobias Kröger, Rechtsanwalt",
    ]),

    Dok(VERW + "Kostenrechnung_2024-0391.pdf", "pdf", "Kostenrechnung", inhalt=KOPF + [
        "",
        "Herrn Jonas Albers, Wittekindstraße 30, 33615 Bielefeld",
        "",
        "# Vergütungsrechnung Nr. 2024-0391",
        "Rechnungsdatum 15.07.2024 · Akte 118/24 Albers ./. Westfalen Direkt Versicherung AG",
        "Gegenstandswert: 6.915,17 EUR · Abrechnung nach dem RVG",
        "",
        "1,3 Verfahrensgebühr Nr. 3100 VV RVG                       659,10 EUR",
        "1,2 Terminsgebühr Nr. 3104 VV RVG                          608,40 EUR",
        "Pauschale für Post und Telekommunikation Nr. 7002 VV RVG    20,00 EUR",
        "Zwischensumme netto                                      1.287,50 EUR",
        "19 % Umsatzsteuer Nr. 7008 VV RVG                          244,63 EUR",
        "Gesamtbetrag                                             1.532,13 EUR",
        "abzüglich gezahlter Vorschuss                           -1.200,00 EUR",
        "Restbetrag                                                 332,13 EUR",
        "",
        "Die Beklagte ist zur Kostenerstattung zu 99 % verurteilt worden. Wir haben den",
        "Kostenfestsetzungsantrag gestellt und leiten den Erstattungsbetrag nach Eingang weiter.",
        "Steuernummer 305/5000/0000 · USt-IdNr. DE000000000",
    ]),

    Dok(VERW + "Fristen.xlsx", "xlsx", "Fristenkalender", inhalt={
        "Fristen 2024": [
            ["Akte", "Mandant", "Gericht / Az.", "Art der Frist", "Fristende", "Vorfrist", "zuständig", "erledigt"],
            ["118/24", "Albers", "AG Bielefeld 3 C 118/24", "Berufungsfrist (Gegner) 1 Monat ab Zustellung", "08.08.2024", "01.08.2024", "Kr", "nein"],
            ["118/24", "Albers", "AG Bielefeld 3 C 118/24", "Kostenfestsetzungsantrag", "31.07.2024", "24.07.2024", "Kr", "ja"],
            ["042/24", "Wortmann", "ArbG Bielefeld 2 Ca 311/24", "Klagefrist § 4 KSchG 3 Wochen", "21.03.2024", "14.03.2024", "Pe", "ja"],
            ["042/24", "Wortmann", "ArbG Bielefeld 2 Ca 311/24", "Gütetermin", "02.07.2024", "25.06.2024", "Pe", "nein"],
            ["024/24", "Schulte", "LG Bielefeld 21 S 44/24", "Berufungsbegründungsfrist 2 Monate", "13.05.2024", "06.05.2024", "Kr", "ja"],
            ["077/24", "Wohnbau Teutoburg", "AG Bielefeld 7 C 211/24", "Stellungnahme Klageerwiderung", "19.06.2024", "12.06.2024", "Kr", "nein"],
            ["090/24", "Özdemir", "außergerichtlich", "Frist Mängelbeseitigung Vermieter", "31.05.2024", "27.05.2024", "Pe", "nein"],
            ["055/24", "Hofmann Metallbau", "AG Hagen 24-1188421-0-3", "Antrag Vollstreckungsbescheid", "21.06.2024", "14.06.2024", "Kr", "nein"],
            ["063/24", "Kaya", "AG Bielefeld FamG", "Auskunft Versorgungsausgleich", "15.08.2024", "08.08.2024", "Pe", "nein"],
        ],
    }),

    Dok(VERW + "Verguetungsvereinbarung_Muster.docx", "docx", "Muster", inhalt=[
        "# Vergütungsvereinbarung",
        "zwischen Rechtsanwälte Kröger & Petersen, Bielefeld (Rechtsanwälte)",
        "und ____________________________________ (Auftraggeber)",
        "",
        "## 1. Gegenstand",
        "Die Vereinbarung gilt für die Beratung und Vertretung in folgender Angelegenheit: "
        "_______________________.",
        "## 2. Stundenhonorar",
        "Die Vergütung erfolgt nach Zeitaufwand. Der Stundensatz beträgt für Partner 280,00 EUR "
        "und für angestellte Rechtsanwälte 220,00 EUR, jeweils zuzüglich gesetzlicher "
        "Umsatzsteuer. Abgerechnet wird im Takt von 15 Minuten; angefangene Einheiten werden "
        "anteilig berechnet.",
        "## 3. Auslagen",
        "Auslagen wie Reisekosten, Kopien und Gerichtskosten werden gesondert erstattet.",
        "## 4. Gesetzliche Vergütung",
        "Die vereinbarte Vergütung kann höher sein als die gesetzliche Vergütung nach dem RVG. "
        "Im Falle der Kostenerstattung erstattet die Gegenpartei, eine Behörde oder die "
        "Rechtsschutzversicherung regelmäßig nicht mehr als die gesetzliche Vergütung (§ 3a Abs. 1 Satz 3 RVG).",
        "## 5. Abrechnung",
        "Die Rechtsanwälte rechnen monatlich mit einer Aufstellung der erbrachten Tätigkeiten ab.",
        "",
        "Diese Vereinbarung bedarf der Textform und ist von der Vollmacht getrennt.",
    ]),

    Dok(VERW + "AVV_Cloudanbieter_unterschrieben.pdf", "pdf", "Vertrag", inhalt=[
        "# Vertrag über die Auftragsverarbeitung gemäß Art. 28 DSGVO",
        "zwischen Kröger & Petersen Rechtsanwälte (Verantwortlicher)",
        "und der Ostwestfalen IT-Service GmbH, Bielefeld (Auftragsverarbeiter)",
        "",
        "## § 1 Gegenstand und Dauer",
        "Der Auftragsverarbeiter betreibt für die Kanzlei die Server, die Datensicherung und",
        "das E-Mail-System. Der Vertrag gilt für die Dauer des Hauptvertrags vom 01.01.2024.",
        "## § 2 Art der Daten und betroffene Personen",
        "Mandantendaten, Daten von Gegnern und Zeugen, Beschäftigtendaten; darunter auch",
        "besondere Kategorien personenbezogener Daten nach Art. 9 DSGVO.",
        "## § 3 Verschwiegenheit",
        "Der Auftragsverarbeiter wird darauf hingewiesen, dass er an der beruflichen",
        "Schweigepflicht mitwirkt und sich bei unbefugter Offenbarung nach § 203 StGB strafbar",
        "machen kann. Er verpflichtet seine Mitarbeiter entsprechend (§ 43e BRAO).",
        "## § 4 Technische und organisatorische Maßnahmen",
        "Verschlüsselung der Daten bei Übertragung und Speicherung, Rechenzentrum in Deutschland,",
        "Zwei-Faktor-Anmeldung, tägliche Sicherung mit 30 Tagen Aufbewahrung, Protokollierung.",
        "## § 5 Unterauftragsverarbeiter",
        "Weitere Unterauftragsverarbeiter dürfen nur nach vorheriger schriftlicher Zustimmung",
        "der Kanzlei eingesetzt werden. Eine Verarbeitung außerhalb der EU ist ausgeschlossen.",
        "## § 6 Meldung von Datenschutzverletzungen",
        "Verletzungen des Schutzes personenbezogener Daten meldet der Auftragsverarbeiter",
        "unverzüglich, spätestens binnen 24 Stunden nach Bekanntwerden.",
    ]),

    Dok(VERW + "Schulung_ERV_2024.pptx", "pptx", "Schulung", inhalt=[
        ("Elektronischer Rechtsverkehr in der Kanzlei", ["Interne Schulung für Mitarbeitende",
                                                          "Kröger & Petersen, Februar 2024"]),
        ("Das beA", ["besonderes elektronisches Anwaltspostfach für jede zugelassene Anwältin und jeden Anwalt",
                     "Seit 2022 aktive Nutzungspflicht: Schriftsätze an Gerichte nur elektronisch (§ 130d ZPO)",
                     "Mitarbeiterrechte werden im beA-Webclient vergeben"]),
        ("Einreichen von Schriftsätzen", ["PDF durchsuchbar, keine eingebetteten Dateien",
                                          "Entweder qualifizierte elektronische Signatur",
                                          "oder einfache Signatur und Versand durch die Anwältin selbst",
                                          "Prüfprotokoll zur Akte nehmen"]),
        ("Empfangsbekenntnis", ["Gerichte stellen elektronisch gegen eEB zu (§ 173 ZPO)",
                                "eEB nur durch die Anwältin oder den Anwalt abgeben",
                                "Datum der Kenntnisnahme ist maßgeblich für den Fristbeginn",
                                "Frist sofort im Fristenkalender eintragen"]),
        ("Störungen", ["Bei technischer Störung Ersatzeinreichung nach § 130d Satz 2 ZPO",
                       "Störung glaubhaft machen, Screenshots sichern",
                       "Ansprechpartner: Ostwestfalen IT-Service"]),
    ]),
]
