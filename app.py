from flask import Flask, render_template, request, jsonify
import requests
from bs4 import BeautifulSoup
import time

app = Flask(__name__)

def search_carrefour(item):
    """Search Carrefour UAE for item prices"""
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
            
            return products if products else [{'name': 'No results found', 'price': 'N/A'}]
        return [{'name': 'Error fetching data', 'price': 'N/A'}]
    except Exception as e:
        return [{'name': f'Error: {str(e)}', 'price': 'N/A'}]

def search_noon(item):
    """Search Noon for item prices"""
    try:
        url = f"https://www.noon.com/uae-en/search/?q={item.replace(' ', '+')}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            products = []
            # Simplified scraper - actual structure may vary
            product_cards = soup.find_all('div', class_='productContainer', limit=5)
            
            for card in product_cards:
                try:
                    name = card.find('div', class_='sc-')
                    price = card.find('span', class_='price')
                    if name and price:
                        products.append({
                            'name': name.text.strip(),
                            'price': price.text.strip()
                        })
                except:
                    continue
            
            return products if products else [{'name': 'No results found', 'price': 'N/A'}]
        return [{'name': 'Error fetching data', 'price': 'N/A'}]
    except Exception as e:
        return [{'name': f'Error: {str(e)}', 'price': 'N/A'}]

def search_talabat(item):
    """Search Talabat for item prices"""
    try:
        # Talabat Mart search
        url = f"https://www.talabat.com/uae/mart/search?query={item.replace(' ', '+')}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            # Note: Talabat is heavily JavaScript-based, this is a placeholder
            return [{'name': 'Talabat requires JavaScript (manual search)', 'price': 'N/A'}]
        return [{'name': 'Error fetching data', 'price': 'N/A'}]
    except Exception as e:
        return [{'name': f'Error: {str(e)}', 'price': 'N/A'}]

def search_kareem(item):
    """Search Kareem (Careem) for item prices"""
    try:
        # Careem Now/Quik search
        url = f"https://www.careem.com/en-ae/grocery/search?q={item.replace(' ', '+')}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            # Note: Careem is heavily JavaScript-based, this is a placeholder
            return [{'name': 'Careem requires JavaScript (manual search)', 'price': 'N/A'}]
        return [{'name': 'Error fetching data', 'price': 'N/A'}]
    except Exception as e:
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
