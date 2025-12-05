# Quick Start Guide

## Setup (One Time)

```bash
# 1. Run setup script
./setup.sh

# 2. Get OpenRouter API key (free)
# Visit: https://openrouter.ai/
# Sign up and copy your API key

# 3. Add API key to .env file
echo "OPENROUTER_API_KEY=sk-or-v1-your-key-here" > .env

# 4. (Optional) Add cookie files for stores
# Place in Cookies/carrefour.json and Cookies/noon_minutes.json
```

## Run Application

```bash
python3 app.py
```

Visit: http://127.0.0.1:5000

## Test Commands

### Basic Search
```bash
curl -X POST http://localhost:5000/search \
  -H "Content-Type: application/json" \
  -d '{"item": "rice"}'
```

### Search with Price Sorting (Ascending)
```bash
curl -X POST http://localhost:5000/search \
  -H "Content-Type: application/json" \
  -d '{"item": "milk", "sort_by": "price", "sort_order": "asc"}'
```

### Search with Quantity Sorting
```bash
curl -X POST http://localhost:5000/search \
  -H "Content-Type: application/json" \
  -d '{"item": "oil", "sort_by": "quantity", "sort_order": "desc"}'
```

### View Analytics
```bash
# Product comparison
curl http://localhost:5000/api/analytics/products?limit=20

# Search trends
curl http://localhost:5000/api/analytics/trends?days=7

# Price history for product ID 1
curl http://localhost:5000/api/analytics/price-history/1?days=30
```

## Database Queries

```bash
# Count products tracked
sqlite3 grocery_prices.db "SELECT COUNT(*) FROM products;"

# View recent searches
sqlite3 grocery_prices.db "SELECT * FROM search_logs ORDER BY timestamp DESC LIMIT 5;"

# Price comparison for a product
sqlite3 grocery_prices.db "
SELECT p.matched_name, pr.store, pr.price, pr.timestamp
FROM products p
JOIN prices pr ON p.id = pr.product_id
WHERE p.id = 1
ORDER BY pr.timestamp DESC;
"

# Products with biggest price differences
sqlite3 grocery_prices.db "
SELECT 
  p.matched_name,
  MIN(pr.price) as min_price,
  MAX(pr.price) as max_price,
  (MAX(pr.price) - MIN(pr.price)) as difference
FROM products p
JOIN prices pr ON p.id = pr.product_id
GROUP BY p.id
HAVING COUNT(DISTINCT pr.store) >= 2
ORDER BY difference DESC
LIMIT 10;
"
```

## Python Usage

```python
from utils import match_products_with_ai, sort_products, parse_price, extract_quantity
from database import get_product_analytics, get_search_trends
import os

# Parse price
price = parse_price("AED 12.50")  # Returns: 12.50

# Extract quantity
qty, unit = extract_quantity("Bayara Rice 1kg")  # Returns: (1.0, 'kg')

# Get analytics
products = get_product_analytics(limit=10)
for row in products:
    print(dict(row))

# Get search trends
trends = get_search_trends(days=7, limit=5)
for row in trends:
    print(f"{row['query']}: {row['count']} searches")
```

## Troubleshooting

### Issue: AI matching not working
**Check logs for:**
- `[AI Matching] No API key provided` → Add key to .env
- `[AI Matching] API error: 401` → Invalid API key
- `[AI Matching] Using fallback matching` → API unavailable (normal fallback)

### Issue: Database not saving
**Check:**
```bash
ls -l grocery_prices.db  # Should exist
python3 -c "from database import init_database; init_database()"  # Recreate
```

### Issue: Import errors
**Fix:**
```bash
pip3 install -r requirements.txt
```

### Issue: Selenium not working
**Check Chrome installed:**
```bash
# macOS
brew install --cask google-chrome

# Verify chromedriver
python3 -c "from selenium import webdriver; webdriver.Chrome()"
```

## Key Files

- `app.py` - Main Flask application
- `utils.py` - AI matching, sorting, parsing
- `database.py` - SQLite operations
- `.env` - Your API key (DO NOT COMMIT)
- `grocery_prices.db` - Price history database

## API Response Structure

```json
{
  "matched_products": [
    {
      "matched_name": "Product Name - Size",
      "brand": "Brand Name",
      "quantity_value": 1.0,
      "quantity_unit": "kg",
      "stores": {
        "carrefour": {"name": "...", "price": 12.50},
        "noon": {"name": "...", "price": 13.00},
        "talabat": null
      }
    }
  ],
  "raw_results": {...},
  "locations": {...}
}
```

## Environment Variables

```bash
# Required
OPENROUTER_API_KEY=sk-or-v1-...

# Optional (defaults shown)
OPENROUTER_MODEL=meta-llama/llama-3.1-8b-instruct:free
```

## Next Steps

1. ✅ Backend complete - all features working
2. 📝 Update `templates/index.html` for new UI
3. 📊 Create `templates/analytics.html` dashboard
4. 🧪 Write unit tests in `tests/`
5. 🚀 Deploy to production server

For detailed documentation, see:
- `FEATURES.md` - Complete feature documentation
- `IMPLEMENTATION_SUMMARY.md` - Technical implementation details
- `WARP.md` - Project rules and architecture
