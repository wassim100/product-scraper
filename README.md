# Selenium Scraper Suite

Production-ready scraping suite for servers, storage, and printers/scanners. It orchestrates Selenium scrapers, optional Gemini-based cleaning, and MySQL storage via a central scheduler.

## Highlights

- Central scheduler (filter by categories or scripts)
- Gemini cleaning (optional) with batching and retries
- MySQL upserts with brand-scoped deactivate-missing
- Safe testing flags: headless, max products, deactivate toggle
- Per-script logs and JSON artifacts

## Setup

1) Python 3.11+ (3.12 recommended)
2) pip install -r requirements.txt
3) Create .env with DB creds and GEMINI_API_KEY

## Run via scheduler

- All: python -m automation.scheduler
- Only printers/scanners: set SCHEDULER_CATEGORIES=imprimantes_scanners
- Only Epson scripts: set SCHEDULER_SCRIPTS=EpsonPrinters.py,EpsonScanner.py

Env flags:
- HEADLESS_MODE=true|false (default true)
- ENABLE_DB=true|false (default true)
- ENABLE_AI_CLEANING=true|false (default true)
- ENABLE_DEACTIVATE_MISSING=true|false (default true)
- MAX_PRODUCTS=0 (0 = no limit)
- SCHEDULER_CATEGORIES=serveurs,stockage,imprimantes_scanners
- SCHEDULER_SCRIPTS=comma-separated names
- MYSQL_HOST, MYSQL_PORT, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DATABASE
- GEMINI_API_KEY

## Epson scripts

- imprimantes_scanners/EpsonPrinters.py → epson_printers_scanners_full.json
- imprimantes_scanners/EpsonScanner.py → epson_scanners_full.json

When RUNNING_UNDER_SCHEDULER=true, scrapers skip direct DB writes; the scheduler handles AI + DB.

## Notes

- Logs: logs/ per run
- Selenium: Chrome; keep chromedriver.exe or rely on Selenium Manager
- MySQL: Unique (brand, sku) and (brand, link_hash); lifecycle fields present
- AI cleaning: see ai_processing/gemini_cleaning.py

## Troubleshooting

- Script names must match scheduler entries (EpsonPrinters.py, EpsonScanner.py)
- For partial tests: set MAX_PRODUCTS>0 and ENABLE_DEACTIVATE_MISSING=false
- Git: ensure local main tracks origin/main before pushing

## License

MIT
