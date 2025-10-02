## Changelog

### v1.0.0 – Initial Stable Pipeline (2025-10-02)
Core features delivered:
- Multi‑brand scraping: serveurs (ASUS, Dell, HP, Lenovo, XFusion), stockage (Dell, Lenovo), imprimantes & scanners (Epson, HP)
- Hybrid extraction: product tiles + JSON‑LD + conditional PDP enrichment (HP) with `SKIP_PDP_ENRICH` flag
- Performance flags: `FAST_SCRAPE`, `MAX_PRODUCTS`, `HEADLESS_MODE` (Chrome eager load, image blocking)
- AI normalization (Gemini): structured tech specs, batching, retries, strict JSON policy
- MySQL persistence: idempotent upsert, unique keys `(brand, sku)` + `(brand, link_hash)`, lifecycle fields, optional deactivate missing
- DB CLI: test, list, brands, export (`python -m database.db_cli ...`)
- Documentation: consolidated `README.md` + operational `COMMANDES.md`
- Robustness: safe driver teardown, logging per script, PDP fallback only when needed, modular flags
- Ignore strategy: large JSON artifacts & cleaned outputs excluded from VCS

Engineering improvements:
- Refactored HP scraper to tile‑based collector (dramatic reduction of ancestor XPath overhead)
- Regex heuristics for CPU, cores, RAM, storage, PSU extraction from titles
- DB connector smart column handling (optional description removal)
- Policies to ensure technical-only spec retention

### Earlier Milestones (pre-tag)
- Added Epson scrapers + scheduler orchestration
- Added AI policies & description drop logic
- Added deactivation flag scoping per brand
- Iterative README overhaul & conflict resolution

---
Next candidates (not yet implemented):
- Add CI workflow (lint & smoke scrape with MAX_PRODUCTS=1)
- Extend storage aggregation (e.g. parse multiplicative capacities 2x2TB)
- Add structured unit tests for regex spec parsing
- Optional export to CSV / Parquet
