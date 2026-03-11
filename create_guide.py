"""Erstellt die Anleitung als PDF (ANLEITUNG.pdf)."""
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER

W, H = A4
ACCENT  = colors.HexColor("#1a1a2e")
ACCENT2 = colors.HexColor("#2563eb")
LIGHT   = colors.HexColor("#f0f4ff")
GRAY    = colors.HexColor("#6b7280")
GREEN   = colors.HexColor("#15803d")
GREEN_BG= colors.HexColor("#f0fdf4")

styles = getSampleStyleSheet()

def sty(name, **kw):
    return ParagraphStyle(name, **kw)

TITLE   = sty("Title2",   fontName="Helvetica-Bold", fontSize=22, textColor=ACCENT,  spaceAfter=4,  leading=28)
SUBTITLE= sty("Sub",      fontName="Helvetica",      fontSize=11, textColor=GRAY,    spaceAfter=20, leading=16)
H1      = sty("H1",       fontName="Helvetica-Bold", fontSize=14, textColor=ACCENT,  spaceBefore=18, spaceAfter=6, leading=18)
H2      = sty("H2",       fontName="Helvetica-Bold", fontSize=11, textColor=ACCENT2, spaceBefore=10, spaceAfter=4, leading=14)
BODY    = sty("Body2",    fontName="Helvetica",      fontSize=10, textColor=colors.HexColor("#1f2937"), spaceAfter=6, leading=15)
SMALL   = sty("Small",    fontName="Helvetica",      fontSize=8.5,textColor=GRAY,    spaceAfter=4,  leading=12)
CODE    = sty("Code2",    fontName="Courier",        fontSize=9,  textColor=ACCENT,  spaceAfter=2,  leading=13,
              backColor=colors.HexColor("#f3f4f6"), borderPadding=4)
BULLET  = sty("Bullet2",  fontName="Helvetica",      fontSize=10, textColor=colors.HexColor("#1f2937"),
              leftIndent=16, spaceAfter=4, leading=14, bulletIndent=4)
NOTE    = sty("Note",     fontName="Helvetica-Oblique", fontSize=9, textColor=GREEN, spaceAfter=6, leading=13)


def step_table(num, title, lines):
    """Schritt-Box mit Nummer und Inhalt."""
    num_para  = Paragraph(f"<b>{num}</b>", sty("n", fontName="Helvetica-Bold", fontSize=13, textColor=colors.white, alignment=TA_CENTER))
    body_parts= [Paragraph(f"<b>{title}</b>", sty("t", fontName="Helvetica-Bold", fontSize=10.5, textColor=ACCENT, spaceAfter=3, leading=14))]
    for l in lines:
        body_parts.append(Paragraph(f"• {l}", BULLET))

    t = Table(
        [[num_para, body_parts]],
        colWidths=[1.1*cm, None],
    )
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(0,0), ACCENT),
        ("BACKGROUND",    (1,0),(1,0), LIGHT),
        ("VALIGN",        (0,0),(-1,-1), "TOP"),
        ("ALIGN",         (0,0),(0,0), "CENTER"),
        ("TOPPADDING",    (0,0),(0,0), 10),
        ("BOTTOMPADDING", (0,0),(-1,-1), 10),
        ("LEFTPADDING",   (1,0),(1,0), 10),
        ("RIGHTPADDING",  (1,0),(1,0), 10),
        ("ROUNDEDCORNERS",(0,0),(-1,-1), [4,4,4,4]),
    ]))
    return t


def info_box(text, bg=LIGHT, fg=ACCENT2):
    t = Table([[Paragraph(text, sty("ib", fontName="Helvetica", fontSize=9.5, textColor=fg, leading=14))]])
    t.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,-1), bg),
        ("LEFTPADDING",  (0,0),(-1,-1), 10),
        ("RIGHTPADDING", (0,0),(-1,-1), 10),
        ("TOPPADDING",   (0,0),(-1,-1), 8),
        ("BOTTOMPADDING",(0,0),(-1,-1), 8),
    ]))
    return t


def build():
    doc = SimpleDocTemplate(
        "ANLEITUNG.pdf",
        pagesize=A4,
        leftMargin=2.2*cm, rightMargin=2.2*cm,
        topMargin=2.2*cm,  bottomMargin=2.2*cm,
        title="ConnectCAD Device Tool — Anleitung",
        author="ConnectCAD Device Tool",
    )

    story = []

    # ── Titelblock ────────────────────────────────────────────────────────────
    story.append(Paragraph("ConnectCAD Device Tool", TITLE))
    story.append(Paragraph("Benutzeranleitung · Vectorworks 2026 / ConnectCAD 2026", SUBTITLE))
    story.append(HRFlowable(width="100%", thickness=1, color=ACCENT, spaceAfter=18))

    # ── Überblick ─────────────────────────────────────────────────────────────
    story.append(Paragraph("Überblick", H1))
    story.append(Paragraph(
        "Dieses Tool ermöglicht es, AV-, IT- und Broadcast-Geräte online zu suchen, "
        "die technischen Daten automatisch per KI zu extrahieren und direkt als "
        "ConnectCAD-kompatibles Worksheet (CSV oder Excel) zu exportieren.",
        BODY
    ))
    story.append(Paragraph(
        "Der Export ist auf den <b>Vectorworks 2026 / ConnectCAD 2026</b>-Workflow abgestimmt. "
        "Die Datei wird über <i>File → Import → Import Worksheet</i> in Vectorworks eingelesen "
        "und anschließend mit <i>ConnectCAD → Update → Create Devices from Worksheet</i> verarbeitet.",
        BODY
    ))

    # ── Voraussetzungen ───────────────────────────────────────────────────────
    story.append(Paragraph("Voraussetzungen", H1))

    reqs = [
        ["", "Was", "Wo bekommt man es"],
        ["✓", "Python 3.9+", "python.org/downloads (kostenlos)"],
        ["✓", "Anthropic API Key", "console.anthropic.com → API Keys"],
        ["○", "SerpAPI Key", "serpapi.com (optional, für bessere Suche)"],
    ]
    rt = Table(reqs, colWidths=[0.7*cm, 4.5*cm, None])
    rt.setStyle(TableStyle([
        ("BACKGROUND",   (0,0),(-1,0), ACCENT),
        ("TEXTCOLOR",    (0,0),(-1,0), colors.white),
        ("FONTNAME",     (0,0),(-1,0), "Helvetica-Bold"),
        ("FONTSIZE",     (0,0),(-1,-1), 9.5),
        ("FONTNAME",     (0,1),(-1,-1), "Helvetica"),
        ("ROWBACKGROUNDS",(0,1),(-1,-1), [colors.white, colors.HexColor("#f9fafb")]),
        ("GRID",         (0,0),(-1,-1), 0.5, colors.HexColor("#e5e7eb")),
        ("LEFTPADDING",  (0,0),(-1,-1), 8),
        ("RIGHTPADDING", (0,0),(-1,-1), 8),
        ("TOPPADDING",   (0,0),(-1,-1), 6),
        ("BOTTOMPADDING",(0,0),(-1,-1), 6),
        ("ALIGN",        (0,0),(0,-1), "CENTER"),
    ]))
    story.append(rt)
    story.append(Spacer(1, 6))
    story.append(Paragraph("✓ = Pflicht · ○ = Optional (Fallback: DuckDuckGo)", SMALL))

    # ── Installation ──────────────────────────────────────────────────────────
    story.append(Paragraph("Installation (einmalig)", H1))
    story.append(info_box(
        "ℹ️  Keine Admin-Rechte erforderlich. Alle Pakete werden lokal im Projektordner installiert."
    ))
    story.append(Spacer(1, 8))

    story.append(KeepTogether([
        step_table("1", "Repository herunterladen",
            ["Terminal öffnen (Spotlight: 'Terminal')",
             "git clone https://github.com/BW2030/connectcad-tool.git",
             "cd connectcad-tool"]),
        Spacer(1, 8),
        step_table("2", "API Key eintragen",
            ["cp .env.example .env",
             "Datei .env mit TextEdit öffnen",
             "ANTHROPIC_API_KEY=sk-ant-... eintragen und speichern"]),
        Spacer(1, 8),
        step_table("3", "Tool starten",
            ["START.command doppelklicken",
             "Beim ersten Start: Pakete werden automatisch geladen (~30 Sek.)",
             "Browser öffnet sich automatisch auf http://localhost:8000"]),
    ]))

    # ── Bedienung ─────────────────────────────────────────────────────────────
    story.append(Paragraph("Bedienung — Schritt für Schritt", H1))

    story.append(Paragraph("Schritt 1 — Gerät suchen", H2))
    story.append(Paragraph(
        "Produktbezeichnung in das Suchfeld eingeben, z.B. <i>Yamaha QL5</i> oder "
        "<i>Sony BRC-X400</i>. Mit Enter oder Klick auf «Suchen» starten. "
        "Das Tool liefert 3–5 Produktseiten als Ergebnis.",
        BODY
    ))

    story.append(Paragraph("Schritt 2 — Produktseite auswählen", H2))
    story.append(Paragraph(
        "Eine Seite aus der Liste anklicken (z.B. die offizielle Herstellerseite "
        "oder eine Händlerseite mit vollständigen Specs). Dann «Mit Claude analysieren» klicken.",
        BODY
    ))

    story.append(Paragraph("Schritt 3 — Daten extrahieren", H2))
    story.append(Paragraph(
        "Die KI (Claude) liest die Produktseite und extrahiert automatisch: "
        "Hersteller, Modell, Rack-Höhe, Abmessungen und alle Ein-/Ausgänge (Sockets). "
        "Dieser Schritt dauert ca. 10–20 Sekunden.",
        BODY
    ))

    story.append(Paragraph("Schritt 4 — Vorschau prüfen und korrigieren", H2))
    story.append(Paragraph(
        "Alle extrahierten Felder werden angezeigt und können manuell bearbeitet werden. "
        "Sockets können ergänzt, geändert oder gelöscht werden.",
        BODY
    ))

    story.append(Paragraph("Schritt 5 — Export", H2))
    story.append(Paragraph(
        "Optionale Felder ausfüllen (Raum, Rack, Rack U), dann herunterladen:",
        BODY
    ))
    for line in [
        "<b>CSV für ConnectCAD 2026</b> — Empfohlenes Format für Vectorworks 2026",
        "<b>Excel (.xlsx)</b> — Alternativ, ebenfalls kompatibel",
    ]:
        story.append(Paragraph(f"• {line}", BULLET))

    # ── Import in Vectorworks ─────────────────────────────────────────────────
    story.append(Paragraph("Import in Vectorworks 2026", H1))
    story.append(info_box(
        "⚠️  In ConnectCAD 2026 sind Gerätedefinitionen (inkl. Sockets) in 3D-Symbolen "
        "in der Resource Manager gespeichert. Das Worksheet verknüpft nur Make + Model "
        "mit bestehenden Symbolen.",
        bg=colors.HexColor("#fffbeb"), fg=colors.HexColor("#92400e")
    ))
    story.append(Spacer(1, 8))

    vw_steps = [
        "Vectorworks öffnen",
        "File → Import → Import Worksheet → CSV-Datei auswählen",
        "ConnectCAD → Update → Create Devices from Worksheet",
        "Spalten zuordnen (Make, Model, Qty …) → OK",
        "Wenn ein Gerät nicht in der Symboldatenbank gefunden wird: "
        "Device Mapping Dialog öffnet sich → passendes Symbol wählen",
    ]
    for i, s in enumerate(vw_steps, 1):
        story.append(Paragraph(f"<b>{i}.</b> {s}", BULLET))

    # ── Häufige Probleme ──────────────────────────────────────────────────────
    story.append(Paragraph("Häufige Probleme", H1))

    problems = [
        ("Keine Suchergebnisse",
         "Anderen Suchbegriff versuchen, z.B. nur Modellnummer. "
         "Bei anhaltenden Problemen SerpAPI Key verwenden (bessere Ergebnisse)."),
        ("Extraktion schlägt fehl",
         "Seite ist möglicherweise durch JavaScript geschützt. "
         "Eine andere Produktseite (z.B. Hersteller statt Händler) auswählen."),
        ("API Key Fehler",
         "Anthropic API Key in der .env-Datei prüfen. "
         "Muss mit 'sk-ant-' beginnen. Guthaben unter console.anthropic.com prüfen."),
        ("Port 8000 belegt",
         "In START.command --port 8000 zu --port 8001 ändern, "
         "und Browser auf http://localhost:8001 öffnen."),
        ("Browser öffnet sich nicht",
         "Manuell im Browser öffnen: http://localhost:8000"),
    ]
    for prob, sol in problems:
        story.append(KeepTogether([
            Paragraph(f"<b>{prob}</b>", sty("ph", fontName="Helvetica-Bold", fontSize=10,
                      textColor=colors.HexColor("#dc2626"), spaceAfter=2, leading=14)),
            Paragraph(sol, sty("ps", fontName="Helvetica", fontSize=9.5,
                      textColor=colors.HexColor("#374151"), spaceAfter=8, leading=14, leftIndent=8)),
        ]))

    # ── Update ────────────────────────────────────────────────────────────────
    story.append(Paragraph("Tool aktualisieren", H1))
    story.append(Paragraph("Im Projektordner im Terminal:", BODY))
    for cmd in ["git pull", "# Dann START.command neu starten"]:
        story.append(Paragraph(cmd, CODE))

    # ── Footer ────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#d1d5db"), spaceAfter=8))
    story.append(Paragraph(
        "ConnectCAD Device Tool · github.com/BW2030/connectcad-tool · "
        "Vectorworks® und ConnectCAD® sind eingetragene Marken von Nemetschek Group.",
        SMALL
    ))

    doc.build(story)
    print("✓ ANLEITUNG.pdf erstellt")


if __name__ == "__main__":
    build()
