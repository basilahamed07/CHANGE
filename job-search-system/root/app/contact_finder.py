import re
import httpx
from bs4 import BeautifulSoup


async def find_hiring_contact(company: str, job_title: str, location: str = "") -> dict:
    """Search DuckDuckGo for hiring manager contact info.

    Returns: dict with keys: name, email, title, source (all optional)
    """
    results = {}
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    async with httpx.AsyncClient(timeout=15.0, headers=headers, follow_redirects=True) as client:
        # Strategy 1: DuckDuckGo HTML search
        queries = [
            f'"{company}" recruiter {job_title} email',
            f'"{company}" hiring manager {job_title}',
            f'"{company}" careers contact email',
        ]

        for query in queries:
            try:
                resp = await client.get(
                    "https://html.duckduckgo.com/html/",
                    params={"q": query},
                )
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.text, "html.parser")
                    for result_el in soup.select(".result__body"):
                        text = result_el.get_text()
                        emails = re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', text)
                        if emails:
                            # Filter out generic/noreply emails
                            good = [e for e in emails if not any(
                                g in e.lower() for g in ['noreply', 'no-reply', 'mailer-daemon', 'postmaster']
                            )]
                            if good:
                                results["email"] = good[0]
                                results["source"] = "web_search"
                                break
                if results.get("email"):
                    break
            except Exception:
                continue

        # Strategy 2: Try company website directly
        if not results.get("email"):
            company_slug = re.sub(r'[^a-z0-9]', '', company.lower())
            for domain in [f"{company_slug}.com", f"www.{company_slug}.com"]:
                for path in ["/careers", "/jobs", "/contact", "/about"]:
                    try:
                        resp = await client.get(f"https://{domain}{path}")
                        if resp.status_code == 200:
                            emails = re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', resp.text)
                            good = [e for e in emails if not any(
                                g in e.lower() for g in ['noreply', 'no-reply', 'support@', 'info@', 'sales@', 'help@']
                            )]
                            if good:
                                results["email"] = good[0]
                                results["source"] = domain
                                break
                    except Exception:
                        continue
                if results.get("email"):
                    break

    return results
