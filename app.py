from flask import Flask, render_template, request, jsonify
import requests
from bs4 import BeautifulSoup
import time
import os
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from dotenv import load_dotenv

# Import our custom modules
from utils import match_products, sort_products, parse_price
from database import save_product_and_prices, log_search, get_product_analytics, get_search_trends, get_price_history

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Cookies files
NOON_COOKIES_FILE = 'Cookies/noon_minutes.json'
CARREFOUR_COOKIES_FILE = 'Cookies/carrefour.json'

# Persistent browser pool
_browser_pool = {
    'carrefour': None,
    'noon': None
}

# Browser preload status
_preload_status = {
    'carrefour': 'not_started',  # not_started, loading, ready, error
    'noon': 'not_started',
    'talabat': 'ready'  # Talabat doesn't use Selenium
}

# Active search status
_search_status = {
    'carrefour': 'ready',  # ready, searching, complete
    'noon': 'ready',
    'talabat': 'ready'
}

def get_chrome_driver():
    """Create a new Chrome driver with standard options"""
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_argument('user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    return webdriver.Chrome(options=chrome_options)

def get_or_create_browser(store_name, base_url, cookies_file=None):
    """Get existing browser or create new one with cookies loaded"""
    global _browser_pool
    
    # Return existing browser if available
    if _browser_pool.get(store_name) is not None:
        try:
            # Test if browser is still alive
            _browser_pool[store_name].current_url
            return _browser_pool[store_name], False  # False = not newly created
        except:
            # Browser died, clean up
            _browser_pool[store_name] = None
    
    # Create new browser
    print(f"[{store_name}] Initializing new browser session...")
    driver = get_chrome_driver()
    driver.get(base_url)
    
    # Load cookies if provided
    if cookies_file and os.path.exists(cookies_file):
        try:
            with open(cookies_file, 'r') as f:
                cookies = json.load(f)
                cookie_count = 0
                for cookie in cookies:
                    try:
                        selenium_cookie = {
                            'name': cookie['name'],
                            'value': cookie['value'],
                            'domain': cookie['domain'],
                            'path': cookie.get('path', '/'),
                            'secure': cookie.get('secure', False)
                        }
                        if 'expirationDate' in cookie:
                            selenium_cookie['expiry'] = int(cookie['expirationDate'])
                        driver.add_cookie(selenium_cookie)
                        cookie_count += 1
                    except:
                        continue
                print(f"[{store_name}] Added {cookie_count} cookies")
        except Exception as e:
            print(f"[{store_name}] Error loading cookies: {str(e)}")
    
    _browser_pool[store_name] = driver
    return driver, True  # True = newly created

def search_carrefour(item):
    """Search Carrefour UAE for item prices using Selenium"""
    global _search_status
    _search_status['carrefour'] = 'searching'
    start_time = time.time()
    print(f"[Carrefour] Starting search for '{item}'...")
    location = None
    try:
        # Get or create persistent browser
        driver, is_new = get_or_create_browser('Carrefour', 'https://www.carrefouruae.com/mafuae/en/', CARREFOUR_COOKIES_FILE)
        
        # Detect location only on first load
        if is_new:
            time.sleep(1)
            try:
                location_elem = driver.find_element(By.CSS_SELECTOR, "div.max-w-\\[250px\\].truncate, div.max-w-\\[220px\\].truncate")
                location = location_elem.text.strip()
                if location:
                    print(f"[Carrefour] Detected location: {location}")
                else:
                    print("[Carrefour] ⚠️  Could not detect location")
            except:
                print("[Carrefour] ⚠️  Could not detect location - results may be for default area")
        
        # Navigate to search URL
        url = f"https://www.carrefouruae.com/mafuae/en/search?keyword={item.replace(' ', '%20')}"
        driver.get(url)
        
        # Wait for products to load
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div[class*='max-w-']")))
        time.sleep(1)
        
        # Parse with BeautifulSoup
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        products = []
        
        # Find product containers
        # User provided HTML shows root is div.relative containing the product card
        # We need a robust selector. The user snippet has `class="relative flex overflow-hidden rounded-xl ..."`
        # Let's target the anchor tag which seems central: `a` with href containing `/p/` usually?
        # Or `div` with `rounded-xl border-solid bg-white`.
        
        # Find product containers - Reverting to broader selector
        product_containers = soup.find_all('div', class_=lambda x: x and 'max-w-' in str(x) and 'sm:max-w-' in str(x))
        
        for container in product_containers[:40]: # Increased limit to ensure we hit results
            try:
                # Find the link with product name (skip labels like "Bestseller")
                link = container.find('a', href=True)
                if not link:
                    continue
                
                # Extract name from span within the product link (not label)
                name_div = link.find('div', class_=lambda x: x and 'line-clamp-2' in str(x))
                if not name_div:
                    continue
                name_elem = name_div.find('span')
                if not name_elem:
                    continue
                name = name_elem.text.strip()
                
                # Skip if name is empty or is a label like "Bestseller"
                if not name or name.lower() in ['bestseller', 'new', 'offer']:
                    continue
                
                # Extract description (size/weight info)
                desc_elem = container.find('div', class_=lambda x: x and 'text-gray-500' in str(x) and 'truncate' in str(x))
                if desc_elem:
                    name += f" - {desc_elem.text.strip()}"
                
                # Extract price - look for the main price div with force-ltr class
                price_container = container.find('div', class_=lambda x: x and 'force-ltr' in str(x))
                if price_container:
                    # Get the large price number
                    price_main = price_container.find('div', class_=lambda x: x and 'font-bold' in str(x))
                    # Get the decimal part
                    price_decimal_container = price_main.find_next_sibling('div') if price_main else None
                    
                    if price_main:
                        price_text = price_main.text.strip()
                        if price_decimal_container:
                            decimal = price_decimal_container.find('div', class_=lambda x: x and 'leading-' in str(x))
                            if decimal:
                                price_text += decimal.text.strip()
                        price_text += " AED"
                        
                        # Extract Image
                        image_url = None
                        try:
                            # User provided specific class: rounded-lg object-contain
                            img_elem = container.find('img', class_=lambda x: x and 'rounded-lg' in x and 'object-contain' in x)
                            if not img_elem:
                                # Fallback to generic
                                img_elem = container.find('img')
                            
                            if img_elem:
                                image_url = img_elem.get('src') or img_elem.get('data-src')
                        except:
                            pass

                        # Extract Product URL
                        product_url = None
                        if link.get('href'):
                            product_url = "https://www.carrefouruae.com" + link.get('href')

                        products.append({
                            'name': name,
                            'price': price_text,
                            'image_url': image_url,
                            'product_url': product_url
                        })
            except Exception:
                continue
        
        elapsed = time.time() - start_time
        print(f"[Carrefour] Completed in {elapsed:.2f}s - Found {len(products)} products")
        _search_status['carrefour'] = 'complete'
        result = {'products': products if products else [{'name': 'No results found', 'price': 'N/A'}]}
        if location:
            result['location'] = location
        return result
        
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"[Carrefour] Error in {elapsed:.2f}s - {str(e)}")
        _search_status['carrefour'] = 'complete'
        return {'products': [{'name': f'Error: {str(e)}', 'price': 'N/A'}]}

def search_noon(item):
    """Search Noon for item prices using Selenium"""
    global _search_status
    _search_status['noon'] = 'searching'
    start_time = time.time()
    print(f"[Noon] Starting search for '{item}'...")
    location = None
    try:
        # Get or create persistent browser
        driver, is_new = get_or_create_browser('Noon', 'https://minutes.noon.com/uae-en/', NOON_COOKIES_FILE)
        
        # Detect location only on first load
        if is_new:
            time.sleep(1)
            try:
                location_elem = driver.find_element(By.CSS_SELECTOR, "span.AddressHeader_addressText__kMyss")
                location = location_elem.text.strip()
                print(f"[Noon] Detected location: {location}")
            except:
                print("[Noon] ⚠️  Could not detect location - results may be for default area")
        
        # Navigate to search URL
        url = f"https://minutes.noon.com/uae-en/search/?q={item.replace(' ', '%20')}"
        driver.get(url)
        
        # Wait for products to load (wait for product boxes)
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div[class*='ProductBox_detailsSection']")))
        
        # Additional wait for dynamic content
        time.sleep(1)
        
        # Parse with BeautifulSoup
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        products = []
        
        # Find single product items directly
        # User HTML: <a class="ProductBox_wrapper__LfrFV" href="...">
        product_boxes = soup.find_all('a', class_=lambda x: x and 'ProductBox_wrapper' in x)
        
        for product in product_boxes[:20]:
            try:
                # 1. Product URL (The element itself is the anchor)
                product_url = None
                href = product.get('href')
                if href:
                     product_url = f"https://minutes.noon.com{href}" if href.startswith('/') else href

                # 2. Image
                image_url = None
                # HTML: <div class="ProductBox_imageSection__e0hHc"><img ...>
                img_section = product.find('div', class_=lambda x: x and 'ProductBox_imageSection' in x)
                if img_section:
                    img_elem = img_section.find('img')
                    if img_elem:
                        image_url = img_elem.get('src')
                
                # 3. Details (Name, Price, Size)
                # HTML: <div class="ProductBox_detailsSection__gmA8X">...
                details = product.find('div', class_=lambda x: x and 'ProductBox_detailsSection' in x)
                if not details:
                    continue

                name_elem = product.find('h2', class_=lambda x: x and 'ProductBox_title' in x)
                # Fallback if h2 not found (sometimes it's just a div)
                if not name_elem:
                    name_elem = product.find('div', class_=lambda x: x and 'ProductBox_title' in x)
                    
                price_elem = product.find('strong', class_=lambda x: x and 'Price_productPrice' in x)
                # Ensure price is within THIS product (scoped find should guarantee this)
                
                size_elem = product.find('span', class_=lambda x: x and 'ProductBox_sizeInfo' in x)
                # Origin might be elsewhere or strictly in details? User didn't enable origin in snippet.
                
                if name_elem and price_elem:
                    name = name_elem.text.strip()
                    
                    if size_elem:
                        name += f" - {size_elem.text.strip()}"
                    
                    products.append({
                        'name': name,
                        'price': f"AED {price_elem.text.strip()}",
                        'image_url': image_url,
                        'product_url': product_url
                    })
            except:
                continue
        
        elapsed = time.time() - start_time
        print(f"[Noon] Completed in {elapsed:.2f}s - Found {len(products)} products")
        _search_status['noon'] = 'complete'
        result = {'products': products if products else [{'name': 'No results found', 'price': 'N/A'}]}
        if location:
            result['location'] = location
        return result
        
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"[Noon] Error in {elapsed:.2f}s - {str(e)}")
        _search_status['noon'] = 'complete'
        return {'products': [{'name': f'Error: {str(e)}', 'price': 'N/A'}]}

def search_talabat(item):
    """Search Talabat for item prices via API"""
    global _search_status
    _search_status['talabat'] = 'searching'
    start_time = time.time()
    print(f"[Talabat] Starting search for '{item}'...")
    try:
        # Talabat Mart API endpoint
        # Store ID: c249bcfd-9962-4a51-adf0-ff8dabc185fa (The Palm Jumeirah)
        url = f"https://www.talabat.com/nextApi/groceries/stores/c249bcfd-9962-4a51-adf0-ff8dabc185fa/products"
        params = {
            'countryId': '4',  # UAE
            'query': item,
            'limit': '20',
            'offset': '0',
            'isDarkstore': 'true',
            'isMigrated': 'false',
            'lang': 'en'  # Force English results
        }
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9'
        }
        response = requests.get(url, params=params, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            items = data.get('items', [])
            products = []
            
            for product in items[:60]:
                try:
                    title = product.get('title', '')
                    price = product.get('price')
                    
                    if title and price is not None:
                        # Extract Image
                        image_url = None
                        if product.get('images') and len(product.get('images')) > 0:
                            image_url = product.get('images')[0]
                        elif product.get('image'):
                             image_url = product.get('image')

                        # Extract Product URL
                        # Pattern: https://www.talabat.com/uae/grocery/673755/talabat-mart-palm-jumeirah/product/<slug>/s/<sku>?aid=1308
                        slug = product.get('slug')
                        sku = product.get('sku')
                        
                        product_url = None
                        if slug and sku:
                             product_url = f"https://www.talabat.com/uae/grocery/673755/talabat-mart-palm-jumeirah/product/{slug}/s/{sku}?aid=1308"
                        
                        products.append({
                            'name': title,
                            'price': f"AED {price}",
                            'image_url': image_url,
                            'product_url': product_url # Likely None for API
                        })
                except:
                    continue
            
            elapsed = time.time() - start_time
            print(f"[Talabat] Completed in {elapsed:.2f}s - Found {len(products)} products")
            _search_status['talabat'] = 'complete'
            return {'products': products if products else [{'name': 'No results found', 'price': 'N/A'}]}
        else:
            elapsed = time.time() - start_time
            print(f"[Talabat] Failed in {elapsed:.2f}s with status code {response.status_code}")
            _search_status['talabat'] = 'complete'
            return {'products': [{'name': 'Error fetching data', 'price': 'N/A'}]}
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"[Talabat] Error in {elapsed:.2f}s - {str(e)}")
        _search_status['talabat'] = 'complete'
        return {'products': [{'name': f'Error: {str(e)}', 'price': 'N/A'}]}


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analytics')
def analytics():
    """Analytics dashboard page"""
    return render_template('analytics.html')

@app.route('/api/analytics/products')
def analytics_products():
    """Get product analytics data"""
    limit = request.args.get('limit', 100, type=int)
    try:
        products = get_product_analytics(limit=limit)
        return jsonify({
            'products': [dict(row) for row in products]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics/trends')
def analytics_trends():
    """Get search trends"""
    days = request.args.get('days', 7, type=int)
    limit = request.args.get('limit', 20, type=int)
    try:
        trends = get_search_trends(days=days, limit=limit)
        return jsonify({
            'trends': [dict(row) for row in trends]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics/price-history/<int:product_id>')
def analytics_price_history(product_id):
    """Get price history for a specific product"""
    days = request.args.get('days', 30, type=int)
    try:
        history = get_price_history(product_id, days=days)
        return jsonify({
            'history': [dict(row) for row in history]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/status')
def status():
    """Return browser preload status"""
    return jsonify(_preload_status)

@app.route('/search-status')
def search_status():
    """Return active search status"""
    return jsonify(_search_status)

@app.route('/search', methods=['POST'])
def search():
    global _search_status
    item = request.json.get('item', '')
    
    if not item:
        return jsonify({'error': 'Please enter an item to search'}), 400
    
    # Reset search status
    _search_status = {'carrefour': 'ready', 'noon': 'ready', 'talabat': 'ready'}
    
    # Search all stores in parallel for better performance
    with ThreadPoolExecutor(max_workers=3) as executor:
        carrefour_future = executor.submit(search_carrefour, item)
        noon_future = executor.submit(search_noon, item)
        talabat_future = executor.submit(search_talabat, item)
        
        raw_results = {
            'carrefour': carrefour_future.result(),
            'noon': noon_future.result(),
            'talabat': talabat_future.result()
        }
    
    # Return raw results only
    return jsonify({
        'raw_results': raw_results,
        'locations': {
            'carrefour': raw_results.get('carrefour', {}).get('location'),
            'noon': raw_results.get('noon', {}).get('location'),
        }
    })

@app.route('/match', methods=['POST'])
def match():
    """Match products from raw results"""
    data = request.json
    raw_results = data.get('raw_results', {})
    sort_by = data.get('sort_by', 'price')  # 'price' or 'quantity'
    sort_order = data.get('sort_order', 'asc')  # 'asc' or 'desc'
    
    if not raw_results:
        return jsonify({'error': 'No raw results provided'}), 400
    
    # Get OpenRouter API key from environment
    openrouter_api_key = os.getenv('OPENROUTER_API_KEY')
    product_name = data.get('product_name', '')
    
    # Match products across stores
    matched_products = match_products(raw_results, openrouter_api_key, query=product_name)
    
    # Sort products
    ascending = (sort_order == 'asc')
    sorted_products = sort_products(matched_products, sort_by=sort_by, ascending=ascending)
    
    # Save to database in background (P1 feature)
    try:
        if sorted_products:
            # Background task to avoid blocking response
            threading.Thread(
                target=save_product_and_prices, 
                args=(sorted_products,), 
                daemon=True
            ).start()
            # Don't log search here, already logged during initial search
    except Exception as e:
        print(f"[Database] Error saving to database: {str(e)}")
    
    return jsonify({
        'matched_products': sorted_products
    })

def preload_single_browser(store_name, base_url, cookies_file):
    """Preload a single browser"""
    global _preload_status
    try:
        _preload_status[store_name.lower()] = 'loading'
        get_or_create_browser(store_name, base_url, cookies_file)
        _preload_status[store_name.lower()] = 'ready'
        print(f"[Startup] {store_name} browser ready")
    except Exception as e:
        _preload_status[store_name.lower()] = 'error'
        print(f"[Startup] Error preloading {store_name}: {str(e)}")

def preload_browsers():
    """Preload browsers in parallel on startup for faster first query"""
    print("[Startup] Preloading browsers in parallel...")
    
    # Preload both browsers in parallel using ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2) as executor:
        carrefour_future = executor.submit(
            preload_single_browser, 
            'Carrefour', 
            'https://www.carrefouruae.com/mafuae/en/', 
            CARREFOUR_COOKIES_FILE
        )
        noon_future = executor.submit(
            preload_single_browser,
            'Noon',
            'https://minutes.noon.com/uae-en/',
            NOON_COOKIES_FILE
        )
        
        # Wait for both to complete
        carrefour_future.result()
        noon_future.result()
    
    print("[Startup] Browser preloading complete")

if __name__ == '__main__':
    # Start browser preloading in background thread
    # Only run once (not in reloader subprocess)
    if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        # First run - mark as not started
        pass
    else:
        # Reloader subprocess - start preloading
        threading.Thread(target=preload_browsers, daemon=True).start()
    
    app.run(debug=True, host='127.0.0.1', port=5000)
