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
from urllib.parse import urlparse
from dotenv import load_dotenv

# Import our custom modules
from utils import match_products, sort_products, parse_price
from database import (
    save_search_results, get_price_history, get_all_tracked_products, 
    get_price_comparison, get_product_by_name, get_db_stats,
    get_price_trends
)

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Cookies files
NOON_COOKIES_FILE = 'Cookies/noon_minutes.json'
CARREFOUR_COOKIES_FILE = 'Cookies/carrefour.json'
AMAZON_COOKIES_FILE = 'Cookies/amazon_now.json'

# Persistent browser pool
_browser_pool = {
    'carrefour': None,
    'noon': None,
    'amazon': None
}

# Browser preload status
_preload_status = {
    'carrefour': 'not_started',  # not_started, loading, ready, error
    'noon': 'not_started',
    'amazon': 'not_started',
    'talabat': 'ready',  # Talabat doesn't use Selenium
    'lulu': 'ready'  # Lulu uses Talabat API
}

# Active search status
_search_status = {
    'carrefour': 'ready',  # ready, searching, complete
    'noon': 'ready',
    'amazon': 'ready',
    'talabat': 'ready',
    'lulu': 'ready'
}

# Detected locations cache
_browser_locations = {
    'carrefour': None,
    'noon': None,
    'amazon': None
}

def get_chrome_driver():
    """Create a new Chrome driver with standard options"""
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-blink-features=AutomationControlled')
    chrome_options.add_argument('user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    # OPTIMIZATION: Eager loading strategy (don't wait for all resources)
    chrome_options.page_load_strategy = 'eager'
    
    # OPTIMIZATION: Disable images to save bandwidth
    prefs = {"profile.managed_default_content_settings.images": 2}
    chrome_options.add_experimental_option("prefs", prefs)
    
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
    
    # OPTIMIZATION: Visit a lightweight page to set cookies before loading the heavy app
    # This avoids loading the main application twice (once to set domain, once to apply cookies)
    if cookies_file and os.path.exists(cookies_file):
        try:
            # Visit robots.txt to establish domain context quickly
            parsed = urlparse(base_url)
            domain_root = f"{parsed.scheme}://{parsed.netloc}"
            driver.get(f"{domain_root}/robots.txt")
            
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
                        driver.add_cookie(selenium_cookie)
                        cookie_count += 1
                    except:
                        continue
                print(f"[{store_name}] Added {cookie_count} cookies")
        except Exception as e:
            print(f"[{store_name}] Error loading cookies: {str(e)}")
            
    # Navigate to the actual application (now with cookies applied)
    driver.get(base_url)
    
    _browser_pool[store_name] = driver
    return driver, True  # True = newly created

def detect_location(driver, store_name):
    """Detect delivery location from the page header"""
    try:
        wait = WebDriverWait(driver, 5)
        if store_name.lower() == 'carrefour':
            location_elem = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "div.max-w-\\[250px\\].truncate, div.max-w-\\[220px\\].truncate")))
            return location_elem.text.strip()
        elif store_name.lower() == 'noon':
            # Wait for ETA element to load, which confirms location-specific data is ready
            # Selector targets the paragraph containing "minutes delivery"
            wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "p[class*='estimate']")))
            location_elem = wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "span[class*='addressText']")))
            return location_elem.text.strip()
        elif store_name.lower() == 'amazon':
            # Amazon location
            location_elem = wait.until(EC.visibility_of_element_located((By.ID, "glow-ingress-line2")))
            return location_elem.text.strip()
    except Exception as e:
        print(f"[{store_name}] ⚠️  Could not detect location: {str(e)}")
    return None

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
        
        # Use cached location or detect if missing
        if not _browser_locations.get('carrefour'):
            _browser_locations['carrefour'] = detect_location(driver, 'Carrefour')
        
        location = _browser_locations.get('carrefour')
        if location:
            print(f"[Carrefour] Using location: {location}")
        else:
            print("[Carrefour] ⚠️  Location not found - results may be for default area")
        
        # Navigate to search URL
        url = f"https://www.carrefouruae.com/mafuae/en/search?keyword={item.replace(' ', '%20')}"
        driver.get(url)
        
        # Wait for products to load
        wait = WebDriverWait(driver, 5) # Optimization: Fail fast (5s is enough for eager load)
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div[class*='max-w-']")))
            print("[Carrefour] Product elements detected")
        except Exception as e:
            print(f"[Carrefour] Timeout waiting for products: {str(e)}")
        
        # Parse with BeautifulSoup
        soup = BeautifulSoup(driver.page_source, 'lxml')
        products = []
        
        # Find product containers - using robust parent selector
        product_containers = soup.find_all('div', class_=lambda x: x and 'mb-lg' in str(x) and 'flex' in str(x) and 'w-full' in str(x))
        
        for container in product_containers[:40]: 
            try:
                # 1. Extract Name
                name_div = container.find('div', class_=lambda x: x and 'line-clamp-2' in str(x))
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
                                # Check for lazy loading attributes first
                                image_url = img_elem.get('src')
                                if not image_url or 'data:image' in image_url:
                                    image_url = img_elem.get('data-src') or img_elem.get('data-srcset') or img_elem.get('srcset')
                                    # If charset, take first URL
                                    if image_url and ' ' in image_url:
                                        image_url = image_url.split(' ')[0]
                        except Exception as e:
                            print(f"[Carrefour] Error extracting image: {str(e)}")

                        # Extract Product URL
                        product_url = None
                        link = name_div.find_parent('a')
                        if link and link.get('href'):
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
        print("[Noon] Getting browser...")
        driver, is_new = get_or_create_browser('Noon', 'https://minutes.noon.com/uae-en/', NOON_COOKIES_FILE)
        print(f"[Noon] Browser ready (new={is_new})")
        
        # Use cached location or detect if missing
        if not _browser_locations.get('noon'):
            _browser_locations['noon'] = detect_location(driver, 'Noon')
            
        location = _browser_locations.get('noon')
        if location:
            print(f"[Noon] Using location: {location}")
        else:
            print("[Noon] ⚠️  Location not found - results may be for default area")
        
        # Navigate to search URL
        url = f"https://minutes.noon.com/uae-en/search/?q={item.replace(' ', '%20')}"
        print(f"[Noon] Navigating to {url}")
        driver.get(url)
        
        # Wait for products to load (wait for product boxes)
        # Wait for products to load (wait for product boxes)
        print("[Noon] Waiting for product elements...")
        wait = WebDriverWait(driver, 5) # Optimization: Fail fast (5s is enough for eager load)
        try:
            # Wait for EITHER products OR "no results" image
            # This returns True as soon as one is found
            wait.until(lambda d: 
                d.find_elements(By.CSS_SELECTOR, "a[class*='ProductBox']") or 
                d.find_elements(By.CSS_SELECTOR, "img[src*='no_res_wid']")
            )
            
            # Check if it was the "no results" image that triggered it
            if driver.find_elements(By.CSS_SELECTOR, "img[src*='no_res_wid']"):
                print("[Noon] 'No results' banner detected - returning early")
                _search_status['noon'] = 'complete'
                return {'products': [{'name': 'No results found', 'price': 'N/A'}]}

            print("[Noon] Product elements detected")
        except Exception as e:
            print(f"[Noon] Timeout waiting for products: {str(e)}")

                
        # Parse with BeautifulSoup
        soup = BeautifulSoup(driver.page_source, 'lxml')
        products = []
        
        # Find single product items directly
        # We search for 'ProductBox' generally to be robust against hash changes
        product_boxes = soup.find_all('a', class_=lambda x: x and 'ProductBox' in str(x))
        print(f"[Noon] Found {len(product_boxes)} product boxes in DOM")
        
        for product in product_boxes[:20]:
            try:
                # 1. Product URL (The element itself is the anchor)
                product_url = None
                href = product.get('href')
                if href:
                     product_url = f"https://minutes.noon.com{href}" if href.startswith('/') else href

                # 2. Image
                image_url = None
                # HTML: <div class="ProductBox-module-scss-module__urFZAa__imageSection"><img ...>
                img_section = product.find('div', class_=lambda x: x and 'imageSection' in str(x))
                if img_section:
                    img_elem = img_section.find('img')
                    if img_elem:
                        image_url = img_elem.get('src')
                
                # 3. Details (Name, Price, Size)
                # HTML: <div class="ProductBox-module-scss-module__urFZAa__detailsSection">...
                details = product.find('div', class_=lambda x: x and 'detailsSection' in str(x))
                if not details:
                    continue

                name_elem = product.find('h2', class_=lambda x: x and 'title' in str(x))

                # Price is usually in a container like priceCtr
                price_elem = product.find('strong', class_=lambda x: x and 'productPrice' in str(x))
                
                size_elem = product.find('span', class_=lambda x: x and 'sizeInfo' in str(x))
                
                if name_elem and price_elem:
                    name = name_elem.text.strip()
                    
                    if size_elem:
                        name += f" - {size_elem.text.strip()}"
                    
                    # Clean price text (remove currency if present to avoid dupes)
                    price_text = price_elem.text.strip().replace('AED', '').strip()
                    
                    products.append({
                        'name': name,
                        'price': f"AED {price_text}",
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
        import traceback
        traceback.print_exc()
        _search_status['noon'] = 'complete'
        return {'products': [{'name': f'Error: {str(e)}', 'price': 'N/A'}]}

def search_amazon(item):
    """Search Amazon.ae (Fresh/Yalla) for item prices using Selenium"""
    global _search_status
    _search_status['amazon'] = 'searching'
    start_time = time.time()
    print(f"[Amazon] Starting search for '{item}'...")
    location = None
    try:
        # Get or create persistent browser
        print("[Amazon] Getting browser...")
        # Amazon grocery homepage
        driver, is_new = get_or_create_browser('Amazon', 'https://www.amazon.ae/fmc/storefront?almBrandId=sAuWWBROaG', AMAZON_COOKIES_FILE)
        print(f"[Amazon] Browser ready (new={is_new})")
        
        # Use cached location or detect if missing
        if not _browser_locations.get('amazon'):
            _browser_locations['amazon'] = detect_location(driver, 'Amazon')
            
        location = _browser_locations.get('amazon')
        if location:
            print(f"[Amazon] Using location: {location}")
        else:
            print("[Amazon] ⚠️  Location not found - results may be for default area")
        
        # Navigate to search URL
        # Construct search URL for Amazon Fresh/Yalla
        # i=amazonyalla ensures we search within the grocery section
        encoded_item = item.replace(' ', '+')
        url = f"https://www.amazon.ae/s?k={encoded_item}&i=amazonyalla&ref=nb_sb_noss"
        print(f"[Amazon] Navigating to {url}")
        driver.get(url)
        
        # Wait for products to load
        print("[Amazon] Waiting for product elements...")
        wait = WebDriverWait(driver, 5)
        try:
            # Wait for any result item or no results indicator
            wait.until(lambda d: 
                d.find_elements(By.CSS_SELECTOR, "div.desktop-grid-content-view") or 
                d.find_elements(By.XPATH, "//*[contains(text(), 'No results for')]")
            )
            
            if driver.find_elements(By.XPATH, "//*[contains(text(), 'No results for')]"):
                 print("[Amazon] 'No results' detected - returning early")
                 _search_status['amazon'] = 'complete'
                 return {'products': [{'name': 'No results found', 'price': 'N/A'}]}
                 
            print("[Amazon] Product elements detected")
        except Exception as e:
            print(f"[Amazon] Timeout waiting for products: {str(e)}")

        # Parse with BeautifulSoup
        soup = BeautifulSoup(driver.page_source, 'lxml')
        products = []
        
        # Find product containers
        # User specified: <div class="a-section a-spacing-base desktop-grid-content-view">
        product_containers = soup.find_all('div', class_=lambda x: x and 'desktop-grid-content-view' in str(x))
        print(f"[Amazon] Found {len(product_containers)} product containers in DOM")
        
        for container in product_containers[:40]:
            try:
                # 1. Product Title
                # <h2 ... class="... a-text-normal"><span>TITLE</span></h2>
                title_elem = container.find('h2', class_=lambda x: x and 'a-text-normal' in str(x))
                if not title_elem:
                    continue
                
                name = title_elem.get_text().strip()
                
                # 2. Price
                # <span class="a-price"><span class="a-offscreen">AED 9.03</span>...</span>
                price_elem = container.find('span', class_='a-price')
                price_text = "N/A"
                if price_elem:
                    offscreen = price_elem.find('span', class_='a-offscreen')
                    if offscreen:
                        price_text = offscreen.get_text().strip()
                    else:
                        price_text = price_elem.get_text().strip()
                
                # Skip if no price
                if not price_text or price_text == 'N/A':
                    continue

                # 3. Image
                # <img class="s-image" src="...">
                image_url = None
                img_elem = container.find('img', class_='s-image')
                if img_elem:
                    image_url = img_elem.get('src')
                    
                # 4. Product URL
                # <a ... href="...">
                product_url = None
                link_elem = container.find('a', class_=lambda x: x and 'a-link-normal' in str(x))
                if link_elem:
                    href = link_elem.get('href')
                    if href:
                        if href.startswith('/'):
                            product_url = f"https://www.amazon.ae{href}"
                        else:
                            product_url = href
                            
                products.append({
                    'name': name,
                    'price': price_text,
                    'image_url': image_url,
                    'product_url': product_url
                })
                
            except Exception as e:
                # print(f"[Amazon] Parsing error for one item: {str(e)}")
                continue
                
        elapsed = time.time() - start_time
        print(f"[Amazon] Completed in {elapsed:.2f}s - Found {len(products)} products")
        
        _search_status['amazon'] = 'complete'
        result = {'products': products if products else [{'name': 'No results found', 'price': 'N/A'}]}
        if location:
            result['location'] = location
        return result

    except Exception as e:
        elapsed = time.time() - start_time
        print(f"[Amazon] Error in {elapsed:.2f}s - {str(e)}")
        _search_status['amazon'] = 'complete'
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

def search_lulu(item):
    """Search Lulu Hypermarket for item prices via Talabat API"""
    global _search_status
    _search_status['lulu'] = 'searching'
    start_time = time.time()
    print(f"[Lulu] Starting search for '{item}'...")
    try:
        # Lulu Hypermarket API endpoint (via Talabat)
        # Store ID: 31fbcd29-f112-47c4-814a-d13ed0ac8233
        url = f"https://www.talabat.com/nextApi/groceries/stores/31fbcd29-f112-47c4-814a-d13ed0ac8233/products"
        params = {
            'countryId': '4',  # UAE
            'query': item,
            'limit': '20',
            'offset': '0',
            'isDarkstore': 'false',
            'isMigrated': 'true',
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
                        # Pattern: https://www.talabat.com/uae/grocery/701679/lulu-hypermarket/product/<slug>/s/<sku>?aid=1308
                        slug = product.get('slug')
                        sku = product.get('sku')
                        
                        product_url = None
                        if slug and sku:
                             product_url = f"https://www.talabat.com/uae/grocery/701679/lulu-hypermarket/product/{slug}/s/{sku}?aid=1308"
                        
                        products.append({
                            'name': title,
                            'price': f"AED {price}",
                            'image_url': image_url,
                            'product_url': product_url
                        })
                except:
                    continue
            
            elapsed = time.time() - start_time
            print(f"[Lulu] Completed in {elapsed:.2f}s - Found {len(products)} products")
            _search_status['lulu'] = 'complete'
            return {'products': products if products else [{'name': 'No results found', 'price': 'N/A'}]}
        else:
            elapsed = time.time() - start_time
            print(f"[Lulu] Failed in {elapsed:.2f}s with status code {response.status_code}")
            _search_status['lulu'] = 'complete'
            return {'products': [{'name': 'Error fetching data', 'price': 'N/A'}]}
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"[Lulu] Error in {elapsed:.2f}s - {str(e)}")
        _search_status['lulu'] = 'complete'
        return {'products': [{'name': f'Error: {str(e)}', 'price': 'N/A'}]}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/analytics')
def analytics():
    """Analytics dashboard page"""
    return render_template('analytics.html')

@app.route('/api/analytics/stats')
def analytics_stats():
    """Get overall database statistics"""
    try:
        stats = get_db_stats()
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics/products')
def analytics_products():
    """Get all tracked products with latest prices"""
    limit = request.args.get('limit', type=int)  # Defaults to None if not provided
    try:
        products = get_all_tracked_products(limit=limit)
        return jsonify({'products': products})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics/price-history/<int:product_id>')
def analytics_price_history(product_id):
    """Get price history for a specific product"""
    days = request.args.get('days', 30, type=int)
    try:
        history = get_price_history(product_id, days=days)
        return jsonify({'history': history})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics/price-history-by-name')
def analytics_price_history_by_name():
    """Get price history for a product by its matched name"""
    matched_name = request.args.get('name', '')
    days = request.args.get('days', 30, type=int)
    try:
        product = get_product_by_name(matched_name)
        if not product:
            return jsonify({'history': [], 'product': None})
        history = get_price_history(product['id'], days=days)
        return jsonify({'history': history, 'product': product})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/analytics/comparison/<int:product_id>')
def analytics_comparison(product_id):
    """Get current price comparison across stores for a product"""
    try:
        comparison = get_price_comparison(product_id)
        return jsonify(comparison)
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
    _search_status = {'carrefour': 'ready', 'noon': 'ready', 'amazon': 'ready', 'talabat': 'ready', 'lulu': 'ready'}
    
    # Search all stores in parallel for better performance
    with ThreadPoolExecutor(max_workers=5) as executor:
        carrefour_future = executor.submit(search_carrefour, item)
        noon_future = executor.submit(search_noon, item)
        amazon_future = executor.submit(search_amazon, item)
        talabat_future = executor.submit(search_talabat, item)
        lulu_future = executor.submit(search_lulu, item)
        
        raw_results = {
            'carrefour': carrefour_future.result(),
            'noon': noon_future.result(),
            'amazon': amazon_future.result(),
            'talabat': talabat_future.result(),
            'lulu': lulu_future.result()
        }
    
    # Return raw results only
    return jsonify({
        'raw_results': raw_results,
        'locations': {
            'carrefour': raw_results.get('carrefour', {}).get('location'),
            'noon': raw_results.get('noon', {}).get('location'),
            'amazon': raw_results.get('amazon', {}).get('location'),
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
    
    # Save to database in background (CDC Type 2 price tracking)
    # We save first, then enrich if possible, though background saving means
    # trends might only show on second search for new products.
    try:
        if sorted_products:
            save_search_results(sorted_products) # Save synchronously for trend availability
            
            # Enrich with trends and IDs for Frontend
            from utils import classify_text
            for p in sorted_products:
                p_db = get_product_by_name(p.get('matched_name'))
                if p_db:
                    p['trends'] = get_price_trends(p_db['id'])
                    p['product_id'] = p_db['id']
                    p['category'] = classify_text(p.get('matched_name'))
    except Exception as e:
        print(f"[Database] Error saving/enriching products: {str(e)}")
    
    return jsonify({
        'matched_products': sorted_products
    })

def preload_single_browser(store_name, base_url, cookies_file):
    """Preload a single browser"""
    global _preload_status
    try:
        _preload_status[store_name.lower()] = 'loading'
        driver, _ = get_or_create_browser(store_name, base_url, cookies_file)
        
        # Detect and cache location
        location = detect_location(driver, store_name)
        if location:
            _browser_locations[store_name.lower()] = location
            print(f"[{store_name}] Pre-detected location: {location}")
            
        _preload_status[store_name.lower()] = 'ready'
        print(f"[Startup] {store_name} browser ready")
    except Exception as e:
        _preload_status[store_name.lower()] = 'error'
        print(f"[Startup] Error preloading {store_name}: {str(e)}")

def preload_browsers():
    """Preload browsers in parallel on startup for faster first query"""
    print("[Startup] Preloading browsers in parallel...")
    
    # Preload both browsers in parallel using ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=3) as executor:
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
        amazon_future = executor.submit(
            preload_single_browser,
            'Amazon',
            'https://www.amazon.ae/fmc/storefront?almBrandId=sAuWWBROaG',
            AMAZON_COOKIES_FILE
        )
        
        # Wait for both to complete
        carrefour_future.result()
        noon_future.result()
        amazon_future.result()
    
    print("[Startup] Browser preloading complete")

if __name__ == '__main__':
    # Start background scheduler for price refreshes
    def run_scheduled_scraping():
        """Background thread to refresh prices for tracked products."""
        # Wait for system to settle
        time.sleep(60)
        while True:
            # Refresh every 12 hours
            time.sleep(12 * 3600)
            try:
                print("[Scheduler] Starting scheduled refresh...")
                # Logic would go here to trigger background searches
                # For now, we just log it as a placeholder for the flow
            except Exception as e:
                print(f"[Scheduler] Error: {e}")

    if os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        # Start preloading
        threading.Thread(target=preload_browsers, daemon=True).start()
        # Start scraper
        threading.Thread(target=run_scheduled_scraping, daemon=True).start()
    
    app.run(debug=True, host='0.0.0.0', port=9000)
