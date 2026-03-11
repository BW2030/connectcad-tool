"""ConnectCAD Device Tool — FastAPI backend."""
import os
import json
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, Response, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

from scraper import search_duckduckgo, search_serpapi, fetch_page_text
from extractor import extract_device_data
from formatter import build_rows, to_csv, to_tab_delimited, to_excel_bytes

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")

app = FastAPI(title="ConnectCAD Device Tool", version="1.0.0")


# ── Models ──────────────────────────────────────────────────────────────────

class ExtractRequest(BaseModel):
    url: str
    anthropic_api_key: Optional[str] = None


class ExportRequest(BaseModel):
    device: dict
    qty: int = 1
    room: str = ""
    rack: str = ""
    rack_u: str = ""
    format: str = "csv"  # "csv", "xlsx", or "txt" (legacy)


# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root():
    with open("templates/index.html", encoding="utf-8") as f:
        return f.read()


@app.get("/search")
async def search(
    q: str = Query(..., description="Device search query"),
    serpapi_key: Optional[str] = Query(None),
):
    """Search for product pages matching the query."""
    if not q.strip():
        raise HTTPException(400, "Query must not be empty")

    key = serpapi_key or SERPAPI_KEY
    try:
        if key:
            results = await search_serpapi(q, key)
        else:
            results = await search_duckduckgo(q)
    except Exception as e:
        raise HTTPException(502, f"Search failed: {e}")

    return {"results": results}


@app.post("/extract")
async def extract(req: ExtractRequest):
    """Fetch a product page and extract ConnectCAD device data via Claude."""
    api_key = req.anthropic_api_key or ANTHROPIC_API_KEY
    if not api_key:
        raise HTTPException(400, "Anthropic API key required. Set ANTHROPIC_API_KEY or pass it in the request.")

    try:
        page_text = await fetch_page_text(req.url)
    except ValueError as e:
        raise HTTPException(403, str(e))
    except Exception as e:
        raise HTTPException(502, f"Seite konnte nicht geladen werden: {e}")

    if len(page_text) < 50:
        raise HTTPException(422, "Seiteninhalt zu kurz. Bitte eine andere Seite wählen.")

    try:
        device = extract_device_data(page_text, api_key)
    except Exception as e:
        raise HTTPException(500, f"Extraction failed: {e}")

    return {"device": device}


@app.post("/export")
async def export(req: ExportRequest):
    """Generate a ConnectCAD 2026 worksheet file (CSV or XLSX)."""
    rows = build_rows(req.device, qty=req.qty, room=req.room, rack=req.rack, rack_u=req.rack_u)

    if req.format == "xlsx":
        content = to_excel_bytes(rows)
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=connectcad_import.xlsx"},
        )
    elif req.format == "txt":
        # Legacy tab-delimited (VW < 2026)
        content = to_tab_delimited(rows)
        return Response(
            content=content.encode("utf-8"),
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=connectcad_import.txt"},
        )
    else:
        # CSV — Standard für VW 2026
        content = to_csv(rows)
        return Response(
            content=content.encode("utf-8-sig"),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=connectcad_import.csv"},
        )
