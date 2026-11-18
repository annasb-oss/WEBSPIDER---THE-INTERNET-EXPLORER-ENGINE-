# WEBSPIDER — The Internet Explorer Engine

A free, open-source web crawling workspace for collecting and organizing publicly accessible web information.

> WEBSPIDER is in its foundation stage. This first milestone establishes the product interface and API. Crawling, live progress, and export features will be implemented incrementally.

## Product principles

- Clear separation between discovered, visited, and successfully analyzed URLs.
- Respect for each website's `robots.txt`, reasonable request intervals, and applicable terms.
- No authentication bypass, paywall circumvention, or collection of private data.
- Local-first development with free and open-source dependencies.

## Stack

- Python 3.11+
- FastAPI for the API
- HTML, CSS, and vanilla JavaScript for the first interface

## Run locally

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
uvicorn backend.main:app --reload
```

Open http://127.0.0.1:8000. API documentation: http://127.0.0.1:8000/docs.

## Project structure

```text
backend/       API and crawler engine
frontend/      Web interface
exports/       Generated reports (local only)
tests/         Automated tests
```

## Roadmap

- [x] Initial project structure and purple technical interface
- [x] API health endpoint
- [ ] URL validation and crawl configuration
- [ ] Robots.txt-aware crawler and extraction
- [ ] Live execution metrics
- [ ] CSV, JSON, TXT and PDF report exports
- [ ] Automated tests and deployment guide

## License

MIT. See [LICENSE](LICENSE).
