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

USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

TIMEOUT = 20.0


def _browser_headers() -> dict:
    """Browser-ähnliche Headers — KEIN brotli (br) da httpx es nicht dekodiert)."""
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "gzip, deflate",   # kein br → httpx dekodiert gzip/deflate nativ
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    }


def _is_blocked_domain(url: str) -> bool:
    host = urlparse(url).netloc.lstrip("www.")
    return any(host == d or host.endswith("." + d) for d in BLOCKED_DOMAINS)


# ── Suche ─────────────────────────────────────────────────────────────────────

async def search_duckduckgo(query: str, max_results: int = 5) -> list[dict]:
    """DuckDuckGo Lite — einfacheres HTML, weniger Bot-Detection."""
    url = f"https://lite.duckduckgo.com/lite/?q={quote_plus(query + ' specifications')}"
    async with httpx.AsyncClient(
        headers=_browser_headers(), timeout=TIMEOUT, follow_redirects=True
    ) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")
    results = []

    # DuckDuckGo Lite: Ergebnisse in <a class="result-link"> + <td class="result-snippet">
    links    = soup.select("a.result-link")
    snippets = soup.select("td.result-snippet")

    for i, link in enumerate(links):
        if len(results) >= max_results:
            break
        href = link.get("href", "")
        if not href.startswith("http"):
            continue
        if _is_blocked_domain(href):
            continue
        results.append({
            "title":   link.get_text(strip=True),
            "url":     href,
            "snippet": snippets[i].get_text(strip=True) if i < len(snippets) else "",
        })

    # Fallback: Bing wenn DuckDuckGo leer
    if not results:
        results = await _search_bing(query, max_results)

    return results


async def _search_bing(query: str, max_results: int = 5) -> list[dict]:
    """Bing HTML-Suche als Fallback."""
    url = f"https://www.bing.com/search?q={quote_plus(query + ' specifications')}&count=10"
    headers = _browser_headers()
    headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

    async with httpx.AsyncClient(headers=headers, timeout=TIMEOUT, follow_redirects=True) as client:
        resp = await client.get(url)
        if resp.status_code != 200:
            return []

    soup = BeautifulSoup(resp.text, "lxml")
    results = []
    for item in soup.select("li.b_algo"):
        if len(results) >= max_results:
            break
        a = item.select_one("h2 a")
        snip = item.select_one(".b_caption p, p")
        if not a:
            continue
        href = a.get("href", "")
        if not href.startswith("http") or _is_blocked_domain(href):
            continue
        results.append({
            "title":   a.get_text(strip=True),
            "url":     href,
            "snippet": snip.get_text(strip=True) if snip else "",
        })
    return results


async def search_serpapi(query: str, api_key: str, max_results: int = 5) -> list[dict]:
    """Search via SerpAPI (Google)."""
    params = {
        "q": query + " specifications",
        "api_key": api_key,
        "num": max_results + 3,
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
            "title":   item.get("title", ""),
            "url":     url,
            "snippet": item.get("snippet", ""),
        })
    return results


# ── Seiteninhalt abrufen ──────────────────────────────────────────────────────

async def fetch_page_text(url: str) -> str:
    """Produktseite abrufen. Bei 403 → Google Cache versuchen."""
    try:
        text = await _fetch_direct(url)
        if text and len(text) > 100:
            return text
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 403:
            try:
                text = await _fetch_google_cache(url)
                if text and len(text) > 100:
                    return text
            except Exception:
                pass
            raise ValueError(
                "Diese Seite blockiert automatische Anfragen (403 Forbidden).\n\n"
                "Bitte eine andere Seite wählen, z.B.:\n"
                "• Offizielle Herstellerseite (sony.com, yamaha.com)\n"
                "• Sweetwater.com\n"
                "• Manualslib.com\n"
                "• ProSoundWeb, AVNetwork, Crutchfield"
            )
        raise ValueError(f"HTTP-Fehler: {e.response.status_code}")
    except Exception as e:
        raise ValueError(f"Seite konnte nicht geladen werden: {e}")

    raise ValueError("Seiteninhalt zu kurz oder leer.")


async def _fetch_direct(url: str) -> str:
    headers = _browser_headers()
    headers["Referer"] = f"{urlparse(url).scheme}://{urlparse(url).netloc}/"
    async with httpx.AsyncClient(
        headers=headers, timeout=TIMEOUT, follow_redirects=True,
    ) as client:
        # Startseite kurz besuchen (simuliert echten Browser)
        home = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
        try:
            await client.get(home, timeout=8.0)
        except Exception:
            pass
        await asyncio.sleep(random.uniform(0.2, 0.6))
        resp = await client.get(url)
        resp.raise_for_status()
        # Encoding explizit setzen falls fehlt
        if resp.encoding is None or resp.encoding.lower() in ("", "latin-1"):
            resp.encoding = "utf-8"
    return _parse_html(resp.text)


async def _fetch_google_cache(url: str) -> str:
    cache_url = f"https://webcache.googleusercontent.com/search?q=cache:{quote_plus(url)}"
    async with httpx.AsyncClient(headers=_browser_headers(), timeout=TIMEOUT, follow_redirects=True) as client:
        resp = await client.get(cache_url)
        resp.raise_for_status()
    return _parse_html(resp.text)


def _parse_html(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "nav", "footer", "header",
                     "aside", "noscript", "iframe", "svg", "form"]):
        tag.decompose()
    for selector in [
        "main", "article",
        "[class*='spec']", "[class*='product']", "[id*='spec']", "[id*='product']",
        "[class*='detail']", "[id*='detail']", ".content", "#content",
    ]:
        el = soup.select_one(selector)
        if el:
            text = el.get_text(separator="\n", strip=True)
            if len(text) > 300:
                return _clean_text(text)
    return _clean_text(soup.get_text(separator="\n", strip=True))


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
