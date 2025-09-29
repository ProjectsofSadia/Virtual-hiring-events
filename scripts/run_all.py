
if __name__ == "__main__" and __package__ is None:
    import sys, pathlib
    sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))
    __package__ = "scripts"

import os
from typing import List, Dict
from urllib.parse import urlparse
import yaml

from .parsers import (
    parse_rss,
    parse_html_cards,
    extract_links_pattern,
    parse_jsonld_from_pages,
)
from .fetchers import resolve_canonical, good_host
from .storage import append_items, export_latest

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def load_sources() -> dict:
    cfg_path = os.path.join(BASE, "scripts", "sources.yaml")
    if not os.path.exists(cfg_path):
        raise FileNotFoundError(f"Missing sources.yaml at {cfg_path}")
    with open(cfg_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def canonicalize(items: List[Dict], verify_200: bool = True) -> List[Dict]:
    out: List[Dict] = []
    for it in items:
        url = (it.get("url") or "").strip()
        if not url:
            continue
        final_url, status = resolve_canonical(url) if verify_200 else (url, 200)
        if verify_200 and status != 200:
            continue
        if not good_host(final_url):
            continue
        it["url"] = final_url
        if not it.get("company"):
            try:
                host = urlparse(final_url).netloc.replace("www.", "")
                it["company"] = host
            except Exception:
                pass
        out.append(it)
    return out

def run() -> None:
    cfg = load_sources()
    rss_list: List[str] = cfg.get("rss", []) or []
    html_list: List[dict] = cfg.get("html", []) or []
    freshness_days = int(cfg.get("settings", {}).get("freshness_days", 90))
    verify_200 = bool(cfg.get("settings", {}).get("verify_http_200", True))

    all_jobs: List[Dict] = []
    all_events: List[Dict] = []

    for url in rss_list:
        try:
            items = parse_rss(url, freshness_days=freshness_days)
            print(f"SOURCE (rss) {url} -> {len(items)} items")
        except Exception as e:
            print(f"WARN rss: {url} -> {e.__class__.__name__}: {e}")
            continue
        if "event" in url.lower() or "status.aws.amazon.com" in url.lower():
            all_events.extend(items)
        else:
            all_jobs.extend(items)

    for block in html_list:
        url = block.get("url", "")
        if not url:
            continue
        try:
            items = parse_html_cards(
                url=url,
                item_selector=block.get("item", ""),
                title_selector=block.get("title", ""),
                link_selector=block.get("link", ""),
                date_selector=(block.get("date") or None),
                date_fmt=(block.get("date_fmt") or None),
                freshness_days=freshness_days,
            )
            if not items:
                include_substr = block.get("include")
                if include_substr:
                    links = extract_links_pattern(url=url, include_substr=include_substr)
                    items = parse_jsonld_from_pages(links, freshness_days=max(180, freshness_days))
            print(f"SOURCE (html) {url} -> {len(items)} items")
        except Exception as e:
            print(f"WARN html: {url} -> {e.__class__.__name__}: {e}")
            continue
        if any(k in url.lower() for k in ["career", "job", "jobs"]):
            all_jobs.extend(items)
        else:
            all_events.extend(items)

    all_jobs = canonicalize(all_jobs, verify_200=verify_200)
    all_events = canonicalize(all_events, verify_200=verify_200)

    print(f"POST-CANON jobs={len(all_jobs)} events={len(all_events)}")

    jobs_added = append_items("jobs", all_jobs)
    events_added = append_items("events", all_events)

    export_latest("jobs")
    export_latest("events")

    try:
        from .build_pages import make_index
        make_index()
    except Exception as e:
        print(f"WARN build_pages: {e.__class__.__name__}: {e}")

    print(f"✅ jobs_added={jobs_added} | events_added={events_added}")

if __name__ == "__main__":
    run()
