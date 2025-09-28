import os, json, hashlib
from typing import List, Dict
import pandas as pd

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(BASE, "data")
LATEST = os.path.join(DATA_DIR, "latest")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LATEST, exist_ok=True)

def _db_path(name: str) -> str:
    return os.path.join(DATA_DIR, f"{name}.jsonl")

def key_for(item: Dict) -> str:
    u = (item.get("url") or "").strip()
    return hashlib.sha256(u.encode("utf-8")).hexdigest()

def load_keys(name: str) -> set:
    keys = set()
    path = _db_path(name)
    if not os.path.exists(path): 
        return keys
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                obj = json.loads(line)
                if "_k" in obj:
                    keys.add(obj["_k"])
            except:
                pass
    return keys

def append_items(name: str, items: List[Dict]) -> int:
    path = _db_path(name)
    seen = load_keys(name)
    added = 0
    with open(path, "a", encoding="utf-8") as f:
        for it in items:
            it["_k"] = key_for(it)
            if not it.get("url"):
                continue
            if it["_k"] in seen:
                continue
            f.write(json.dumps(it, ensure_ascii=False) + "\n")
            seen.add(it["_k"])
            added += 1
    return added

def export_latest(name: str):
    path = _db_path(name)
    rows = []
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    rows.append(json.loads(line))
                except:
                    pass
    if not rows:
        return
    df = pd.DataFrame(rows)
    if "published" in df.columns:
        df["published"] = pd.to_datetime(df["published"], errors="coerce", utc=True)
        df = df.sort_values("published", ascending=False, na_position="last")
    out_csv = os.path.join(LATEST, f"{name}.csv")
    out_json = os.path.join(LATEST, f"{name}.json")
    df.to_csv(out_csv, index=False)
    df.to_json(out_json, orient="records", force_ascii=False, indent=2)
