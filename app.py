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
        product_containers = soup.find_all('div', class_=lambda x: x and 'max-w-' in str(x) and 'sm:max-w-' in str(x))
        
        for container in product_containers[:20]:
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
                        
                        products.append({
                            'name': name,
                            'price': price_text
                        })
            except Exception:
                continue
        
        elapsed = time.time() - start_time
        print(f"[Carrefour] Completed in {elapsed:.2f}s - Found {len(products)} products")
        result = {'products': products if products else [{'name': 'No results found', 'price': 'N/A'}]}
        if location:
            result['location'] = location
        return result
        
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"[Carrefour] Error in {elapsed:.2f}s - {str(e)}")
        return {'products': [{'name': f'Error: {str(e)}', 'price': 'N/A'}]}

def search_noon(item):
    """Search Noon for item prices using Selenium"""
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
        
        # Find product boxes
        product_boxes = soup.find_all('div', class_=lambda x: x and 'ProductBox_detailsSection' in x)
        
        for product in product_boxes[:20]:  # Limit to 20 results
            try:
                name_elem = product.find('h2', class_=lambda x: x and 'ProductBox_title' in x)
                price_elem = product.find('strong', class_=lambda x: x and 'Price_productPrice' in x)
                size_elem = product.find('span', class_=lambda x: x and 'ProductBox_sizeInfo' in x)
                origin_elem = product.find('span', class_=lambda x: x and 'TaggedAttributes_attribute' in x)
                
                if name_elem and price_elem:
                    name = name_elem.text.strip()
                    
                    # Add size info if available
                    if size_elem:
                        name += f" - {size_elem.text.strip()}"
                    
                    # Add origin info if available
                    if origin_elem:
                        origin = origin_elem.text.strip()
                        name += f" ({origin})"
                    
                    products.append({
                        'name': name,
                        'price': f"AED {price_elem.text.strip()}"
                    })
            except:
                continue
        
        elapsed = time.time() - start_time
        print(f"[Noon] Completed in {elapsed:.2f}s - Found {len(products)} products")
        result = {'products': products if products else [{'name': 'No results found', 'price': 'N/A'}]}
        if location:
            result['location'] = location
        return result
        
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"[Noon] Error in {elapsed:.2f}s - {str(e)}")
        return {'products': [{'name': f'Error: {str(e)}', 'price': 'N/A'}]}

def search_talabat(item):
    """Search Talabat for item prices"""
    start_time = time.time()
    print(f"[Talabat] Starting search for '{item}'...")
    try:
        # Talabat Mart search
        url = f"https://www.talabat.com/uae/mart/search?query={item.replace(' ', '+')}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            # Note: Talabat is heavily JavaScript-based, this is a placeholder
            elapsed = time.time() - start_time
            print(f"[Talabat] Completed in {elapsed:.2f}s - Placeholder response")
            return {'products': [{'name': 'Talabat requires JavaScript (manual search)', 'price': 'N/A'}]}
        else:
            elapsed = time.time() - start_time
            print(f"[Talabat] Failed in {elapsed:.2f}s with status code {response.status_code}")
            return {'products': [{'name': 'Error fetching data', 'price': 'N/A'}]}
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"[Talabat] Error in {elapsed:.2f}s - {str(e)}")
        return {'products': [{'name': f'Error: {str(e)}', 'price': 'N/A'}]}


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/status')
def status():
    """Return browser preload status"""
    return jsonify(_preload_status)

@app.route('/search', methods=['POST'])
def search():
    item = request.json.get('item', '')
    
    if not item:
        return jsonify({'error': 'Please enter an item to search'}), 400
    
    # Search all stores in parallel for better performance
    with ThreadPoolExecutor(max_workers=3) as executor:
        carrefour_future = executor.submit(search_carrefour, item)
        noon_future = executor.submit(search_noon, item)
        talabat_future = executor.submit(search_talabat, item)
        
        results = {
            'carrefour': carrefour_future.result(),
            'noon': noon_future.result(),
            'talabat': talabat_future.result()
        }
    
    return jsonify(results)

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
