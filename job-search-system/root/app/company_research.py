import re
import httpx


async def research_company(company_name: str) -> dict:
    """Fetch company info via DuckDuckGo Instant Answer API."""
    info = {"name": company_name}
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
    }

    async with httpx.AsyncClient(timeout=15.0, headers=headers, follow_redirects=True) as client:
        # DuckDuckGo Instant Answer API (no key needed)
        try:
            resp = await client.get("https://api.duckduckgo.com/", params={
                "q": company_name, "format": "json", "no_html": "1"
            })
            if resp.status_code == 200:
                data = resp.json()
                if data.get("Abstract"):
                    info["description"] = data["Abstract"][:500]
                if data.get("AbstractURL"):
                    info["website"] = data["AbstractURL"]
        except Exception:
            pass

        # Try to find Glassdoor rating via search
        try:
            from bs4 import BeautifulSoup
            resp = await client.get("https://html.duckduckgo.com/html/",
                params={"q": f"{company_name} glassdoor rating"})
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                text = soup.get_text()
                rating_match = re.search(r'(\d\.\d)\s*(?:out of 5|/5|stars?)', text)
                if rating_match:
                    rating = float(rating_match.group(1))
                    if 1.0 <= rating <= 5.0:
                        info["glassdoor_rating"] = rating
        except Exception:
            pass

    return info
