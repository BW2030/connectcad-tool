#!/bin/bash
# Doppelklick zum Starten — keine Admin-Rechte nötig
cd "$(dirname "$0")"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ConnectCAD Device Tool"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Python prüfen
if ! command -v python3 &>/dev/null; then
  echo "FEHLER: Python 3 nicht gefunden."
  echo "Bitte installieren: https://www.python.org/downloads/"
  read -p "Enter drücken zum Beenden…"
  exit 1
fi

# Virtuelle Umgebung anlegen (nur beim ersten Start)
if [ ! -d ".venv" ]; then
  echo "Erstelle virtuelle Umgebung…"
  python3 -m venv .venv
fi

# Pakete installieren (nur beim ersten Start oder nach Update)
echo "Abhängigkeiten prüfen…"
.venv/bin/pip install -q -r requirements.txt

# Browser öffnen (kurz warten bis Server läuft)
sleep 2 && open "http://localhost:8000" &

echo ""
echo "✓ Tool läuft unter: http://localhost:8000"
echo "  (Fenster offen lassen — Strg+C zum Beenden)"
echo ""

# Server starten
.venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000
