import requests, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC  = ROOT / "data" / "sources"

def ok(url):
    try:
        r = requests.get(url, timeout=15)
        return r.status_code == 200
    except Exception:
        return False

def clean_lines(p):
    if not p.exists(): return []
    return [l.strip() for l in p.read_text(encoding="utf-8").splitlines() if l.strip() and not l.strip().startswith("#")]

def main():
    gh_in  = clean_lines(SRC / "greenhouse.txt")
    lv_in  = clean_lines(SRC / "lever.txt")

    gh_ok = []
    for s in gh_in:
        # try common board slugs
        urls = [f"https://boards.greenhouse.io/{s}", f"https://boards.greenhouse.io/{s}/jobs", f"https://boards-api.greenhouse.io/v1/boards/{s}/jobs"]
        if any(ok(u) for u in urls):
            gh_ok.append(s)

    lv_ok = []
    for s in lv_in:
        urls = [f"https://jobs.lever.co/{s}", f"https://api.lever.co/v0/postings/{s}?mode=json"]
        if any(ok(u) for u in urls):
            lv_ok.append(s)

    # overwrite with only good slugs
    (SRC / "greenhouse.txt").write_text("\n".join(gh_ok) + ("\n" if gh_ok else ""), encoding="utf-8")
    (SRC / "lever.txt").write_text("\n".join(lv_ok) + ("\n" if lv_ok else ""), encoding="utf-8")

    print("✅ Greenhouse valid:", gh_ok)
    print("✅ Lever valid:", lv_ok)

if __name__ == "__main__":
    main()
