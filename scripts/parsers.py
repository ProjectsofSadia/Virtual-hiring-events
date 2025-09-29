# scripts/parsers.py
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Any, Iterable
import json

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
            "summary": (e.get("summary") or "").strip(),
        })
    return items


def parse_html_cards(
    url: str,
    item_selector: str,
    title_selector: str,
    link_selector: str,
    date_selector: Optional[str] = None,
    date_fmt: Optional[str] = None,
    freshness_days: int = 90,
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
            dt = None
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
            "source": url,
        })
    return out


def _collect_jsonld_objects(raw: str) -> List[Any]:
    objs: List[Any] = []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            objs.extend(data)
        else:
            objs.append(data)
    except Exception:
        pass
    return objs


def extract_links_pattern(url: str, include_substr: str) -> list[str]:
    r = fetch(url)
    soup = BeautifulSoup(r.text, "html.parser")
    hits: list[str] = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if include_substr in href:
            hits.append(absolutize(url, href))
    seen = set()
    out: list[str] = []
    for u in hits:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def parse_jsonld_from_pages(urls: Iterable[str], freshness_days: int = 180) -> list[dict]:
    out: list[dict] = []
    for u in urls:
        try:
            r = fetch(u)
            soup = BeautifulSoup(r.text, "html.parser")
            for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
                for obj in _collect_jsonld_objects(tag.string or tag.get_text() or ""):
                    if not isinstance(obj, dict):
                        continue
                    candidates = []
                    if obj.get("@type") == "Event":
                        candidates = [obj]
                    if "@graph" in obj and isinstance(obj["@graph"], list):
                        candidates.extend([x for x in obj["@graph"] if isinstance(x, dict) and x.get("@type") == "Event"])
                    for ev in candidates:
                        title = (ev.get("name") or "").strip()
                        link = (ev.get("url") or u).strip()
                        start = ev.get("startDate") or ev.get("startTime") or ev.get("start")
                        end = ev.get("endDate") or ev.get("endTime") or ev.get("end")
                        pub_dt = parse_date_any(start) or parse_date_any(end)
                        if not within_window(pub_dt, days=freshness_days):
                            continue
                        item = {
                            "title": title,
                            "url": absolutize(u, link),
                            "published": pub_dt.isoformat() if pub_dt else "",
                            "source": u,
                        }
                        out.append(item)
        except Exception:
            continue
    return out
