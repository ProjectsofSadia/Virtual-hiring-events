if __name__ == "__main__" and __package__ is None:
    import sys, pathlib
    sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))
    __package__ = "scripts"

import os, json, hashlib
from typing import List, Dict
from urllib.parse import urlparse
import yaml
import requests

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_LATEST = os.path.join(BASE, "data", "latest")
ALERTS_CFG = os.path.join(BASE, "scripts", "alerts.yaml")

def load_cfg() -> dict:
    with open(ALERTS_CFG, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}

def load_latest_jobs() -> List[Dict]:
    path = os.path.join(DATA_LATEST, "jobs.json")
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def matches_filters(job: Dict, cfg: dict) -> bool:
    title = (job.get("title") or "").lower()
    url = job.get("url") or ""
    host = urlparse(url).netloc.lower()
    kw = [k.lower() for k in (cfg.get("alerts", {}).get("keywords") or [])]
    incl = [d.lower() for d in (cfg.get("alerts", {}).get("include_domains") or [])]
    if kw and not any(k in title for k in kw):
        return False
    if incl and not any(d in host for d in incl):
        return False
    return True

def dedupe_key(job: Dict) -> str:
    u = (job.get("url") or "").strip()
    return hashlib.sha256(u.encode("utf-8")).hexdigest()

def load_sent_keys() -> set:
    path = os.path.join(BASE, "data", "alerts_sent.json")
    if not os.path.exists(path):
        return set()
    try:
        with open(path, "r", encoding="utf-8") as f:
            return set(json.load(f))
    except Exception:
        return set()

def save_sent_keys(keys: set):
    path = os.path.join(BASE, "data", "alerts_sent.json")
    os.makedirs(os.path.dirname(path), exist_ok=True
    )
    with open(path, "w", encoding="utf-8") as f:
        json.dump(sorted(list(keys)), f, ensure_ascii=False, indent=2)

def notify_discord(webhook_url: str, jobs: List[Dict]):
    if not jobs:
        return
    content_lines = []
    for j in jobs[:10]:
        content_lines.append(f"• **{j.get('title','')}** — {j.get('company','')}  <{j.get('url')}>")
    payload = {"content": "**New Job Alerts**\n" + "\n".join(content_lines)}
    try:
        requests.post(webhook_url, json=payload, timeout=15)
    except Exception:
        pass

def run():
    cfg = load_cfg()
    jobs = load_latest_jobs()
    sent = load_sent_keys()

    filtered = [j for j in jobs if matches_filters(j, cfg)]
    new_items = []
    for j in filtered:
        k = dedupe_key(j)
        if k in sent:
            continue
        new_items.append(j)
        sent.add(k)

    disc_cfg = (cfg.get("notify", {}).get("discord") or {})
    if disc_cfg.get("enabled"):
        webhook = os.getenv(disc_cfg.get("webhook_secret_name","DISCORD_WEBHOOK_URL"), "")
        if webhook:
            notify_discord(webhook, new_items)

    save_sent_keys(sent)
    print(f"✅ alerts_sent={len(new_items)} | filtered={len(filtered)} | total_jobs={len(jobs)}")

if __name__ == "__main__":
    run()
