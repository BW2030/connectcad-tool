"""Extract structured device data from product page text using Claude API."""
import json
import re
import anthropic

SYSTEM_PROMPT = """You are an AV/IT/Broadcast equipment specialist.
Extract device specifications from product page text and return ONLY a JSON object.

ConnectCAD socket format:
- Each socket: {"direction": "IN"|"OUT"|"IO", "signal": "<signal>", "connector": "<connector>", "label": "<label>", "qty": <int>}
- Directions: IN = input, OUT = output, IO = bidirectional
- Common signals: Audio, Video, Data, Power, Control, Networking, AES, MADI, DANTE, AVB
- Common connectors: XLR, TRS, TS, RCA, BNC, HDMI, DisplayPort, VGA, DVI, RJ45, USB-A, USB-B, USB-C, SFP, DB9, DB25, Speakon, etherCON, opticalCON, SC, LC, IEC, powerCON

Return JSON with this exact structure:
{
  "make": "string",
  "model": "string",
  "device_type": "Physical" | "Virtual",
  "rack_units": number | null,
  "width_mm": number | null,
  "depth_mm": number | null,
  "description": "string",
  "sockets": [
    {"direction": "IN", "signal": "Audio", "connector": "XLR", "label": "Mic/Line In", "qty": 8}
  ]
}

If a value is unknown, use null. Group identical sockets by qty. Be precise with connector types."""

USER_TEMPLATE = """Product page text:
---
{text}
---

Extract all specifications and I/O connections as ConnectCAD JSON."""


def extract_device_data(page_text: str, api_key: str) -> dict:
    """Call Claude API to extract structured device data from page text."""
    client = anthropic.Anthropic(api_key=api_key)

    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": USER_TEMPLATE.format(text=page_text)}
            ],
        )
    except anthropic.AuthenticationError:
        raise ValueError("Ungültiger API Key. Bitte prüfe deinen Anthropic API Key.")
    except anthropic.BadRequestError as e:
        msg = str(e)
        if "credit balance" in msg or "too low" in msg:
            raise ValueError(
                "Kein Guthaben auf dem Anthropic-Konto. "
                "Bitte unter console.anthropic.com/settings/billing Credits kaufen."
            )
        raise ValueError(f"API Fehler: {msg[:200]}")
    except anthropic.RateLimitError:
        raise ValueError("Rate Limit erreicht. Bitte kurz warten und erneut versuchen.")
    except Exception as e:
        raise ValueError(f"Claude API nicht erreichbar: {e}")

    raw = message.content[0].text.strip()
    json_match = re.search(r"\{[\s\S]*\}", raw)
    if not json_match:
        raise ValueError(f"Kein JSON in Claude-Antwort gefunden: {raw[:200]}")

    data = json.loads(json_match.group())
    return _validate_and_normalize(data)


def _validate_and_normalize(data: dict) -> dict:
    """Ensure all required fields exist with sensible defaults."""
    data.setdefault("make", "Unknown")
    data.setdefault("model", "Unknown")
    data.setdefault("device_type", "Physical")
    data.setdefault("rack_units", None)
    data.setdefault("width_mm", None)
    data.setdefault("depth_mm", None)
    data.setdefault("description", "")
    data.setdefault("sockets", [])

    # Normalize sockets
    normalized_sockets = []
    for s in data["sockets"]:
        normalized_sockets.append({
            "direction": s.get("direction", "IO"),
            "signal": s.get("signal", ""),
            "connector": s.get("connector", ""),
            "label": s.get("label", ""),
            "qty": int(s.get("qty", 1)),
        })
    data["sockets"] = normalized_sockets
    return data
