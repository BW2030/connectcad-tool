#!/bin/bash
# Doppelklick um das Tool zu starten
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

# Pakete installieren (nur beim ersten Start)
echo "Abhängigkeiten prüfen…"
python3 -m pip install -q -r requirements.txt

# Browser öffnen (kurz warten bis Server läuft)
sleep 2 && open "http://localhost:8000" &

echo ""
echo "✓ Tool läuft unter: http://localhost:8000"
echo "  (Fenster offen lassen — Strg+C zum Beenden)"
echo ""

# Server starten
PATH="$HOME/Library/Python/3.9/bin:$HOME/Library/Python/3.11/bin:$HOME/Library/Python/3.12/bin:/usr/local/bin:$PATH"
python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
