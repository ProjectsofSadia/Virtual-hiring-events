from typing import Tuple, Optional
import time
import requests
from urllib.parse import urljoin, urlparse

UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) VirtualHiringBot/1.0 (+https://github.com/ProjectsofSadia/Virtual-hiring-events)"
}

def fetch(url: str, timeout: int = 25, tries: int = 3, backoff: float = 1.7) -> requests.Response:
    last_err = None
    for i in range(tries):
        try:
            r = requests.get(url, headers=UA, timeout=timeout, allow_redirects=True)
            r.raise_for_status()
            return r
        except Exception as e:
            last_err = e
            time.sleep(backoff ** i)
    raise last_err

def absolutize(base_url: str, href: Optional[str]) -> str:
    return urljoin(base_url, href or "")

def resolve_canonical(url: str, timeout: int = 10) -> Tuple[str, int]:
    try:
        r = requests.get(url, headers=UA, timeout=timeout, allow_redirects=True)
        return r.url, r.status_code
    except Exception:
        return url, 0

def good_host(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    bad_parts = ("lnkd.in", "l.facebook.com", "t.co")
    return not any(x in host for x in bad_parts)
