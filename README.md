# WEBSPIDER — The Internet Explorer Engine

A free, open-source crawler for discovering and organizing publicly accessible web pages.

## Current features

- Same-origin crawling (the crawler stays on the starting website).
- Reads and follows the site's `robots.txt` rules.
- Configurable limit of 1–50 pages and depth of 0–3.
- One request at a time with a one-second pause between page requests.
- Extracts page title, meta description, a short text preview and discovered links.
- Live dashboard updates through API polling.
- CSV export after a crawl.
- Blocks localhost, private, reserved and non-public IP destinations, including redirects to another origin.
- Limits downloaded response bodies to 2 MB per request.
- Stops safely when robots.txt cannot be verified or returns an access/rate-limit/server error.

## Run locally

Requires Python 3.11+.

```bash
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
uvicorn backend.main:app --reload
```

Open http://127.0.0.1:8000. API docs: http://127.0.0.1:8000/docs.

## How to use

1. Enter a public website URL (for example, your own website or a site that permits crawling).
2. Choose the page and depth limits.
3. Start the crawl and watch the metrics and event log update.
4. Download the CSV report when the run finishes.

## Responsible-use limits

WEBSPIDER is intentionally conservative: it only follows links on the starting origin, honors robots.txt, applies a delay between requests, and does not bypass logins, paywalls, rate limits or other access controls. Use it only on websites you own or are authorized to crawl, and check each site's terms and applicable law. Robots.txt is a crawler preference protocol, not legal permission.

The crawler runs in the API process. Active jobs and results are held in memory and are cleared when the server restarts. This is an early local-first milestone, not a hosted multi-user service.

## Structure

```text
backend/       API and crawler engine
frontend/      Web interface
exports/       Reserved for local reports
tests/         Automated tests
```

## Roadmap

- [x] API health endpoint
- [x] URL validation and crawl configuration
- [x] robots.txt-aware same-origin crawler
- [x] Live execution metrics
- [x] CSV report export
- [ ] JSON and TXT report exports
- [x] Initial automated URL-validation tests
- [ ] Expanded integration tests and deployment guide

## License

MIT. See [LICENSE](LICENSE).
