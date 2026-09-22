import httpx
from urllib.parse import urljoin
from bs4 import BeautifulSoup

APPLY_PATTERNS = [
    "apply now", "apply for this job", "apply for this position",
    "submit application", "apply here", "apply on company",
    "apply on website", "easy apply", "apply for job",
]


async def find_apply_url(job_url: str) -> str | None:
    """Fetch job listing page and find the actual apply link."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    try:
        async with httpx.AsyncClient(timeout=15.0, headers=headers, follow_redirects=True) as client:
            resp = await client.get(job_url)
            if resp.status_code != 200:
                return None
            soup = BeautifulSoup(resp.text, "html.parser")

            # Look for apply links/buttons by text content
            for a in soup.find_all("a", href=True):
                text = a.get_text(strip=True).lower()
                if any(p in text for p in APPLY_PATTERNS):
                    href = a["href"]
                    if href.startswith("http"):
                        return href
                    if href.startswith("/"):
                        return urljoin(job_url, href)

            # Look for elements with "apply" in class name that have href
            for el in soup.find_all(["a", "button"], class_=lambda c: c and "apply" in " ".join(c).lower() if isinstance(c, list) else c and "apply" in c.lower()):
                href = el.get("href") or el.get("data-url")
                if href:
                    if href.startswith("http"):
                        return href
                    if href.startswith("/"):
                        return urljoin(job_url, href)

    except Exception:
        pass
    return None
