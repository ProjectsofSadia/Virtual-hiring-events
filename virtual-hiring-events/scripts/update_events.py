import os, json, re, sys
from datetime import datetime, timezone
from dateutil import parser as dtp
import pandas as pd
import requests
import feedparser
from ics import Calendar

DATA_DIR = "data"
SRC_DIR = os.path.join(DATA_DIR, "sources")
README = "README.md"

EVENTS_CSV = os.path.join(DATA_DIR, "events.csv")
EVENTS_JSON = os.path.join(DATA_DIR, "events.json")
JOBS_CSV = os.path.join(DATA_DIR, "jobs.csv")
JOBS_JSON = os.path.join(DATA_DIR, "jobs.json")
INTERNSHIPS_CSV = os.path.join(DATA_DIR, "internships.csv")
INTERNSHIPS_JSON = os.path.join(DATA_DIR, "internships.json")
FULLTIME_CSV = os.path.join(DATA_DIR, "fulltime.csv")
FULLTIME_JSON = os.path.join(DATA_DIR, "fulltime.json")

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

def load_list(path):
    items = []
    if not os.path.exists(path):
        return items
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            items.append(line)
    return items

def to_event_row(event):
    return {
        "date_iso": event.get("date_iso",""),
        "date_human": event.get("date_human",""),
        "name": event.get("name",""),
        "org": event.get("org",""),
        "location": event.get("location","Virtual"),
        "url": event.get("url",""),
        "source": event.get("source",""),
    }

def dedupe_sort_events(events):
    seen = set()
    uniq = []
    for e in events:
        key = (e.get("url",""), e.get("date_iso",""), e.get("name",""))
        if key in seen: continue
        seen.add(key)
        uniq.append(e)
    uniq.sort(key=lambda x: (x.get("date_iso","9999-12-31"), x.get("name","")))
    return uniq

def matches_event_filters(ev):
    name = f"{ev.get('name','')} {ev.get('org','')} {ev.get('source','')}".lower()
    loc  = (ev.get("location","") or "").lower()
    if SEARCH_TERMS and not any(t in name for t in SEARCH_TERMS):
        return False
    if LOCATIONS and all(l not in loc for l in LOCATIONS):
        if loc not in ("virtual","online","remote"):
            return False
    return True

def md_event_table(sample):
    lines = [
        "| Date | Event Name | Company/Org | Location | Link |",
        "|------|------------|-------------|----------|------|",
    ]
    for e in sample:
        lines.append(
            f"| {e.get('date_human') or e.get('date_iso','')} "
            f"| {e.get('name','').replace('|','-')} "
            f"| {e.get('org','').replace('|','-')} "
            f"| {e.get('location','').replace('|','-')} "
            f"| [Register]({e.get('url','')}) |"
        )
    return "\n".join(lines)

def fetch_from_rss(url, label=None):
    out = []
    feed = feedparser.parse(url)
    label = label or (feed.feed.get("title","RSS"))
    for entry in feed.entries:
        title = (entry.get("title") or "").strip()
        link  = (entry.get("link") or "").strip()
        dt = entry.get("published") or entry.get("updated") or ""
        pdt = parse_date(dt) or _guess_date_from_text(title + " " + (entry.get("summary") or ""))
        if not pdt: continue
        ev = {
            "date_iso": pdt.date().isoformat(),
            "date_human": pdt.strftime("%b %d, %Y"),
            "name": title,
            "org": label,
            "location": "Virtual",
            "url": link,
            "source": f"RSS:{label}",
        }
        if matches_event_filters(ev):
            out.append(to_event_row(ev))
    return out

def _guess_date_from_text(txt):
    m = re.findall(r"\b(\d{4}-\d{2}-\d{2})\b", txt)
    if m: return parse_date(m[0])
    m = re.findall(r"\b([A-Za-z]{3,9}\s+\d{1,2},\s*\d{4})\b", txt)
    if m: return parse_date(m[0])
    return None

def fetch_from_ics(url, label=None):
    out = []
    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        cal = Calendar(resp.text)
        for ev in cal.events:
            if not ev.begin: continue
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
                "location": loc,
                "url": str(link),
                "source": f"ICS:{label or 'ICS'}",
            }
            if matches_event_filters(evr):
                out.append(to_event_row(evr))
    except Exception as e:
        print(f"[WARN] ICS fetch failed for {url}: {e}", file=sys.stderr)
    return out

def fetch_greenhouse_events(subdomain):
    out = []
    api_url = f"https://boards-api.greenhouse.io/v1/boards/{subdomain}/jobs"
    try:
        r = requests.get(api_url, timeout=30)
        if r.status_code != 200: return out
        data = r.json()
        for job in data.get("jobs", []):
            title = (job.get("title") or "").strip()
            if not re.search(r"(info session|hiring event|career fair|recruit|open house|virtual event)", title, re.I):
                continue
            dt = parse_date(job.get("updated_at") or job.get("created_at")) or datetime.now(timezone.utc)
            ev = {
                "date_iso": dt.date().isoformat(),
                "date_human": dt.strftime("%b %d, %Y"),
                "name": title,
                "org": subdomain,
                "location": "Virtual",
                "url": job.get("absolute_url"),
                "source": f"Greenhouse:{subdomain}",
            }
            if matches_event_filters(ev):
                out.append(to_event_row(ev))
    except Exception as e:
        print(f"[WARN] Greenhouse events failed for {subdomain}: {e}", file=sys.stderr)
    return out

def dedupe_sort_jobs(rows):
    seen = set()
    uniq = []
    for r in rows:
        key = (r.get("apply_url",""), r.get("title",""), r.get("company",""))
        if key in seen: continue
        seen.add(key)
        uniq.append(r)
    uniq.sort(key=lambda x: (x.get("date_iso","9999-12-31"), x.get("company",""), x.get("title","")))
    return uniq

def jobs_md_table(rows):
    lines = [
        "| Date | Title | Company | Location | Apply |",
        "|------|-------|---------|----------|-------|",
    ]
    for r in rows:
        date = str(r.get('date_human') or r.get('date_iso',''))
        title = str(r.get('title','')).replace('|','-')
        company = str(r.get('company','')).replace('|','-')
        location = str(r.get('location','')).replace('|','-')
        apply_url = r.get('apply_url','')
        lines.append(f"| {date} | {title} | {company} | {location} | [Apply]({apply_url}) |")
    return "\n".join(lines)



def fetch_greenhouse_jobs(subdomain):
    out = []
    api_url = f"https://boards-api.greenhouse.io/v1/boards/{subdomain}/jobs"
    try:
        r = requests.get(api_url, timeout=30)
        if r.status_code != 200: return out
        data = r.json()
        for job in data.get("jobs", []):
            title = (job.get("title") or "").strip()
            if SEARCH_TERMS and not any(t in title.lower() for t in SEARCH_TERMS):
                continue
            locs = [l.get("name","") for l in job.get("offices",[])]
            loc_text = ", ".join([l for l in locs if l]) or (job.get("location","") or "")
            if LOCATIONS and (not any(L in loc_text.lower() for L in LOCATIONS) and "remote" not in loc_text.lower()):
                continue
            url = job.get("absolute_url")
            dt = parse_date(job.get("updated_at") or job.get("created_at")) or datetime.now(timezone.utc)
            out.append({
                "date_iso": dt.date().isoformat(),
                "date_human": dt.strftime("%b %d, %Y"),
                "title": title,
                "company": subdomain,
                "location": loc_text or "Remote",
                "apply_url": url,
                "source": f"Greenhouse:{subdomain}",
            })
    except Exception as e:
        print(f"[WARN] Greenhouse jobs failed for {subdomain}: {e}", file=sys.stderr)
    return out

def fetch_lever_jobs(subdomain):
    out = []
    api_url = f"https://api.lever.co/v0/postings/{subdomain}?mode=json"
    try:
        r = requests.get(api_url, timeout=30)
        if r.status_code != 200: return out
        data = r.json()
        for job in data:
            title = (job.get("text") or job.get("title") or "").strip()
            if SEARCH_TERMS and not any(t in title.lower() for t in SEARCH_TERMS):
                continue
            loc_text = (job.get("categories",{}).get("location") or "")
            if LOCATIONS and (not any(L in loc_text.lower() for L in LOCATIONS) and "remote" not in loc_text.lower()):
                continue
            url = job.get("hostedUrl") or job.get("applyUrl")
            dt = parse_date(job.get("updatedAt")) or datetime.now(timezone.utc)
            out.append({
                "date_iso": dt.date().isoformat(),
                "date_human": dt.strftime("%b %d, %Y"),
                "title": title,
                "company": subdomain,
                "location": loc_text or "Remote",
                "apply_url": url,
                "source": f"Lever:{subdomain}",
            })
    except Exception as e:
        print(f"[WARN] Lever jobs failed for {subdomain}: {e}", file=sys.stderr)
    return out

def categorize_job(job):
    title = (job.get("title","") or "").lower()
    if "intern" in title or "internship" in title:
        return "internship"
    return "fulltime"

def replace_or_append_section(content, header, table_text):
    if header in content:
        return re.sub(
            rf"({re.escape(header)}\s*\n)(?:\|.*\n)+",
            r"\1" + table_text + "\n",
            content,
            flags=re.DOTALL
        )
    else:
        return content + f"\n\n{header}\n\n{table_text}\n"

def update_readme_events(events, readme_path=README):
    table = md_event_table(events[:20])
    try:
        with open(readme_path, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        content = "# Virtual Hiring Events Hub\n"
    content = replace_or_append_section(content, "## Upcoming Events (Auto-updated)", table)
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(content)

def update_readme_jobs(jobs, readme_path=README):
    table = jobs_md_table(jobs[:25])
    try:
        with open(readme_path, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        content = "# Virtual Hiring Events Hub\n"
    content = replace_or_append_section(content, "## Open Roles (Auto-updated)", table)
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(content)

def update_readme_internships(internships, readme_path=README):
    table = jobs_md_table(internships[:20])
    try:
        with open(readme_path,"r",encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        content = "# Virtual Hiring Events Hub\n"
    content = replace_or_append_section(content, "## Internship Roles (Auto-updated)", table)
    with open(readme_path,"w",encoding="utf-8") as f:
        f.write(content)

def update_readme_fulltime(fulltime, readme_path=README):
    table = jobs_md_table(fulltime[:20])
    try:
        with open(readme_path,"r",encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        content = "# Virtual Hiring Events Hub\n"
    content = replace_or_append_section(content, "## Full-Time Opportunities (Auto-updated)", table)
    with open(readme_path,"w",encoding="utf-8") as f:
        f.write(content)

def main():
    events = []
    rss_list = load_list(os.path.join(SRC_DIR, "rss.txt"))
    ics_list = load_list(os.path.join(SRC_DIR, "ics.txt"))
    gh_list  = load_list(os.path.join(SRC_DIR, "greenhouse.txt"))
    lever_list = load_list(os.path.join(SRC_DIR, "lever.txt"))

    for url in rss_list: events += fetch_from_rss(url)
    for url in ics_list: events += fetch_from_ics(url)
    for sub in gh_list: events += fetch_greenhouse_events(sub)

    events = dedupe_sort_events(events)
    pd.DataFrame(events).to_csv(EVENTS_CSV, index=False)
    with open(EVENTS_JSON,"w",encoding="utf-8") as f: json.dump(events,f,indent=2,ensure_ascii=False)

    jobs = []
    for sub in gh_list: jobs += fetch_greenhouse_jobs(sub)
    for sub in lever_list: jobs += fetch_lever_jobs(sub)

    jobs = dedupe_sort_jobs(jobs)
    pd.DataFrame(jobs).to_csv(JOBS_CSV, index=False)
    with open(JOBS_JSON,"w",encoding="utf-8") as f: json.dump(jobs,f,indent=2,ensure_ascii=False)

    internships = [j for j in jobs if categorize_job(j) == "internship"]
    fulltime = [j for j in jobs if categorize_job(j) == "fulltime"]

    pd.DataFrame(internships).to_csv(INTERNSHIPS_CSV, index=False)
    with open(INTERNSHIPS_JSON,"w",encoding="utf-8") as f: json.dump(internships,f,indent=2,ensure_ascii=False)

    pd.DataFrame(fulltime).to_csv(FULLTIME_CSV, index=False)
    with open(FULLTIME_JSON,"w",encoding="utf-8") as f: json.dump(fulltime,f,indent=2,ensure_ascii=False)

    update_readme_events(events)
    update_readme_jobs(jobs)
    update_readme_internships(internships)
    update_readme_fulltime(fulltime)

if __name__ == "__main__":
    main()
