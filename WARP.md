# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

This is a Flask-based web application that compares grocery prices across three Dubai stores: Carrefour, Noon, and Talabat.
It uses:
- Selenium + BeautifulSoup scrapers for Carrefour and Noon
- A Talabat Mart HTTP API
- AI-powered product matching via OpenRouter
- A SQLite database for price history and analytics

The UI is a single-page style experience in `templates/index.html` that shows raw results per store and an AI-matched comparison table.

## Architecture

### Application Structure
```text
app.py           # Flask server, Selenium scrapers, routes (/search, /match, /analytics*, /status)
utils.py         # Price parsing, quantity extraction, AI matching & sorting helpers
database.py      # SQLite schema + helpers (products, prices, search_logs)
templates/
  index.html     # Frontend UI (search, raw results, AI-matched table)
Cookies/         # Store cookie JSONs for Selenium sessions
requirements.txt # Python dependencies
FEATURES.md      # Detailed feature documentation
QUICKSTART.md    # Setup & CLI/API examples
WARP.md          # Warp-specific project guidance
```

### Data Flow
1. User enters search query in the frontend.
2. Frontend sends `POST /search` with JSON: `{ "item": "rice" }`.
3. Backend calls three scraper functions in parallel via `ThreadPoolExecutor`:
   - `search_carrefour(item)` (Selenium + BeautifulSoup)
   - `search_noon(item)` (Selenium + BeautifulSoup)
   - `search_talabat(item)` (Talabat Mart JSON API)
4. Each scraper returns `{"products": [{"name": str, "price": str}, ...], "location"?: str}`.
5. `/search` aggregates results into `{"raw_results": {"carrefour": ..., "noon": ..., "talabat": ...}, "locations": {...}}`.
6. Frontend renders raw results per store and then calls `POST /match` with:
   ```json
   {
     "raw_results": { ... },
     "sort_by": "price" | "quantity",
     "sort_order": "asc" | "desc"
   }
   ```
7. `/match` uses `match_products_with_ai` (OpenRouter) and `sort_products` to return a `matched_products` array, and writes matched SKUs/prices to SQLite in a background thread.
8. Analytics endpoints (`/api/analytics/...`) read from SQLite to feed future dashboards.

### Scraper Functions
All scrapers live in `app.py` and ultimately produce a list of `{ 'name': str, 'price': str }`:
- `search_carrefour(item)`
  - Uses a persistent Selenium Chrome session plus `Cookies/carrefour.json`.
  - Navigates to Carrefour search URL and parses HTML with BeautifulSoup.
  - Extracts product name, size/weight, and price.
- `search_noon(item)`
  - Uses a persistent Selenium Chrome session plus `Cookies/noon_minutes.json`.
  - Navigates to Noon Minutes search, waits for product boxes, and parses with BeautifulSoup.
- `search_talabat(item)`
  - Calls Talabat Mart API for a fixed darkstore and parses JSON.
  - Returns up to 20 products as `{name, price}`.

All three functions set status in the `_search_status` dict so `/search-status` can be polled from the UI.

### AI Matching & Sorting
Relevant helpers are in `utils.py`:
- `parse_price(price_str)` – turn strings like `"AED 12.50"` into floats.
- Quantity helpers: `extract_quantity`, `normalize_quantity`.
- `match_products_with_ai(raw_results, openrouter_api_key)` – groups SKUs across stores using OpenRouter.
- `sort_products(matched_products, sort_by, ascending)` – sorts by lowest price or quantity.

The `/match` route in `app.py`:
- Reads `OPENROUTER_API_KEY` and optional `OPENROUTER_MODEL` from `.env`.
- Calls `match_products_with_ai` then `sort_products`.
- Spawns a background thread that calls `save_product_and_prices` to persist to SQLite.

### Database Layer
`database.py` owns all DB concerns:
- `init_database()` – creates tables if missing:
  - `products` – unified SKUs (matched name, brand, quantity).
  - `prices` – timestamped store prices.
  - `search_logs` – basic search telemetry.
- `save_product_and_prices(matched_products)` – writes a batch of matched SKUs + store prices.
- Analytics helpers used by Flask routes:
  - `get_product_analytics(limit)` → `/api/analytics/products`
  - `get_search_trends(days, limit)` → `/api/analytics/trends`
  - `get_price_history(product_id, days)` → `/api/analytics/price-history/<id>`

`grocery_prices.db` is created in the project root on first run.

## Common Commands

### Setup & Installation
```bash
# Install Python dependencies
pip install -r requirements.txt

# Recommended: run project setup (installs deps, creates .env stub, etc.)
./setup.sh

# Add your OpenRouter API key to .env
# OPENROUTER_API_KEY=sk-or-v1-...
```

### Running the Application
```bash
python app.py
# App runs at http://127.0.0.1:5000
```

### Hitting Core Endpoints (manual testing)
```bash
# Raw search results (used by frontend before AI matching)
curl -X POST http://localhost:5000/search \
  -H "Content-Type: application/json" \
  -d '{"item": "rice"}'

# AI matching + sorting (normally called by frontend)
curl -X POST http://localhost:5000/match \
  -H "Content-Type: application/json" \
  -d '{"raw_results": {...}, "sort_by": "price", "sort_order": "asc"}'

# Analytics APIs
curl "http://localhost:5000/api/analytics/products?limit=20"
curl "http://localhost:5000/api/analytics/trends?days=7"
curl "http://localhost:5000/api/analytics/price-history/1?days=30"
```

For more end-to-end examples, see `QUICKSTART.md` and `FEATURES.md`.

## Development Patterns

### Adding a New Store
1. Implement a new `search_newstore(item)` in `app.py`:
```python
import requests
from bs4 import BeautifulSoup

def search_newstore(item: str) -> dict:
    """Search NewStore for item prices and return {"products": [...]}"""
    try:
        url = f"https://newstore.com/search?q={item.replace(' ', '+')}"
        headers = {"User-Agent": "Mozilla/5.0 ..."}
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code != 200:
            return {"products": [{"name": "Error fetching data", "price": "N/A"}]}

        soup = BeautifulSoup(response.content, "html.parser")
        products = []
        # TODO: parse product cards here
        return {"products": products or [{"name": "No results found", "price": "N/A"}]}
    except Exception as e:
        return {"products": [{"name": f"Error: {e}", "price": "N/A"}]}
```
2. Wire it into `/search` using `ThreadPoolExecutor` alongside the existing stores.
3. Update `templates/index.html` to render a new store card (CSS class + section).

### Updating CSS / Selenium Selectors
When store markup changes:
1. Visit the store search page in a browser.
2. Use DevTools → Elements to inspect a single product card.
3. Copy a stable selector (class patterns vs. brittle IDs).
4. Update the relevant `BeautifulSoup` or Selenium `By.CSS_SELECTOR` in `app.py`.
5. Test via `python3` REPL or a one-off script calling `search_*`.

## Key Constraints & Gotchas

1. **Environment variables required:**
   - `OPENROUTER_API_KEY` must be set (via `.env` + `python-dotenv`) for AI matching; without it the matching will fail or fall back.
2. **Selenium & Chrome:**
   - Requires Chrome + a compatible ChromeDriver; failures here surface as scraper errors.
   - A persistent browser pool is maintained; if a browser dies it is recreated.
3. **Database side effects:**
   - `grocery_prices.db` is written in the repo root.
   - Writes happen in a background thread from `/match` to avoid blocking responses.
4. **Concurrency:**
   - Scrapers run in parallel via `ThreadPoolExecutor`; be careful adding blocking I/O or shared global state.
5. **Rate limiting / bot detection:**
   - Heavy use may trigger store protections; respect timeouts and consider adding sleeps or proxy rotation if needed.

## Testing Strategy

Two layers of testing are relevant:

1. **Unit tests** (preferred)
   - Add tests under `tests/` (e.g. `tests/test_utils.py`, `tests/test_database.py`).
   - Run with:
   ```bash
   python -m pytest tests -v
   ```

2. **Manual testing**
   - Start server with `python app.py`.
   - Open `http://127.0.0.1:5000` and try queries like `bayara moong dal`, `milk`, `basmati rice`.
   - Verify:
     - Store status pills update from Loading → Ready.
     - Raw results render for Carrefour, Noon, Talabat.
     - "Match Products with AI" produces a matched SKU table with best-price highlighting.

## Dependencies

Core (see `requirements.txt` for exact versions):
- `flask` – web framework
- `requests` – HTTP client
- `beautifulsoup4` + `lxml` – HTML parsing
- `selenium` – browser automation for JS-heavy sites
- `python-dotenv` – load `.env` for API keys
- `pytest` (dev) – testing

## Future Enhancement Areas

Based on current docs (`FEATURES.md`, `README.md`):
1. **Analytics UI:** Build `templates/analytics.html` backed by existing `/api/analytics/*` endpoints.
2. **Caching layer:** Reduce scraping + AI calls via short-lived caches.
3. **Selector configuration:** Move CSS/XPath selectors into a config module or JSON.
4. **Proxy / user-agent rotation:** Improve robustness against rate limiting.
5. **Price alerts & watchlists:** Use the SQLite history to drive notifications and richer UX.
