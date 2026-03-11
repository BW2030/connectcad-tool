"""ConnectCAD Device Tool — FastAPI backend."""
import os
import re
import ipaddress
import logging
import socket
import threading
import tempfile
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

from scraper import search_duckduckgo, search_serpapi, fetch_page_text
from extractor import extract_device_data
from formatter import build_rows, to_csv, to_tab_delimited, to_excel_bytes

load_dotenv()
logger = logging.getLogger("connectcad")

# ── Config (thread-safe) ─────────────────────────────────────────────────────

class _Config:
    _lock = threading.Lock()
    _anthropic_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    _serpapi_key: str   = os.getenv("SERPAPI_KEY", "")
    _env_path: Path     = Path(__file__).parent / ".env"

    @classmethod
    def anthropic_key(cls) -> str:
        with cls._lock:
            return cls._anthropic_key

    @classmethod
    def serpapi_key(cls) -> str:
        with cls._lock:
            return cls._serpapi_key

    @classmethod
    def save_anthropic_key(cls, key: str) -> None:
        with cls._lock:
            env = cls._env_path
            lines = env.read_text(encoding="utf-8").splitlines() if env.exists() else []
            lines = [l for l in lines if not l.startswith("ANTHROPIC_API_KEY=")]
            lines.append(f"ANTHROPIC_API_KEY={key}")
            # Atomic write
            fd, tmp = tempfile.mkstemp(dir=env.parent)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write("\n".join(lines) + "\n")
                Path(tmp).replace(env)
            except Exception:
                Path(tmp).unlink(missing_ok=True)
                raise
            cls._anthropic_key = key

cfg = _Config()

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="ConnectCAD Device Tool", version="1.0.0", docs_url=None, redoc_url=None)

# CORS: nur localhost erlauben (lokales Tool)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# Security Headers
class SecurityHeaders(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        resp = await call_next(request)
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
        return resp

app.add_middleware(SecurityHeaders)

# ── Validation helpers ────────────────────────────────────────────────────────

_QUERY_RE = re.compile(r'^[\w\s\-\.\(\)/äöüßÄÖÜéàèê]+$', re.UNICODE)

def _validate_query(q: str) -> str:
    q = q.strip()
    if not q:
        raise HTTPException(400, "Suchbegriff darf nicht leer sein.")
    if len(q) > 200:
        raise HTTPException(400, "Suchbegriff zu lang (max. 200 Zeichen).")
    if not _QUERY_RE.match(q):
        raise HTTPException(400, "Suchbegriff enthält ungültige Zeichen.")
    return q

def _validate_url(url: str) -> str:
    """SSRF-Schutz: nur öffentliche HTTP/HTTPS URLs erlaubt."""
    try:
        p = urlparse(url)
    except Exception:
        raise HTTPException(400, "Ungültige URL.")

    if p.scheme not in ("http", "https"):
        raise HTTPException(400, "Nur HTTP/HTTPS URLs sind erlaubt.")

    hostname = p.hostname or ""
    if not hostname:
        raise HTTPException(400, "URL ohne Hostname.")

    # Direkte IP-Prüfung
    try:
        ip = ipaddress.ip_address(hostname)
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
            raise HTTPException(400, "Private/lokale Adressen sind nicht erlaubt.")
    except ValueError:
        # Hostname → DNS auflösen und IP prüfen
        try:
            resolved = socket.gethostbyname(hostname)
            ip = ipaddress.ip_address(resolved)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved:
                raise HTTPException(400, "Diese URL zeigt auf eine private Adresse.")
        except HTTPException:
            raise
        except Exception:
            pass  # DNS-Fehler → Netzwerk-Layer handelt es ab

    return url

def _validate_api_key(key: str) -> str:
    if not key or not key.startswith("sk-"):
        raise HTTPException(400, "Ungültiger API Key (muss mit 'sk-' beginnen).")
    if len(key) > 300:
        raise HTTPException(400, "API Key zu lang.")
    return key

# ── Models ────────────────────────────────────────────────────────────────────

class SaveKeyRequest(BaseModel):
    anthropic_api_key: str

class ExtractRequest(BaseModel):
    url: str
    anthropic_api_key: Optional[str] = None

class ExportRequest(BaseModel):
    device: dict
    qty: int = 1
    room: str = ""
    rack: str = ""
    rack_u: str = ""
    format: str = "csv"

# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root():
    with open(Path(__file__).parent / "templates" / "index.html", encoding="utf-8") as f:
        return f.read()


@app.get("/keycheck")
async def keycheck():
    """Nur boolean — kein Key-Inhalt wird zurückgegeben."""
    return {"saved": bool(cfg.anthropic_key())}


@app.post("/savekey")
async def savekey(req: SaveKeyRequest):
    """Speichert API Key sicher in .env (atomarer Schreibvorgang)."""
    _validate_api_key(req.anthropic_api_key)
    try:
        cfg.save_anthropic_key(req.anthropic_api_key)
    except Exception:
        logger.exception("Fehler beim Speichern des API Keys")
        raise HTTPException(500, "API Key konnte nicht gespeichert werden.")
    return {"ok": True}


@app.get("/search")
async def search(q: str = Query(...)):
    """Produktseiten suchen."""
    q = _validate_query(q)
    try:
        key = cfg.serpapi_key()
        if key:
            results = await search_serpapi(q, key)
        else:
            results = await search_duckduckgo(q)
    except Exception:
        logger.exception("Suche fehlgeschlagen für Query: %s", q[:50])
        raise HTTPException(502, "Suche fehlgeschlagen. Bitte erneut versuchen.")
    return {"results": results}


@app.post("/extract")
async def extract(req: ExtractRequest):
    """Produktseite abrufen und Gerätedaten per Claude extrahieren."""
    # SSRF-Schutz
    _validate_url(req.url)

    # API Key: Client-Key nur wenn kein Server-Key vorhanden
    api_key = cfg.anthropic_key() or req.anthropic_api_key
    if not api_key:
        raise HTTPException(400, "Kein Anthropic API Key konfiguriert.")
    _validate_api_key(api_key)

    try:
        page_text = await fetch_page_text(req.url)
    except ValueError as e:
        raise HTTPException(403, str(e))
    except Exception:
        logger.exception("Seite konnte nicht geladen werden: %s", req.url)
        raise HTTPException(502, "Seite konnte nicht geladen werden.")

    if len(page_text) < 50:
        raise HTTPException(422, "Seiteninhalt zu kurz. Bitte eine andere Seite wählen.")

    try:
        device = extract_device_data(page_text, api_key)
    except Exception:
        logger.exception("Claude-Extraktion fehlgeschlagen")
        raise HTTPException(500, "Extraktion fehlgeschlagen. Bitte erneut versuchen.")

    return {"device": device}


@app.post("/export")
async def export(req: ExportRequest):
    """ConnectCAD 2026 Worksheet exportieren (CSV oder XLSX)."""
    if req.format not in ("csv", "xlsx", "txt"):
        raise HTTPException(400, "Ungültiges Format.")
    if not isinstance(req.qty, int) or not (1 <= req.qty <= 9999):
        raise HTTPException(400, "Qty muss zwischen 1 und 9999 liegen.")

    rows = build_rows(req.device, qty=req.qty, room=req.room, rack=req.rack, rack_u=req.rack_u)

    if req.format == "xlsx":
        content = to_excel_bytes(rows)
        return Response(
            content=content,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": "attachment; filename=connectcad_import.xlsx"},
        )
    elif req.format == "txt":
        content = to_tab_delimited(rows)
        return Response(
            content=content.encode("utf-8"),
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=connectcad_import.txt"},
        )
    else:
        content = to_csv(rows)
        return Response(
            content=content.encode("utf-8-sig"),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=connectcad_import.csv"},
        )
