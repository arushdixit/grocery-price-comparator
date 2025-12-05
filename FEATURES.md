# New Features Documentation

## Overview
This document describes the new features added to the Grocery Price Comparator application.

## Features Implemented

### 1. AI-Powered Product Matching (P0)

**Description:** Uses OpenRouter API with LLM to intelligently match products across stores based on brand AND weight/volume.

**Key Capabilities:**
- Matches "Bayara Moong Dal 1kg" separately from "Bayara Moong Dal 800g"
- Handles spelling variations
- Extracts brand names and quantities automatically
- Falls back to rule-based matching if API unavailable

**Configuration:**
1. Copy `.env.example` to `.env`
2. Add your OpenRouter API key:
   ```
   OPENROUTER_API_KEY=your_key_here
   ```
3. Optional: Change model (default is free Llama 3.1):
   ```
   OPENROUTER_MODEL=meta-llama/llama-3.1-8b-instruct:free
   ```

**API Endpoint:**
- Automatic - integrated into `/search` endpoint
- Returns `matched_products` array with unified product information

**Response Format:**
```json
{
  "matched_products": [
    {
      "matched_name": "Bayara Moong Dal - 1kg",
      "brand": "Bayara",
      "quantity_value": 1.0,
      "quantity_unit": "kg",
      "stores": {
        "carrefour": {"name": "...", "price": 12.50},
        "noon": {"name": "...", "price": 13.00},
        "talabat": null
      }
    }
  ]
}
```

### 2. Sort by Price (P0)

**Description:** Products are sorted by lowest available price in ascending order by default.

**Usage:**
```javascript
// Frontend request
fetch('/search', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    item: 'rice',
    sort_by: 'price',
    sort_order: 'asc'  // or 'desc'
  })
})
```

**Features:**
- Compares prices across all stores for each SKU
- Sorts by minimum available price
- Handles missing prices gracefully

### 3. Sort by Weight/Volume (P0)

**Description:** Sort products by their normalized quantity (kg→g, L→mL).

**Usage:**
```javascript
// Frontend request
fetch('/search', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({
    item: 'milk',
    sort_by: 'quantity',
    sort_order: 'asc'  // smallest to largest
  })
})
```

**Supported Units:**
- Weight: kg, g, grams, kilograms
- Volume: l, ml, ltr, litre, liter
- Multi-pack: "2 x 500g", "3 pack x 1kg"

### 4. Price History Database (P1)

**Description:** SQLite database tracking all price points with timestamps for analytics.

**Database Schema:**

**Products Table:**
- `id`: Primary key
- `matched_name`: Unique product identifier
- `brand`: Extracted brand name
- `quantity_value`: Numeric quantity
- `quantity_unit`: Unit (kg, g, l, ml)
- `created_at`: First seen timestamp

**Prices Table:**
- `id`: Primary key
- `product_id`: Foreign key to products
- `store`: Store name (carrefour, noon, talabat)
- `price`: Numeric price
- `raw_name`: Original product name from store
- `timestamp`: Price capture time

**Search Logs Table:**
- `id`: Primary key
- `query`: User search query
- `result_count`: Number of matched products
- `timestamp`: Search time

**Analytics Endpoints:**

1. **Product Analytics**
   ```
   GET /api/analytics/products?limit=100
   ```
   Returns latest prices for all products across stores.

2. **Search Trends**
   ```
   GET /api/analytics/trends?days=7&limit=20
   ```
   Returns most popular search queries in timeframe.

3. **Price History**
   ```
   GET /api/analytics/price-history/{product_id}?days=30
   ```
   Returns historical prices for specific product.

4. **Dashboard Page**
   ```
   GET /analytics
   ```
   Web interface for viewing analytics (needs frontend implementation).

## Setup Instructions

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
# Copy example env file
cp .env.example .env

# Edit .env and add your OpenRouter API key
# Get free key at: https://openrouter.ai/
```

### 3. Initialize Database
Database is automatically created on first run at `grocery_prices.db`.

### 4. Run Application
```bash
python app.py
```

## API Usage Examples

### Basic Search with Sorting
```python
import requests

response = requests.post('http://localhost:5000/search', json={
    'item': 'basmati rice',
    'sort_by': 'price',
    'sort_order': 'asc'
})

data = response.json()
matched_products = data['matched_products']

for product in matched_products:
    print(f"{product['matched_name']}")
    for store, info in product['stores'].items():
        if info:
            print(f"  {store}: AED {info['price']}")
```

### Get Analytics Data
```python
import requests

# Get product price comparison
response = requests.get('http://localhost:5000/api/analytics/products?limit=50')
products = response.json()['products']

for product in products:
    print(f"{product['matched_name']}")
    print(f"  Carrefour: AED {product['carrefour_price']}")
    print(f"  Noon: AED {product['noon_price']}")
    print(f"  Talabat: AED {product['talabat_price']}")
```

## Utility Functions

The `utils.py` module provides helper functions:

### `parse_price(price_str)`
Extracts numeric value from price strings.
```python
from utils import parse_price
parse_price("AED 12.50")  # Returns 12.50
parse_price("12,50 AED")  # Returns 12.50
```

### `extract_quantity(product_name)`
Extracts quantity value and unit from product name.
```python
from utils import extract_quantity
extract_quantity("Bayara Moong Dal 1kg")  # Returns (1.0, 'kg')
extract_quantity("Nestle Milk 500ml")     # Returns (500.0, 'ml')
```

### `normalize_quantity(value, unit)`
Converts quantities to base units (g for weight, ml for volume).
```python
from utils import normalize_quantity
normalize_quantity(1, 'kg')   # Returns 1000 (grams)
normalize_quantity(1.5, 'l')  # Returns 1500 (milliliters)
```

## Performance Considerations

### AI Matching
- **Latency:** Adds 2-5 seconds per search due to LLM API call
- **Cost:** Free tier limits apply (check OpenRouter pricing)
- **Fallback:** Automatic rule-based matching if API fails

### Database Operations
- **Async Writes:** Database saves happen in background threads
- **No Read Latency:** Search responses not blocked by DB writes
- **Indexes:** Optimized queries for analytics dashboard

### Caching (Future Enhancement)
Currently no caching implemented. Consider adding:
- Redis/memcached for AI matching results (5-10 min TTL)
- Product mapping cache to reduce API calls

## Testing

### Unit Tests
```bash
# Run unit tests for utility functions
python -m pytest tests/test_utils.py -v

# Test database operations
python -m pytest tests/test_database.py -v
```

### Manual Testing
```bash
# Test AI matching
curl -X POST http://localhost:5000/search \
  -H "Content-Type: application/json" \
  -d '{"item": "rice", "sort_by": "price"}'

# Test analytics
curl http://localhost:5000/api/analytics/products?limit=10

# Test search trends
curl http://localhost:5000/api/analytics/trends?days=7
```

## Troubleshooting

### AI Matching Not Working
1. Check `.env` file exists and contains valid API key
2. Verify API key has credits: https://openrouter.ai/account
3. Check logs for error messages: `[AI Matching] Error: ...`
4. Falls back to rule-based matching automatically

### Database Errors
1. Check write permissions in application directory
2. Delete `grocery_prices.db` to recreate from scratch
3. Ensure SQLite3 is installed: `sqlite3 --version`

### Sorting Issues
1. Verify products have quantity data in `quantity_value` field
2. Check price fields are numeric (not strings)
3. Review logs for parsing warnings

## Future Enhancements

### Short Term
- [ ] Frontend UI for matched products view
- [ ] Visual analytics dashboard with charts
- [ ] Export analytics data to CSV/Excel
- [ ] Email price alerts for watched products

### Long Term
- [ ] Price prediction using historical data
- [ ] Multi-city support (currently Dubai-focused)
- [ ] User accounts and watchlists
- [ ] Mobile app integration
- [ ] Real-time price change notifications

## Architecture Diagram

```
┌─────────────────┐
│   User Request  │
└────────┬────────┘
         │
         v
┌─────────────────┐      ┌──────────────┐
│  Flask Server   │─────>│   Scrapers   │
│                 │      │  (Parallel)  │
└────────┬────────┘      └──────┬───────┘
         │                      │
         v                      v
┌─────────────────┐      ┌──────────────┐
│  OpenRouter AI  │<─────│ Raw Results  │
│   Matching      │      └──────────────┘
└────────┬────────┘
         │
         v
┌─────────────────┐
│  Matched SKUs   │
│  + Sorting      │
└────────┬────────┘
         │
         ├──────────────────┐
         v                  v
┌─────────────────┐  ┌────────────┐
│  JSON Response  │  │  Database  │
│  to Frontend    │  │  (Async)   │
└─────────────────┘  └────────────┘
```

## License
Same as parent project.
