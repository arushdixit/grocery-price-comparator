from flask import Flask, render_template, request, jsonify
import requests
from bs4 import BeautifulSoup
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

app = Flask(__name__)

def search_carrefour(item):
    """Search Carrefour UAE for item prices"""
    start_time = time.time()
    print(f"[Carrefour] Starting search for '{item}'...")
    try:
        url = f"https://www.carrefouruae.com/mafuae/en/search?keyword={item.replace(' ', '+')}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            # This is a simplified scraper - actual structure may vary
            products = []
            # You'll need to inspect the actual HTML structure
            product_cards = soup.find_all('div', class_='product-card', limit=5)
            
            for card in product_cards:
                try:
                    name = card.find('h3', class_='product-title')
                    price = card.find('span', class_='price')
                    if name and price:
                        products.append({
                            'name': name.text.strip(),
                            'price': price.text.strip()
                        })
                except:
                    continue
            
            elapsed = time.time() - start_time
            print(f"[Carrefour] Completed in {elapsed:.2f}s - Found {len(products)} products")
            return products if products else [{'name': 'No results found', 'price': 'N/A'}]
        elapsed = time.time() - start_time
        print(f"[Carrefour] Failed in {elapsed:.2f}s - Status code: {response.status_code}")
        return [{'name': 'Error fetching data', 'price': 'N/A'}]
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"[Carrefour] Error in {elapsed:.2f}s - {str(e)}")
        return [{'name': f'Error: {str(e)}', 'price': 'N/A'}]

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

def search_kareem(item):
    """Search Kareem (Careem) for item prices"""
    start_time = time.time()
    print(f"[Kareem] Starting search for '{item}'...")
    try:
        # Careem Now/Quik search
        url = f"https://www.careem.com/en-ae/grocery/search?q={item.replace(' ', '+')}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            # Note: Careem is heavily JavaScript-based, this is a placeholder
            elapsed = time.time() - start_time
            print(f"[Kareem] Completed in {elapsed:.2f}s - Placeholder response")
            return [{'name': 'Careem requires JavaScript (manual search)', 'price': 'N/A'}]
        elapsed = time.time() - start_time
        print(f"[Kareem] Failed in {elapsed:.2f}s")
        return [{'name': 'Error fetching data', 'price': 'N/A'}]
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"[Kareem] Error in {elapsed:.2f}s - {str(e)}")
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
        'talabat': search_talabat(item),
        'kareem': search_kareem(item)
    }
    
    return jsonify(results)

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5000)
