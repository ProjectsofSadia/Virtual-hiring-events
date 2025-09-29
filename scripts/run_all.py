
if __name__ == "__main__" and __package__ is None:
    import sys, pathlib
    sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))
    __package__ = "scripts"

import os
from typing import List, Dict
from urllib.parse import urlparse
import yaml

from .parsers import parse_rss
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
        try:
            final_url, status = resolve_canonical(url) if verify_200 else (url, 200)
        except Exception:
            
            continue
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
    freshness_days = int(cfg.get("settings", {}).get("freshness_days", 90))
    verify_200 = bool(cfg.get("settings", {}).get("verify_http_200", True))

    all_jobs: List[Dict] = []

    for url in rss_list:
        try:
            items = parse_rss(url, freshness_days=freshness_days)
            print(f"SOURCE (rss) {url} -> {len(items)} items")
        except Exception as e:
            print(f"WARN rss: {url} -> {e.__class__.__name__}: {e}")
            continue
        all_jobs.extend(items)

    all_jobs = canonicalize(all_jobs, verify_200=verify_200)
    print(f"POST-CANON jobs={len(all_jobs)}")

    jobs_added = append_items("jobs", all_jobs)
    export_latest("jobs")

    try:
        from .build_pages import make_index
        make_index()
    except Exception as e:
        print(f"WARN build_pages: {e.__class__.__name__}: {e}")

    print(f"✅ jobs_added={jobs_added}")

if __name__ == "__main__":
    run()
