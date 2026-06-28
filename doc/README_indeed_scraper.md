# Indeed Remote Job Scraper

A full-featured scraper that searches Indeed.com for remote jobs using multiple
tech keywords, clicks each card, extracts job details, handles pagination, and
deduplicates results by `jobId + queueId`.

---

## Features

| Feature | Detail |
|---|---|
| **Keywords** | java · python · typescript · javascript |
| **Filter** | Remote jobs only |
| **Pagination** | Auto-follows Next Page (configurable max pages) |
| **Card clicking** | Opens each job card and scrapes the detail pane |
| **Deduplication** | Tracks `jobId + queueId`; skips already-seen jobs across runs |
| **Apply URL** | Captures the external "Apply" button link |
| **Output** | `indeed_jobs.json` + `indeed_jobs.xlsx` |
| **Resume** | Re-running picks up where it left off (`seen_jobs.json`) |

---

## Setup

```bash
# 1. Install Python dependencies
pip install playwright pandas openpyxl

# 2. Install the Chromium browser used by Playwright
python -m playwright install chromium

# 3. Run the scraper
python indeed_scraper.py
```

---

## Output Columns (Excel / JSON)

| Column | Description |
|---|---|
| `jobId` | Indeed job key (`jk=` param) — primary unique ID |
| `queueId` | Queue/tracking key (`from=` or `tk=` param) |
| `keyword` | Which search keyword found this job |
| `title` | Job title |
| `company` | Company name |
| `location` | Location / Remote tag |
| `salary` | Salary range (if shown) |
| `jobType` | Full-time / Part-time / Contract etc. |
| `postedDate` | When posted ("3 days ago" etc.) |
| `applyUrl` | Direct URL of the Apply button |
| `cardUrl` | Indeed viewjob URL |
| `description` | Full job description text |
| `scrapedAt` | UTC timestamp of scrape |

---

## Configuration (top of `indeed_scraper.py`)

```python
KEYWORDS   = ["java", "python", "typescript", "javascript"]  # search terms
MAX_PAGES  = 5        # max pages per keyword (10 jobs/page)
HEADLESS   = True     # False = show browser window
DELAY_MIN  = 1.5      # min seconds between actions
DELAY_MAX  = 3.0      # max seconds between actions
```

---

## Deduplication Logic

- After each job is scraped, its `f"{jobId}_{queueId}"` key is stored in `seen_jobs.json`.
- On subsequent runs (or across keywords), if the same key appears it is **skipped immediately**.
- This means the scraper is **safe to re-run** — it won't duplicate entries.

---

## Tips

- **Indeed blocks aggressive scrapers** — the random delays help avoid this.
- Set `HEADLESS = False` to watch the browser and debug selector issues.
- If jobs stop loading, increase `DELAY_MIN` / `DELAY_MAX`.
- The `seen_jobs.json` file is your persistent dedupe store — delete it to start fresh.
- Excel column widths are auto-sized (capped at 60 chars) for readability.
