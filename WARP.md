# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

This is a Flask-based web application that compares grocery prices across four Dubai stores: Carrefour, Noon, Talabat, and Careem. The application uses web scraping with BeautifulSoup and requests to fetch product data.

**Key Technical Limitation:** Most target stores use JavaScript-heavy SPAs, making simple HTTP scraping ineffective. Current implementation provides a framework that returns placeholder data for Talabat and Careem.

## Architecture

### Application Structure
```
app.py                 # Flask server + scraping logic (single file)
templates/index.html   # Frontend UI (self-contained with inline CSS/JS)
requirements.txt       # Python dependencies
```

### Data Flow
1. User enters search query in frontend
2. Frontend POST request to `/search` endpoint with JSON payload
3. Backend calls 4 scraper functions concurrently
4. Each function returns list of products: `[{'name': str, 'price': str}]`
5. Results aggregated into JSON response: `{'carrefour': [...], 'noon': [...], ...}`
6. Frontend renders results in 4-column grid layout

### Scraper Functions
Each store has a dedicated function in `app.py`:
- `search_carrefour(item)` - Attempts BeautifulSoup scraping (needs updated selectors)
- `search_noon(item)` - Attempts BeautifulSoup scraping (needs updated selectors)
- `search_talabat(item)` - Placeholder (requires JS rendering)
- `search_kareem(item)` - Placeholder (requires JS rendering)

All scrapers return the same structure: list of dicts with 'name' and 'price' keys.

## Common Commands

### Setup & Installation
```bash
# Install dependencies
pip install -r requirements.txt

# For Selenium-based scraping (future enhancement)
pip install selenium
```

### Running the Application
```bash
# Start Flask development server
python app.py

# Access application at http://127.0.0.1:5000
```

### Testing Individual Scrapers
```python
# Test a single scraper function in Python REPL
python3
>>> from app import search_carrefour
>>> results = search_carrefour("milk")
>>> print(results)
```

### Debugging Web Scraping
```bash
# Inspect HTML structure with curl
curl -A "Mozilla/5.0" "https://www.carrefouruae.com/mafuae/en/search?keyword=milk"

# Save response for analysis
curl -A "Mozilla/5.0" "https://www.carrefouruae.com/mafuae/en/search?keyword=milk" > test_response.html
```

## Development Patterns

### Adding a New Store
1. Create a new scraper function following this template:
```python
def search_newstore(item):
    """Search NewStore for item prices"""
    try:
        url = f"https://newstore.com/search?q={item.replace(' ', '+')}"
        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            products = []
            # Add scraping logic here
            return products if products else [{'name': 'No results found', 'price': 'N/A'}]
        return [{'name': 'Error fetching data', 'price': 'N/A'}]
    except Exception as e:
        return [{'name': f'Error: {str(e)}', 'price': 'N/A'}]
```

2. Add to results dict in `/search` route
3. Update frontend grid in `templates/index.html` (add CSS class + store card rendering)

### Updating CSS Selectors
When store websites change:
1. Visit the store's search page in browser
2. Open DevTools (F12) → Network tab → Search for an item
3. Find product cards in Elements tab → Copy selector
4. Update `soup.find_all()` calls in respective function
5. Test with sample item: `python3` → `from app import search_*` → test function

### Converting to Selenium
For JavaScript-rendered sites:
```python
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

def search_store_selenium(item):
    driver = webdriver.Chrome()
    try:
        driver.get(f"https://store.com/search?q={item}")
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "product-card"))
        )
        # Parse products from driver.page_source
    finally:
        driver.quit()
```

## Key Constraints & Gotchas

1. **No Environment Variables:** Application runs without configuration files. URLs and selectors are hardcoded.

2. **No Database:** All data is ephemeral. Each search makes fresh HTTP requests with no caching.

3. **Single-threaded:** Scraper functions run sequentially. Consider `concurrent.futures.ThreadPoolExecutor` for parallel execution.

4. **Error Handling:** All scraper exceptions are caught and return error messages as products. No logging framework.

5. **Rate Limiting:** No delays between requests. May trigger bot detection. Add `time.sleep()` if needed.

6. **User Agent:** Static user agent string. Consider rotation for production use.

## Testing Strategy

No formal test suite exists. Manual testing approach:
1. Start server: `python app.py`
2. Open browser to `http://127.0.0.1:5000`
3. Test various search terms: common items (milk, rice), edge cases (empty, special chars)
4. Verify all 4 store cards render
5. Check browser console for JS errors
6. Check terminal for Flask errors

## Dependencies

Core:
- `flask==3.0.0` - Web framework
- `requests==2.31.0` - HTTP client
- `beautifulsoup4==4.12.2` - HTML parser
- `lxml==5.1.0` - XML/HTML processing

Future (for JS sites):
- `selenium` - Browser automation
- `playwright` - Modern browser automation alternative

## Future Enhancement Areas

Per README.md, priority improvements:
1. **Selenium/Playwright Integration:** Required for Talabat and Careem
2. **Caching Layer:** File-based or Redis to reduce scraping frequency
3. **Selector Configuration:** Move CSS selectors to JSON config file
4. **Parallel Execution:** Use `ThreadPoolExecutor` for concurrent scraping
5. **Price History:** Database (SQLite) to track price changes over time
6. **Proxy Rotation:** Avoid rate limiting and IP blocks
