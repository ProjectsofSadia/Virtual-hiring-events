import os, json
import pandas as pd

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_LATEST = os.path.join(BASE, "data", "latest")
DOCS = os.path.join(BASE, "docs")
os.makedirs(DOCS, exist_ok=True)

def read_latest(name: str):
    path = os.path.join(DATA_LATEST, f"{name}.json")
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def md_table(rows, cols):
    out = []
    out.append("| " + " | ".join(cols) + " |")
    out.append("| " + " | ".join(["---"]*len(cols)) + " |")
    for r in rows:
        out.append("| " + " | ".join(r) + " |")
    return "\n".join(out)

def make_index():
    jobs = read_latest("jobs")
    events = read_latest("events")

    def fmt_date(s): 
        try:
            return pd.to_datetime(s).strftime("%b %d, %Y")
        except:
            return ""

    job_rows = []
    for j in jobs[:50]:
        job_rows.append([
            fmt_date(j.get("published","")),
            (j.get("title") or "").replace("|","/"),
            (j.get("company") or j.get("source","")).replace("|","/"),
            (j.get("location") or "").replace("|","/"),
            f"[Apply]({j.get('url')})"
        ])

    event_rows = []
    for e in events[:50]:
        event_rows.append([
            fmt_date(e.get("published","")),
            (e.get("title") or "").replace("|","/"),
            (e.get("source") or "").replace("|","/"),
            (e.get("location") or ""),
            f"[Link]({e.get('url')})"
        ])

    content = f"""# Virtual Hiring Events Hub

Welcome! This page auto-updates with fresh roles and events.  
*Pro tip:* Open the CSV/JSON for full lists.

##  Upcoming Events (Auto-updated)
{md_table(event_rows or [["", "No events yet", "", "", ""]], ["Date","Event Name","Source","Location","Link"])}

➡️ [View All Events (CSV)](../data/latest/events.csv) | [View All Events (JSON)](../data/latest/events.json)

##  Open Roles (Auto-updated)
{md_table(job_rows or [["", "No jobs yet", "", "", ""]], ["Date","Title","Company/Source","Location","Apply"])}

➡️ [View All Jobs (CSV)](../data/latest/jobs.csv) | [View All Jobs (JSON)](../data/latest/jobs.json)
"""

    with open(os.path.join(DOCS, "index.md"), "w", encoding="utf-8") as f:
        f.write(content)

if __name__ == "__main__":
    make_index()
