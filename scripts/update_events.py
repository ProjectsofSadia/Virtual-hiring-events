import os, re, csv, json, sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import requests
import feedparser
import pandas as pd
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SRC  = DATA / "sources"
DATA.mkdir(parents=True, exist_ok=True)
SRC.mkdir(parents=True, exist_ok=True)

UTC = timezone.utc
TODAY = datetime.now(UTC).date()
MAX_EVENT_AGE_DAYS = 180  # 6 months window
DEBUG = os.getenv("DEBUG", "0") == "1"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

def load_lines(p: Path):
    if not p.exists(): return []
    return [ln.strip() for ln in p.read_text(encoding="utf-8").splitlines()
            if ln.strip() and not ln.strip().startswith("#")]

def write_csv(path: Path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})

def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def norm_date(dt_str):
    if not dt_str: return None
    try:
        return datetime.fromisoformat(dt_str.replace("Z","+00:00")).astimezone(UTC)
    except Exception:
        pass
    try:
        return datetime.strptime(dt_str, "%a, %d %b %Y %H:%M:%S %Z").replace(tzinfo=UTC)
    except Exception:
        return None

def is_intern(title: str):
    t = (title or "").lower()
    return any(k in t for k in ["intern", "internship", "co-op", "co op"])

def clean_location(loc: str):
    loc = (loc or "").strip()
    return loc if loc else "Remote/Virtual"

def top_table(rows, cols, limit=25):
    lines = []
    lines.append("| " + " | ".join(cols) + " |")
    lines.append("|" + "|".join(["------"]*len(cols)) + "|")
    for r in rows[:limit]:
        lines.append("| " + " | ".join(str(r.get(c,"")).replace("|","-") for c in cols) + " |")
    return "\n".join(lines)

def readme_replace_section(md: str, header: str, table_md: str):
    pattern = rf"(## {re.escape(header)}\s*\n)(.*?)(?=\n## |\Z)"
    repl = r"\1" + table_md.strip() + "\n"
    new, n = re.subn(pattern, repl, md, flags=re.S|re.M)
    if n == 0:
        new = md.rstrip() + f"\n\n## {header}\n{table_md.strip()}\n"
    return new

# -------------------- JOBS (Greenhouse + Lever) --------------------

def fetch_greenhouse_company(board):
    out = []
    url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs"
    try:
        resp = requests.get(url, timeout=30, headers=HEADERS)
        resp.raise_for_status()
        data = resp.json()
        for j in data.get("jobs", []):
            title = j.get("title","").strip()
            locations = j.get("locations") or []
            loc = ", ".join([l.get("name","") for l in locations]) if locations else (j.get("location",{}) or {}).get("name","")
            link = j.get("absolute_url") or j.get("url") or ""
            created = j.get("updated_at") or j.get("created_at") or ""
            dtv = norm_date(created) or datetime.now(UTC)
            out.append({
                "date_iso": dtv.date().isoformat(),
                "date_human": dtv.strftime("%b %d, %Y"),
                "title": title,
                "company": board,
                "location": clean_location(loc),
                "apply": link,
                "source": "greenhouse",
                "department": ((j.get("departments") or [{}])[0] or {}).get("name","")
            })
    except Exception as ex:
        if DEBUG: print(f"[WARN] Greenhouse fetch failed for {board}: {ex}", file=sys.stderr)
    if DEBUG: print(f"[DEBUG] Greenhouse {board}: {len(out)} jobs")
    return out

def fetch_lever_company(company):
    out = []
    url = f"https://api.lever.co/v0/postings/{company}?mode=json"
    try:
        resp = requests.get(url, timeout=30, headers=HEADERS)
        resp.raise_for_status()
        data = resp.json()
        for j in data:
            title = (j.get("text") or "").strip()
            loc = j.get("categories",{}).get("location","")
            link = j.get("hostedUrl") or j.get("applyUrl") or ""
            created = j.get("createdAt") or j.get("updatedAt")
            if isinstance(created, (int, float)):
                dtv = datetime.fromtimestamp(int(created)/1000, tz=UTC)
            else:
                dtv = norm_date(str(created)) or datetime.now(UTC)
            out.append({
                "date_iso": dtv.date().isoformat(),
                "date_human": dtv.strftime("%b %d, %Y"),
                "title": title,
                "company": company,
                "location": clean_location(loc),
                "apply": link,
                "source": "lever",
                "department": j.get("categories",{}).get("team","")
            })
    except Exception as ex:
        if DEBUG: print(f"[WARN] Lever fetch failed for {company}: {ex}", file=sys.stderr)
    if DEBUG: print(f"[DEBUG] Lever {company}: {len(out)} jobs")
    return out

def collect_jobs():
    ghs = load_lines(SRC / "greenhouse.txt")
    lev = load_lines(SRC / "lever.txt")
    jobs = []
    for c in ghs:
        jobs += fetch_greenhouse_company(c)
    for c in lev:
        jobs += fetch_lever_company(c)
    # Dedup
    seen = set()
    uniq = []
    for j in jobs:
        key = (j["title"].lower(), j["company"].lower(), j["apply"])
        if key in seen: continue
        seen.add(key)
        uniq.append(j)
    # Sort newest first
    uniq.sort(key=lambda x: (x.get("date_iso",""), x.get("title","").lower()), reverse=True)
    return uniq

def split_jobs(jobs):
    interns = [j for j in jobs if is_intern(j["title"])]
    fulltime = [j for j in jobs if not is_intern(j["title"])]
    return interns, fulltime

# -------------------- EVENTS --------------------

def fetch_rss_events(url):
    out = []
    try:
        # Use requests with headers then feedparser on the bytes (helps with sites blocking default clients)
        r = requests.get(url, timeout=30, headers=HEADERS)
        r.raise_for_status()
        d = feedparser.parse(r.content)
        if DEBUG: print(f"[DEBUG] RSS '{url}' entries: {len(d.entries)}")
        for e in d.entries:
            # pick a date
            dtv = None
            if getattr(e, "published_parsed", None):
                p = e.published_parsed
                dtv = datetime(p.tm_year, p.tm_mon, p.tm_mday, p.tm_hour, p.tm_min, p.tm_sec, tzinfo=UTC)
            elif getattr(e, "updated_parsed", None):
                p = e.updated_parsed
                dtv = datetime(p.tm_year, p.tm_mon, p.tm_mday, p.tm_hour, p.tm_min, p.tm_sec, tzinfo=UTC)
            else:
                # fallback: now
                dtv = datetime.now(UTC)
            # window filter
            if not (TODAY - timedelta(days=7) <= dtv.date() <= TODAY + timedelta(days=MAX_EVENT_AGE_DAYS)):
                continue
            out.append({
                "date_iso": dtv.date().isoformat(),
                "date_human": dtv.strftime("%b %d, %Y"),
                "name": (getattr(e, "title", "") or "").strip(),
                "org": (getattr(e, "author", "") or getattr(e, "source", "") or "").strip(),
                "location": "Virtual/Online",
                "url": getattr(e, "link", "") or "",
                "source": url,
            })
    except Exception as ex:
        if DEBUG: print(f"[WARN] RSS fetch failed for {url}: {ex}", file=sys.stderr)
    return out

def fetch_eventbrite_category(base_url: str, pages: int = 5):
    out = []
    for p in range(1, pages + 1):
        url = base_url if p == 1 else (base_url.rstrip("/") + f"/?page={p}")
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            # JSON-LD events
            for tag in soup.find_all("script", type="application/ld+json"):
                try:
                    data = json.loads(tag.string or "{}")
                    items = data if isinstance(data, list) else [data]
                except Exception:
                    continue
                for item in items:
                    if item.get("@type") == "Event":
                        name = (item.get("name") or "").strip()
                        start = item.get("startDate") or item.get("startdate")
                        link = (item.get("url") or "").strip()
                        dtv = norm_date(start) or datetime.now(UTC)
                        ev = {
                            "date_iso": dtv.date().isoformat(),
                            "date_human": dtv.strftime("%b %d, %Y"),
                            "name": name,
                            "org": "Eventbrite",
                            "location": "Virtual/Online",
                            "url": link,
                            "source": base_url,
                        }
                        out.append(ev)

            # Visible cards fallback
            cards = soup.select('[data-testid="event-card"]') or soup.select("div[data-spec*='event-card']")
            for c in cards:
                a = c.find("a", href=True)
                if not a: continue
                link = a["href"]
                ttl = c.select_one('[data-testid="event-card__formatted-name"], h2, h3')
                date_el = c.select_one('[data-testid="event-card__formatted-date"]')
                name = (ttl.get_text(strip=True) if ttl else "Event").strip()
                date_txt = (date_el.get_text(" ", strip=True) if date_el else "")
                # naive parse: keep today if unknown
                dtv = norm_date(date_txt) or datetime.now(UTC)
                ev = {
                    "date_iso": dtv.date().isoformat(),
                    "date_human": dtv.strftime("%b %d, %Y"),
                    "name": name,
                    "org": "Eventbrite",
                    "location": "Virtual/Online",
                    "url": link,
                    "source": base_url,
                }
                out.append(ev)

            if DEBUG: print(f"[DEBUG] Eventbrite page {p} -> {len(out)} total from {base_url}")
            # simple early break if page returned nothing new
            if p > 1 and not cards and not any(True for _ in soup.find_all("script", type="application/ld+json")):
                break

        except Exception as ex:
            if DEBUG: print(f"[WARN] Eventbrite fetch failed for {url}: {ex}", file=sys.stderr)
            if p == 1:
                continue
            else:
                break
    return out

def collect_events():
    events = []

    rss_list = load_lines(SRC / "rss.txt")
    if DEBUG: print(f"[DEBUG] rss.txt URLs: {len(rss_list)}")
    for url in rss_list:
        before = len(events)
        events += fetch_rss_events(url)
        if DEBUG: print(f"[DEBUG] RSS added {len(events)-before} (total {len(events)}) from {url}")

    eb_list = load_lines(SRC / "eventbrite.txt")
    if DEBUG: print(f"[DEBUG] eventbrite.txt URLs: {len(eb_list)}")
    for url in eb_list:
        before = len(events)
        events += fetch_eventbrite_category(url, pages=5)
        if DEBUG: print(f"[DEBUG] Eventbrite added {len(events)-before} (total {len(events)}) from {url}")

    # Keep upcoming-ish
    kept = []
    for ev in events:
        try:
            d = datetime.fromisoformat(ev["date_iso"]).date()
        except Exception:
            continue
        if d >= TODAY - timedelta(days=7) and d <= TODAY + timedelta(days=MAX_EVENT_AGE_DAYS):
            kept.append(ev)

    # Dedupe by (name,url,date)
    seen = set()
    uniq = []
    for e in kept:
        key = (e["name"].lower(), e["url"], e["date_iso"])
        if key in seen: continue
        seen.add(key)
        uniq.append(e)

    uniq.sort(key=lambda x: (x["date_iso"], x["name"].lower()))
    return uniq

# -------------------- README UPDATE --------------------

def update_readme(events, jobs, interns, fulltime):
    path = ROOT / "README.md"
    if not path.exists(): return
    md = path.read_text(encoding="utf-8")

    events_view = [{
        "date_human": e["date_human"],
        "name": e["name"],
        "org": e["org"],
        "location": e["location"],
        "url": f"[Register]({e['url']})" if e.get("url") else ""
    } for e in events]
    ev_table = top_table(events_view, ["date_human","name","org","location","url"], limit=25) + \
        "\n\n➡️ [View All Events (CSV)](data/events.csv) | [View All Events (JSON)](data/events.json)\n"

    jobs_view = [{
        "date_human": j["date_human"],
        "title": j["title"],
        "company": j["company"],
        "location": j["location"],
        "apply": f"[Apply]({j['apply']})" if j.get("apply") else ""
    } for j in jobs]
    jobs_table = top_table(jobs_view, ["date_human","title","company","location","apply"], limit=25) + \
        "\n\n➡️ [All Jobs (CSV)](data/jobs.csv) | [All Jobs (JSON)](data/jobs.json)\n"

    interns_view = [{
        "date_human": j["date_human"],
        "title": j["title"],
        "company": j["company"],
        "location": j["location"],
        "apply": f"[Apply]({j['apply']})" if j.get("apply") else ""
    } for j in interns]
    interns_table = top_table(interns_view, ["date_human","title","company","location","apply"], limit=25) + \
        "\n\n➡️ [Internships (CSV)](data/internships.csv) | [Internships (JSON)](data/internships.json)\n"

    ft_view = [{
        "date_human": j["date_human"],
        "title": j["title"],
        "company": j["company"],
        "location": j["location"],
        "apply": f"[Apply]({j['apply']})" if j.get("apply") else ""
    } for j in fulltime]
    ft_table = top_table(ft_view, ["date_human","title","company","location","apply"], limit=25) + \
        "\n\n➡️ [Full-Time (CSV)](data/fulltime.csv) | [Full-Time (JSON)](data/fulltime.json)\n"

    md = readme_replace_section(md, "📅 Upcoming Events (Auto-updated)", ev_table)
    md = readme_replace_section(md, "💼 Open Roles (Auto-updated)", jobs_table)
    md = readme_replace_section(md, "🎓 Internship Roles (Auto-updated)", interns_table)
    md = readme_replace_section(md, "🏢 Full-Time Opportunities (Auto-updated)", ft_table)

    path.write_text(md, encoding="utf-8")

# -------------------- MAIN --------------------

def main():
    # Jobs
    jobs = collect_jobs()
    interns, fulltime = split_jobs(jobs)

    # Events
    events = collect_events()

    # Save datasets
    write_csv(DATA / "jobs.csv", jobs, ["date_iso","date_human","title","company","location","apply","source","department"])
    write_json(DATA / "jobs.json", jobs)
    write_csv(DATA / "internships.csv", interns, ["date_iso","date_human","title","company","location","apply","source","department"])
    write_json(DATA / "internships.json", interns)
    write_csv(DATA / "fulltime.csv", fulltime, ["date_iso","date_human","title","company","location","apply","source","department"])
    write_json(DATA / "fulltime.json", fulltime)

    write_csv(DATA / "events.csv", events, ["date_iso","date_human","name","org","location","url","source"])
    write_json(DATA / "events.json", events)

    # README
    update_readme(events, jobs, interns, fulltime)

    if DEBUG:
        print(f"[DEBUG] Wrote {len(events)} events, {len(jobs)} jobs "
              f"({len(interns)} interns, {len(fulltime)} full-time)")

if __name__ == "__main__":
    main()
