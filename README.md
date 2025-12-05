# Dubai Grocery Price Comparator

A simple web application to compare grocery prices across four popular stores in Dubai:
- **Carrefour**
- **Noon**
- **Talabat**
- **Careem** (formerly Kareem)

## Features

- 🔍 Simple search interface
- 💰 Side-by-side price comparison
- 🎨 Clean, responsive design
- 🖥️ Runs locally on your desktop

## Prerequisites

- Python 3.8 or higher
- pip (Python package manager)

## Installation

1. **Navigate to the project directory:**
   ```bash
   cd /Users/arushdixit/Downloads/AI\ Project/grocery-price-comparator
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

## Usage

1. **Start the application:**
   ```bash
   python app.py
   ```

2. **Open your browser and navigate to:**
   ```
   http://127.0.0.1:5000
   ```

3. **Search for grocery items:**
   - Enter an item name (e.g., "milk", "rice", "apples")
   - Click "Search" or press Enter
   - View prices from all four stores

## Important Notes

⚠️ **Web Scraping Limitations:**
- Many of these stores use JavaScript-heavy websites, which means simple HTTP requests may not work
- The current implementation provides a basic framework that may need adjustments based on actual store website structures
- Some stores may require more sophisticated scraping techniques (like Selenium) or access to their APIs

**Current Implementation:**
- **Carrefour & Noon**: Basic web scraping attempted (may need HTML selectors updated)
- **Talabat & Careem**: Placeholder responses (require JavaScript rendering)

## Improving the Tool

To make this tool more functional, you may need to:

1. **Inspect actual website HTML:**
   - Visit each store's search page
   - Use browser developer tools (F12) to find the correct CSS selectors for product names and prices
   - Update the selector classes in `app.py`

2. **Consider using Selenium:**
   - For JavaScript-heavy sites like Talabat and Careem
   - Install: `pip install selenium`
   - Download ChromeDriver

3. **Look for unofficial APIs:**
   - Some stores may have mobile app APIs that are easier to use
   - Check browser network tab when searching on their websites

4. **Add caching:**
   - Store recent search results to avoid repeated requests
   - Implement simple file-based caching or use Redis

## Project Structure

```
grocery-price-comparator/
├── app.py                 # Flask backend with scraping logic
├── templates/
│   └── index.html        # Web interface
├── requirements.txt      # Python dependencies
└── README.md            # This file
```

## Troubleshooting

**Issue: No prices showing**
- The HTML selectors in `app.py` may need updating
- Check the store websites to see if their structure has changed
- Consider adding print statements to debug what HTML is being received

**Issue: Connection errors**
- Check your internet connection
- Some stores may block automated requests
- Try adding delays between requests or rotating user agents

**Issue: "JavaScript required" messages**
- These stores need browser rendering
- Consider using Selenium or Playwright for full browser automation

## Future Enhancements

- [ ] Add Selenium support for JavaScript-heavy sites
- [ ] Implement result caching
- [ ] Add price history tracking
- [ ] Export comparison results to CSV
- [ ] Add more stores
- [ ] Implement proxy rotation to avoid rate limiting

## License

This is a personal project for learning purposes. Please respect the terms of service of each store when scraping their data.
