from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
import feedparser
from bs4 import BeautifulSoup
from dateutil import parser as dtparse

from .fetchers import fetch, absolutize

def parse_date_any(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        dt = dtparse.parse(s, fuzzy=True)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt
    except Exception:
        return None

def within_window(dt: Optional[datetime], days: int = 90) -> bool:
    if dt is None:
        return True  
    return dt >= (datetime.now(timezone.utc) - timedelta(days=days))

def parse_rss(url: str, freshness_days: int = 90) -> List[Dict]:
    r = fetch(url)
    d = feedparser.parse(r.content)
    items: List[Dict] = []
    for e in d.entries:
        title = (e.get("title") or "").strip()
        link = (e.get("link") or "").strip()
        pub_raw = e.get("published") or e.get("updated") or ""
        pub_dt = parse_date_any(pub_raw)
        if not within_window(pub_dt, days=freshness_days):
            continue
        items.append({
            "title": title,
            "url": link,
            "published": pub_dt.isoformat() if pub_dt else "",
            "source": url,
            "summary": (e.get("summary") or "").strip()
        })
    return items

def parse_html_cards(
    url: str,
    item_selector: str,
    title_selector: str,
    link_selector: str,
    date_selector: Optional[str] = None,
    date_fmt: Optional[str] = None,
    freshness_days: int = 90
) -> List[Dict]:
    r = fetch(url)
    soup = BeautifulSoup(r.text, "html.parser")
    out: List[Dict] = []
    for card in soup.select(item_selector):
        t_el = card.select_one(title_selector)
        l_el = card.select_one(link_selector)
        d_el = card.select_one(date_selector) if date_selector else None

        title = (t_el.get_text(strip=True) if t_el else "").strip()
        link = absolutize(url, l_el.get("href") if l_el else "")
        published = ""
        if d_el:
            raw = d_el.get_text(strip=True)
            if date_fmt:
                try:
                    dt = datetime.strptime(raw, date_fmt).replace(tzinfo=timezone.utc)
                except Exception:
                    dt = parse_date_any(raw)
            else:
                dt = parse_date_any(raw)
            published = dt.isoformat() if dt else ""

        pub_dt = parse_date_any(published) if published else None
        if not within_window(pub_dt, days=freshness_days):
            continue

        out.append({
            "title": title,
            "url": link,
            "published": published,
            "source": url
        })
    return out
