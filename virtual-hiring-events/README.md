# Virtual Hiring Events Hub

Daily auto-updated list of **virtual hiring events, career fairs, and info sessions**.
This repo collects events from public/ToS-friendly sources (RSS, ICS, and Greenhouse job boards) and
updates itself via GitHub Actions.

## How it works
- A scheduled workflow runs **daily**.
- `scripts/update_events.py` pulls events from sources listed in `data/sources/`.
- Events are normalized, deduped, and written to:
  - `data/events.csv`
  - `data/events.json`
- A sample table is injected into the README.

## Configure your sources
Edit the text files under `data/sources/`:

- `rss.txt` — one RSS feed URL per line (e.g., Eventbrite online career fairs).
- `ics.txt` — one ICS calendar URL per line (many universities/communities publish these).
- `greenhouse.txt` — one Greenhouse subdomain per line (e.g., `openai`, `stripe`, `datadog`).
  The script will query public Greenhouse job boards and extract event-like postings if present.

> Pro tip: Start with a few high-signal sources, then grow over time.

## Local run
```bash
pip install -r requirements.txt
python scripts/update_events.py
```

## GitHub Actions
The workflow at `.github/workflows/update-events.yml` runs daily by default.
You can also trigger it manually from the Actions tab.

## Upcoming (sample)

| Date | Event Name | Company/Org | Location | Link |
|------|------------|-------------|----------|------|
| _Auto-filled by workflow_ | | | | |

📦 Full dataset: see `data/events.csv` and `data/events.json`.
