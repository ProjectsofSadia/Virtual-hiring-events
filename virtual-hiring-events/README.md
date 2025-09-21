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
| Aug 25, 2025 | Sourcer, Business Recruiting | datadog | Virtual | [Register](https://careers.datadoghq.com/detail/6888865/?gh_jid=6888865) |
| Aug 25, 2025 | Sourcer, Business Recruiting | datadog | Virtual | [Register](https://careers.datadoghq.com/detail/7142207/?gh_jid=7142207) |
| Aug 26, 2025 | Recruiter II, Business Recruiting - London | datadog | Virtual | [Register](https://careers.datadoghq.com/detail/6900429/?gh_jid=6900429) |
| Aug 26, 2025 | Senior Recruiter, Tech Recruiting | datadog | Virtual | [Register](https://careers.datadoghq.com/detail/7089557/?gh_jid=7089557) |
| Aug 26, 2025 | Senior Recruiter, Tech Recruiting | datadog | Virtual | [Register](https://careers.datadoghq.com/detail/7105200/?gh_jid=7105200) |
| Sep 09, 2025 | Core Recruiter (Fixed Term Contract) | stripe | Virtual | [Register](https://stripe.com/jobs/search?gh_jid=7216261) |
| Sep 09, 2025 | Go-To-Market Recruiter (Fixed Term Contract) | stripe | Virtual | [Register](https://stripe.com/jobs/search?gh_jid=7231138) |
| Sep 09, 2025 | Go-To-Market Recruiter (Fixed Term Contract) | stripe | Virtual | [Register](https://stripe.com/jobs/search?gh_jid=7228783) |
| Sep 09, 2025 | Go-To-Market Recruiter (Fixed Term Contract) | stripe | Virtual | [Register](https://stripe.com/jobs/search?gh_jid=7216346) |
| Sep 09, 2025 | Recruiting Product Marketing Manager | stripe | Virtual | [Register](https://stripe.com/jobs/search?gh_jid=7185485) |
| Sep 10, 2025 | Recruiting Coordination Manager | stripe | Virtual | [Register](https://stripe.com/jobs/search?gh_jid=7229581) |
| Sep 10, 2025 | Recruiting Scheduler | stripe | Virtual | [Register](https://stripe.com/jobs/search?gh_jid=7229583) |
| Sep 11, 2025 | Recruiter II, Business Recruiting | datadog | Virtual | [Register](https://careers.datadoghq.com/detail/7235437/?gh_jid=7235437) |
| Sep 15, 2025 | Senior Recruiter, Business Recruiting | datadog | Virtual | [Register](https://careers.datadoghq.com/detail/7235421/?gh_jid=7235421) |
| Sep 16, 2025 | Business Recruiter (Fixed Term Contract) | stripe | Virtual | [Register](https://stripe.com/jobs/search?gh_jid=7233201) |
| Sep 16, 2025 | Go-To-Market Recruiter (Fixed Term Contract) | stripe | Virtual | [Register](https://stripe.com/jobs/search?gh_jid=7249012) |
| Sep 16, 2025 | Go-To-Market Recruiter (Fixed Term Contract) | stripe | Virtual | [Register](https://stripe.com/jobs/search?gh_jid=7218467) |
| Sep 18, 2025 | Recruiting Scheduler (Fixed Term Contract) | stripe | Virtual | [Register](https://stripe.com/jobs/search?gh_jid=7228682) |
| Sep 19, 2025 | Recruiter - Sales - Contract | datadog | Virtual | [Register](https://careers.datadoghq.com/detail/7082196/?gh_jid=7082196) |
