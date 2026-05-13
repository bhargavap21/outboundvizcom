"""
Agency website scraper — httpx + BeautifulSoup4.
Crawls homepage + auto-detected team/work/about pages.
Extracts: team headcount, tool mentions, client names, contact names/titles.
"""
from __future__ import annotations
import re
from urllib.parse import urljoin, urlparse
from typing import Optional
import httpx
import structlog
from bs4 import BeautifulSoup

log = structlog.get_logger()

TIMEOUT = 12
MAX_PAGES = 4   # homepage + up to 3 sub-pages

# Sub-page slugs to try, in priority order
TEAM_PAGE_HINTS   = ["/team", "/people", "/about", "/about-us", "/studio", "/us"]
WORK_PAGE_HINTS   = ["/work", "/projects", "/portfolio", "/case-studies", "/clients"]

# Title keywords that signal a relevant contact
DIRECTOR_TITLES = {
    "design director", "creative director", "creative lead",
    "principal designer", "principal industrial designer",
    "founder", "co-founder", "partner", "head of design",
    "vp design", "chief design officer",
}

TARGET_TOOLS = {
    "keyshot", "rhino", "rhinoceros", "solidworks", "alias",
    "catia", "modo", "v-ray", "cinema 4d", "blender", "procreate",
    "fusion 360", "cad", "3d rendering",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


def scrape_website(base_url: str) -> dict:
    """
    Crawl the agency website and return a raw data dict.
    Keys: team_members, tool_mentions, client_names, page_texts, contacts
    """
    if not base_url:
        return {}

    base_url = base_url.rstrip("/")
    result: dict = {
        "team_members": [],
        "tool_mentions": [],
        "client_names": [],
        "contacts": [],       # [{name, title, linkedin_url}]
        "page_texts": {},     # {url: text}
    }

    with httpx.Client(
        timeout=TIMEOUT,
        follow_redirects=True,
        headers=HEADERS,
    ) as client:
        # Fetch homepage
        homepage_soup = _fetch_page(client, base_url)
        if homepage_soup:
            result["page_texts"][base_url] = _text(homepage_soup)
            result["client_names"] = _extract_clients(homepage_soup)

        # Detect and fetch team + work sub-pages
        links = _find_links(homepage_soup, base_url) if homepage_soup else []
        fetched_pages = 1

        for slug_list in [TEAM_PAGE_HINTS, WORK_PAGE_HINTS]:
            target_url = _find_subpage(links, base_url, slug_list)
            if not target_url or fetched_pages >= MAX_PAGES:
                continue
            soup = _fetch_page(client, target_url)
            if soup:
                result["page_texts"][target_url] = _text(soup)
                result["team_members"].extend(_extract_team_members(soup))
                result["contacts"].extend(_extract_contacts(soup))
                fetched_pages += 1

    # Scan all page text for tool mentions
    combined = " ".join(result["page_texts"].values()).lower()
    result["tool_mentions"] = [t for t in TARGET_TOOLS if t in combined]

    # Deduplicate contacts
    seen = set()
    unique_contacts = []
    for c in result["contacts"]:
        key = c.get("name", "").lower()
        if key and key not in seen:
            seen.add(key)
            unique_contacts.append(c)
    result["contacts"] = unique_contacts

    log.info(
        "website_scraped",
        url=base_url,
        pages=len(result["page_texts"]),
        team_members=len(result["team_members"]),
        contacts=len(result["contacts"]),
        tools=result["tool_mentions"],
    )
    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fetch_page(client: httpx.Client, url: str) -> Optional[BeautifulSoup]:
    try:
        resp = client.get(url)
        resp.raise_for_status()
        return BeautifulSoup(resp.text, "html.parser")
    except Exception as e:
        log.warning("website_page_fetch_failed", url=url, error=str(e))
        return None


def _text(soup: BeautifulSoup) -> str:
    for tag in soup(["script", "style", "nav", "footer"]):
        tag.decompose()
    return " ".join(soup.get_text(separator=" ").split())


def _find_links(soup: Optional[BeautifulSoup], base_url: str) -> list[str]:
    if not soup:
        return []
    return [
        urljoin(base_url, a["href"])
        for a in soup.find_all("a", href=True)
        if _same_domain(urljoin(base_url, a["href"]), base_url)
    ]


def _same_domain(url: str, base: str) -> bool:
    return urlparse(url).netloc == urlparse(base).netloc


def _find_subpage(links: list[str], base_url: str, hints: list[str]) -> Optional[str]:
    # First pass: match against actual links found on the page
    for hint in hints:
        for link in links:
            path = urlparse(link).path.lower().rstrip("/")
            if path == hint or path.endswith(hint):
                return link
    # Fallback: try the first hint as a constructed URL
    if hints:
        return base_url + hints[0]
    return None


def _extract_clients(soup: BeautifulSoup) -> list[str]:
    """Look for alt text on logo images as proxy for client names."""
    clients = []
    for img in soup.find_all("img", alt=True):
        alt = img["alt"].strip()
        if 2 < len(alt) < 40 and not any(c.isdigit() for c in alt[:4]):
            clients.append(alt)
    return list(dict.fromkeys(clients))[:20]


def _extract_team_members(soup: BeautifulSoup) -> list[dict]:
    """
    Heuristic: look for name+title patterns near each other in a team section.
    Common pattern: <h3>Name</h3><p>Title</p> or aria-label patterns.
    """
    members = []
    # Find all text nodes that look like job titles
    for el in soup.find_all(["h2", "h3", "h4", "p", "span"]):
        text = el.get_text(strip=True)
        if len(text) > 60:
            continue
        title_lower = text.lower()
        if any(kw in title_lower for kw in ("designer", "director", "lead", "founder", "partner")):
            # Sibling or parent likely contains the name
            prev = el.find_previous_sibling()
            if prev and 2 < len(prev.get_text(strip=True)) < 40:
                members.append({
                    "name": prev.get_text(strip=True),
                    "title": text,
                })
    return members[:30]


def _extract_contacts(soup: BeautifulSoup) -> list[dict]:
    """
    Extract high-value contacts (directors/leads) with LinkedIn links where available.
    """
    contacts = []
    all_text = _text(soup)

    # Look for LinkedIn profile links near director-title keywords
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "linkedin.com/in/" not in href:
            continue
        context = a.get_text(strip=True)
        # Get surrounding text
        parent_text = (a.parent or a).get_text(separator=" ", strip=True)[:200].lower()
        if any(t in parent_text for t in DIRECTOR_TITLES):
            name = context or parent_text[:40]
            title = next(
                (t for t in DIRECTOR_TITLES if t in parent_text),
                "designer",
            )
            contacts.append({"name": name, "title": title, "linkedin_url": href})

    return contacts
