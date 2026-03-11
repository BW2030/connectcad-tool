"""Web scraping: find product pages and fetch content."""
import httpx
from bs4 import BeautifulSoup
from urllib.parse import quote_plus
import re

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

TIMEOUT = 15.0


async def search_duckduckgo(query: str, max_results: int = 5) -> list[dict]:
    """Search DuckDuckGo HTML and return list of {title, url, snippet}."""
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query + ' specifications')}"
    async with httpx.AsyncClient(headers=HEADERS, timeout=TIMEOUT, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")
    results = []
    for result in soup.select(".result")[:max_results]:
        title_el = result.select_one(".result__title a")
        snippet_el = result.select_one(".result__snippet")
        if not title_el:
            continue
        href = title_el.get("href", "")
        # DuckDuckGo wraps URLs — extract the real one
        real_url = _extract_ddg_url(href)
        if not real_url:
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
        "num": max_results,
        "engine": "google",
    }
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.get("https://serpapi.com/search", params=params)
        resp.raise_for_status()

    data = resp.json()
    results = []
    for item in data.get("organic_results", [])[:max_results]:
        results.append({
            "title": item.get("title", ""),
            "url": item.get("link", ""),
            "snippet": item.get("snippet", ""),
        })
    return results


async def fetch_page_text(url: str) -> str:
    """Fetch a product page and return cleaned text content."""
    async with httpx.AsyncClient(headers=HEADERS, timeout=TIMEOUT, follow_redirects=True) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")

    # Remove nav/footer/scripts/ads
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
        tag.decompose()

    # Prefer main content areas
    for selector in ["main", "article", ".product", "#product", ".specs", "#specs", ".specifications"]:
        el = soup.select_one(selector)
        if el:
            text = el.get_text(separator="\n", strip=True)
            if len(text) > 200:
                return _clean_text(text)

    return _clean_text(soup.get_text(separator="\n", strip=True))


def _extract_ddg_url(href: str) -> str:
    """Extract real URL from DuckDuckGo redirect or direct href."""
    if href.startswith("http"):
        return href
    match = re.search(r"uddg=([^&]+)", href)
    if match:
        from urllib.parse import unquote
        return unquote(match.group(1))
    return ""


def _clean_text(text: str) -> str:
    """Remove excessive whitespace from scraped text."""
    lines = [line.strip() for line in text.splitlines()]
    lines = [l for l in lines if l]
    # Collapse runs of blank lines
    result = []
    prev_blank = False
    for line in lines:
        if line == "":
            if not prev_blank:
                result.append(line)
            prev_blank = True
        else:
            result.append(line)
            prev_blank = False
    return "\n".join(result)[:12000]  # Cap at ~12k chars for Claude
