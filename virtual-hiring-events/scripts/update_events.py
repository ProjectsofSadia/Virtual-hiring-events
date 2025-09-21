import os, json, csv, re, sys
from datetime import datetime, timezone
from dateutil import parser as dtp
import pandas as pd

import requests
import feedparser
from bs4 import BeautifulSoup
from ics import Calendar

DATA_DIR = "data"
SRC_DIR = os.path.join(DATA_DIR, "sources")
README = "README.md"
CSV_PATH = os.path.join(DATA_DIR, "events.csv")
JSON_PATH = os.path.join(DATA_DIR, "events.json")

os.makedirs(DATA_DIR, exist_ok=True)

SEARCH_TERMS = [t.strip().lower() for t in (os.getenv("SEARCH_TERMS","").split(",")) if t.strip()]
LOCATIONS    = [l.strip().lower() for l in (os.getenv("LOCATIONS","").split(";")) if l.strip()]

def parse_date(s):
    try:
        dt = dtp.parse(s)
        if not dt.tzinfo:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None

def md_table(sample):
    lines = [
        "| Date | Event Name | Company/Org | Location | Link |",
        "|------|------------|-------------|----------|------|",
    ]
    for e in sample:
        date_ = e.get("date_human") or e.get("date_iso") or ""
        name  = (e.get("name","") or "").replace("|","-")
        org   = (e.get("org","") or "").replace("|","-")
        loc   = (e.get("location","") or "Virtual").replace("|","-")
        url   = e.get("url","")
        link  = f"[Register]({url})" if url else ""
        lines.append(f"| {date_} | {name} | {org} | {loc} | {link} |")
    return "\n".join(lines)

def to_row(event):
    return {
        "date_iso": event.get("date_iso",""),
        "date_human": event.get("date_human",""),
        "name": event.get("name",""),
        "org": event.get("org",""),
        "location": event.get("location","Virtual"),
        "url": event.get("url",""),
        "source": event.get("source",""),
    }

def dedupe_sort(events):
    seen = set()
    uniq = []
    for e in events:
        key = (e.get("url","").strip(), e.get("date_iso","").strip(), e.get("name","").strip())
        if key in seen: 
            continue
        seen.add(key)
        uniq.append(e)
    uniq.sort(key=lambda x: (x.get("date_iso","9999-12-31"), x.get("name","")))
    return uniq

def matches_filters(ev):
    # Optional keyword/location filters
    name = f"{ev.get('name','')} {ev.get('org','')} {ev.get('source','')}".lower()
    loc  = (ev.get("location","") or "").lower()
    if SEARCH_TERMS and not any(t in name for t in SEARCH_TERMS):
        return False
    if LOCATIONS and all(l not in loc for l in LOCATIONS):
        # Allow virtual if locations filter provided but event is explicitly virtual
        if loc not in ("virtual","online","remote"):
            return False
    return True

# ---------- RSS ----------
def load_list(path):
    urls = []
    if not os.path.exists(path):
        return urls
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"): 
                continue
            urls.append(line)
    return urls

def fetch_from_rss(url, label=None):
    out = []
    feed = feedparser.parse(url)
    label = label or (feed.feed.get("title","RSS"))
    for entry in feed.entries:
        title = (entry.get("title") or "").strip()
        link  = (entry.get("link") or "").strip()
        dt = entry.get("published") or entry.get("updated") or ""
        pdt = parse_date(dt) or _guess_date_from_text(title + " " + (entry.get("summary") or ""))
        if not pdt:
            continue
        ev = {
            "date_iso": pdt.date().isoformat(),
            "date_human": pdt.strftime("%b %d, %Y"),
            "name": title,
            "org": label,
            "location": "Virtual",
            "url": link,
            "source": f"RSS:{label}",
        }
        if matches_filters(ev):
            out.append(to_row(ev))
    return out

def _guess_date_from_text(txt):
    # very rough; looks for YYYY-MM-DD or "Month DD, YYYY"
    m = re.findall(r"\b(\d{4}-\d{2}-\d{2})\b", txt)
    if m:
        return parse_date(m[0])
    m = re.findall(r"\b([A-Za-z]{3,9}\s+\d{1,2},\s*\d{4})\b", txt)
    if m:
        return parse_date(m[0])
    return None

# ---------- ICS ----------
def fetch_from_ics(url, label=None):
    out = []
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        cal = Calendar(resp.text)
        for ev in cal.events:
            if not ev.begin:
                continue
            dt = ev.begin.datetime
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            name = (ev.name or "").strip()
            loc = (ev.location or "Virtual").strip()
            link = (ev.url or url)
            evr = {
                "date_iso": dt.date().isoformat(),
                "date_human": dt.strftime("%b %d, %Y"),
                "name": name,
                "org": label or "ICS",
                "location": loc or "Virtual",
                "url": str(link),
                "source": f"ICS:{label or 'ICS'}",
            }
            if matches_filters(evr):
                out.append(to_row(evr))
    except Exception as e:
        print(f"[WARN] ICS fetch failed for {url}: {e}", file=sys.stderr)
    return out

# ---------- Greenhouse ----------
def fetch_greenhouse(subdomain):
    """
    Greenhouse public board: https://boards.greenhouse.io/{subdomain}
    There's a JSON feed often available at:
      https://boards-api.greenhouse.io/v1/boards/{subdomain}/jobs
    We'll look for job posts that look like virtual events / recruiting sessions by title heuristics.
    """
    out = []
    api_url = f"https://boards-api.greenhouse.io/v1/boards/{subdomain}/jobs"
    try:
        r = requests.get(api_url, timeout=30)
        if r.status_code != 200:
            return out
        data = r.json()
        for job in data.get("jobs", []):
            title = (job.get("title") or "").strip()
            # Heuristic: treat titles suggesting info sessions, events, fairs, recruiting
            if not re.search(r"(info session|hiring event|career fair|recruit|open house|virtual event)", title, re.I):
                continue
            # Try to find a date in metadata or the title/body (rare; fallback to posted date)
            dt = None
            # Greenhouse has "updated_at" in ISO8601
            dt_s = job.get("updated_at") or job.get("created_at")
            if dt_s:
                p = parse_date(dt_s)
                if p:
                    dt = p
            if not dt:
                # as last resort, current date
                dt = datetime.now(timezone.utc)
            org = subdomain
            url = job.get("absolute_url") or f"https://boards.greenhouse.io/{subdomain}"
            ev = {
                "date_iso": dt.date().isoformat(),
                "date_human": dt.strftime("%b %d, %Y"),
                "name": title,
                "org": org,
                "location": "Virtual",
                "url": url,
                "source": f"Greenhouse:{subdomain}",
            }
            if matches_filters(ev):
                out.append(to_row(ev))
    except Exception as e:
        print(f"[WARN] Greenhouse fetch failed for {subdomain}: {e}", file=sys.stderr)
    return out

def update_readme_table(events, readme_path=README):
    try:
        with open(readme_path, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        content = "# Virtual Hiring Events Hub\n\n## Upcoming (sample)\n\n"

    table = md_table(events[:20])
    if "## Upcoming (sample)" in content:
        new_content = re.sub(
            r"(## Upcoming \(sample\)\s*\n)(?:\|.*\n)+",
            r"\\1" + table + "\n",
            content,
            flags=re.DOTALL
        )
    else:
        new_content = content + "\n\n## Upcoming (sample)\n\n" + table + "\n"

    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(new_content)

def main():
    events = []

    # Load source lists
    rss_list = load_list(os.path.join(SRC_DIR, "rss.txt"))
    ics_list = load_list(os.path.join(SRC_DIR, "ics.txt"))
    gh_list  = load_list(os.path.join(SRC_DIR, "greenhouse.txt"))

    # Fetch RSS
    for url in rss_list:
        try:
            events += fetch_from_rss(url)
        except Exception as e:
            print(f"[WARN] RSS failed for {url}: {e}", file=sys.stderr)

    # Fetch ICS
    for url in ics_list:
        events += fetch_from_ics(url)

    # Fetch Greenhouse
    for sub in gh_list:
        events += fetch_greenhouse(sub)

    # Normalize, dedupe, sort
    events = [to_row(e) for e in events]
    events = dedupe_sort(events)

    # Write outputs
    pd.DataFrame(events).to_csv(CSV_PATH, index=False)
    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(events, f, indent=2, ensure_ascii=False)

    # Update README
    update_readme_table(events)

if __name__ == "__main__":
    main()
