from flask import Flask, render_template, request, jsonify
import requests
from bs4 import BeautifulSoup
import time
import os
import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

app = Flask(__name__)

# Cookies files
NOON_COOKIES_FILE = 'Cookies/noon_minutes.json'
CARREFOUR_COOKIES_FILE = 'Cookies/carrefour.json'

def search_carrefour(item):
    """Search Carrefour UAE for item prices using Selenium"""
    start_time = time.time()
    print(f"[Carrefour] Starting search for '{item}'...")
    driver = None
    try:
        # Setup Chrome options
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        # Initialize driver
        driver = webdriver.Chrome(options=chrome_options)
        
        # Navigate to Carrefour first (required to set cookies)
        driver.get("https://www.carrefouruae.com/mafuae/en/")
        
        # Add cookies if provided
        try:
            if os.path.exists(CARREFOUR_COOKIES_FILE):
                with open(CARREFOUR_COOKIES_FILE, 'r') as f:
                    cookies = json.load(f)
                    cookie_count = 0
                    for cookie in cookies:
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
                    print(f"[Carrefour] Added {cookie_count} cookies")
                    driver.refresh()
            else:
                print(f"[Carrefour] No cookies file found")
        except Exception as e:
            print(f"[Carrefour] Error loading cookies: {str(e)}")
        
        # Detect location on homepage
        time.sleep(2)
        try:
            location_elem = driver.find_element(By.CSS_SELECTOR, "div.max-w-\[250px\].truncate, div.max-w-\[220px\].truncate")
            location_text = location_elem.text.strip()
            if location_text:
                print(f"[Carrefour] Detected location: {location_text}")
            else:
                print("[Carrefour] ⚠️  Could not detect location")
        except:
            print("[Carrefour] ⚠️  Could not detect location - results may be for default area")
        
        # Navigate to search URL
        url = f"https://www.carrefouruae.com/mafuae/en/search?keyword={item.replace(' ', '%20')}"
        driver.get(url)
        
        # Wait for products to load
        wait = WebDriverWait(driver, 15)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div[class*='max-w-']")))
        time.sleep(2)
        
        # Parse with BeautifulSoup
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        products = []
        
        # Find product containers
        product_containers = soup.find_all('div', class_=lambda x: x and 'max-w-' in str(x) and 'sm:max-w-' in str(x))
        
        for container in product_containers[:10]:
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
        return products if products else [{'name': 'No results found', 'price': 'N/A'}]
        
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"[Carrefour] Error in {elapsed:.2f}s - {str(e)}")
        return [{'name': f'Error: {str(e)}', 'price': 'N/A'}]
    finally:
        if driver:
            driver.quit()

def search_noon(item):
    """Search Noon for item prices using Selenium"""
    start_time = time.time()
    print(f"[Noon] Starting search for '{item}'...")
    driver = None
    try:
        # Setup Chrome options
        chrome_options = Options()
        chrome_options.add_argument('--headless')  # Run in background
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        # Initialize driver
        driver = webdriver.Chrome(options=chrome_options)
        
        # Navigate to Noon first (required to set cookies)
        driver.get("https://minutes.noon.com/uae-en/")
        
        # Add cookies if provided
        try:
            if os.path.exists(NOON_COOKIES_FILE):
                with open(NOON_COOKIES_FILE, 'r') as f:
                    cookies = json.load(f)
                    cookie_count = 0
                    for cookie in cookies:
                        # Selenium requires specific cookie format
                        selenium_cookie = {
                            'name': cookie['name'],
                            'value': cookie['value'],
                            'domain': cookie['domain'],
                            'path': cookie.get('path', '/'),
                            'secure': cookie.get('secure', False)
                        }
                        # Add expiry if present
                        if 'expirationDate' in cookie:
                            selenium_cookie['expiry'] = int(cookie['expirationDate'])
                        
                        driver.add_cookie(selenium_cookie)
                        cookie_count += 1
                    print(f"[Noon] Added {cookie_count} cookies")
                    # Reload to apply cookies
                    driver.refresh()
            else:
                print(f"[Noon] No cookies file found at {NOON_COOKIES_FILE}")
        except Exception as e:
            print(f"[Noon] Error loading cookies: {str(e)}")
        
        # Wait for homepage to load and detect location
        time.sleep(2)
        try:
            location_elem = driver.find_element(By.CSS_SELECTOR, "span.AddressHeader_addressText__kMyss")
            location_text = location_elem.text.strip()
            print(f"[Noon] Detected location: {location_text}")
        except:
            print("[Noon] ⚠️  Could not detect location - results may be for default area")
        
        # Navigate to search URL
        url = f"https://minutes.noon.com/uae-en/search/?q={item.replace(' ', '%20')}"
        driver.get(url)
        
        # Wait for products to load (wait for product boxes)
        wait = WebDriverWait(driver, 15)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div[class*='ProductBox_detailsSection']")))
        
        # Additional wait for dynamic content
        time.sleep(2)
        
        # Parse with BeautifulSoup
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        products = []
        
        # Find product boxes
        product_boxes = soup.find_all('div', class_=lambda x: x and 'ProductBox_detailsSection' in x)
        
        for product in product_boxes[:10]:  # Limit to 10 results
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
        return products if products else [{'name': 'No results found', 'price': 'N/A'}]
        
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"[Noon] Error in {elapsed:.2f}s - {str(e)}")
        return [{'name': f'Error: {str(e)}', 'price': 'N/A'}]
    finally:
        if driver:
            driver.quit()

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
            return [{'name': 'Talabat requires JavaScript (manual search)', 'price': 'N/A'}]
        elapsed = time.time() - start_time
        print(f"[Talabat] Failed in {elapsed:.2f}s")
        return [{'name': 'Error fetching data', 'price': 'N/A'}]
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"[Talabat] Error in {elapsed:.2f}s - {str(e)}")
        return [{'name': f'Error: {str(e)}', 'price': 'N/A'}]


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    item = request.json.get('item', '')
    
    if not item:
        return jsonify({'error': 'Please enter an item to search'}), 400
    
    # Search all stores
    results = {
        'carrefour': search_carrefour(item),
        'noon': search_noon(item),
        'talabat': search_talabat(item)
    }
    
    return jsonify(results)

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)
