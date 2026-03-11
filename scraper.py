"""Web scraping: find product pages and fetch content."""
import httpx
import asyncio
import random
from bs4 import BeautifulSoup
from urllib.parse import quote_plus, urlparse

# Bekannte Seiten die immer blocken → direkt überspringen
BLOCKED_DOMAINS = {
    "bhphotovideo.com", "adorama.com", "amazon.com", "amazon.de",
    "ebay.com", "ebay.de", "walmart.com", "bestbuy.com",
}

# Realistischer Browser-Header-Pool
USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

TIMEOUT = 20.0


def _browser_headers(url: str = "") -> dict:
    """Vollständige Browser-ähnliche Header um Blocking zu vermeiden."""
    host = urlparse(url).netloc if url else ""
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
        **({"Referer": f"https://www.google.com/search?q={quote_plus(host)}"} if host else {}),
    }


def _is_blocked_domain(url: str) -> bool:
    host = urlparse(url).netloc.lstrip("www.")
    return any(host == d or host.endswith("." + d) for d in BLOCKED_DOMAINS)


async def search_duckduckgo(query: str, max_results: int = 5) -> list[dict]:
    """Search DuckDuckGo HTML, filtert bekannte Blocker-Seiten."""
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query + ' specifications site specs')}"
    async with httpx.AsyncClient(headers=_browser_headers(), timeout=TIMEOUT, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")
    results = []
    for result in soup.select(".result"):
        if len(results) >= max_results:
            break
        title_el = result.select_one(".result__title a")
        snippet_el = result.select_one(".result__snippet")
        if not title_el:
            continue
        href = title_el.get("href", "")
        real_url = _extract_ddg_url(href)
        if not real_url:
            continue
        # Bekannte Blocker-Domains überspringen
        if _is_blocked_domain(real_url):
            continue
        results.append({
            "title": title_el.get_text(strip=True),
            "url": real_url,
            "snippet": snippet_el.get_text(strip=True) if snippet_el else "",
        })
    return results


async def search_serpapi(query: str, api_key: str, max_results: int = 5) -> list[dict]:
    """Search via SerpAPI (Google). Requires SERPAPI_KEY."""
    params = {
        "q": query + " specifications",
        "api_key": api_key,
        "num": max_results + 3,  # Mehr holen, da wir filtern
        "engine": "google",
    }
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get("https://serpapi.com/search", params=params)
        resp.raise_for_status()

    data = resp.json()
    results = []
    for item in data.get("organic_results", []):
        if len(results) >= max_results:
            break
        url = item.get("link", "")
        if _is_blocked_domain(url):
            continue
        results.append({
            "title": item.get("title", ""),
            "url": url,
            "snippet": item.get("snippet", ""),
        })
    return results


async def fetch_page_text(url: str) -> str:
    """
    Seite abrufen mit mehreren Fallback-Strategien:
    1. Direkter Abruf mit Browser-Headern
    2. Bei 403: Google Cache versuchen
    3. Bei 403: Fehlermeldung mit Hinweis auf alternative Seite
    """
    # Direkter Versuch
    try:
        text = await _fetch_direct(url)
        if text and len(text) > 100:
            return text
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 403:
            # Google Cache versuchen
            try:
                text = await _fetch_google_cache(url)
                if text and len(text) > 100:
                    return text
            except Exception:
                pass
            raise ValueError(
                f"Diese Seite blockiert automatische Anfragen (403 Forbidden).\n\n"
                f"Bitte eine andere Seite wählen, z.B.:\n"
                f"• Offizielle Herstellerseite (z.B. sony.com, yamaha.com)\n"
                f"• Manuals.plus, manualslib.com\n"
                f"• Sweetwater.com (meist zugänglich)\n"
                f"• ProSoundWeb, AVNetwork, Crutchfield"
            )
        raise
    except Exception as e:
        raise ValueError(f"Seite konnte nicht geladen werden: {e}")

    raise ValueError("Seiteninhalt zu kurz oder leer.")


async def _fetch_direct(url: str) -> str:
    """Direkter HTTP-Abruf mit realistischen Headern."""
    headers = _browser_headers(url)
    async with httpx.AsyncClient(
        headers=headers,
        timeout=TIMEOUT,
        follow_redirects=True,
        # Cookie-Jar aktivieren für Seiten die Session-Cookies brauchen
        cookies={},
    ) as client:
        # Erst Startseite besuchen (simuliert echten Browser-Weg)
        parsed = urlparse(url)
        home = f"{parsed.scheme}://{parsed.netloc}"
        try:
            await client.get(home, timeout=8.0)
        except Exception:
            pass
        await asyncio.sleep(random.uniform(0.3, 0.8))

        resp = await client.get(url)
        resp.raise_for_status()

    return _parse_html(resp.text)


async def _fetch_google_cache(url: str) -> str:
    """Google Cache als Fallback für geblockte Seiten."""
    cache_url = f"https://webcache.googleusercontent.com/search?q=cache:{quote_plus(url)}"
    headers = _browser_headers()
    async with httpx.AsyncClient(headers=headers, timeout=TIMEOUT, follow_redirects=True) as client:
        resp = await client.get(cache_url)
        resp.raise_for_status()
    return _parse_html(resp.text)


def _parse_html(html: str) -> str:
    """HTML zu sauberem Text für Claude."""
    soup = BeautifulSoup(html, "lxml")

    # Unnötige Tags entfernen
    for tag in soup(["script", "style", "nav", "footer", "header",
                     "aside", "noscript", "iframe", "svg", "form"]):
        tag.decompose()

    # Beste Inhaltsregionen priorisieren
    for selector in [
        "main", "article",
        "[class*='spec']", "[class*='product']", "[id*='spec']", "[id*='product']",
        "[class*='detail']", "[id*='detail']",
        ".content", "#content", ".page-content",
    ]:
        el = soup.select_one(selector)
        if el:
            text = el.get_text(separator="\n", strip=True)
            if len(text) > 300:
                return _clean_text(text)

    return _clean_text(soup.get_text(separator="\n", strip=True))


def _extract_ddg_url(href: str) -> str:
    if href.startswith("http"):
        return href
    import re
    from urllib.parse import unquote
    match = re.search(r"uddg=([^&]+)", href)
    return unquote(match.group(1)) if match else ""


def _clean_text(text: str) -> str:
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    result, prev_blank = [], False
    for line in lines:
        if not line:
            if not prev_blank:
                result.append(line)
            prev_blank = True
        else:
            result.append(line)
            prev_blank = False
    return "\n".join(result)[:12000]
