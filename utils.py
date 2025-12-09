"""Utility functions for product matching, parsing, and sorting"""
import re
import os
import requests
import json
import difflib
from typing import List, Dict, Optional, Tuple

def parse_price(price_str: str) -> Optional[float]:
    """
    Extract numeric price value from price string
    
    Args:
        price_str: Price string like "AED 12.50" or "12.50 AED"
    
    Returns:
        Float price value or None if parsing fails
    """
    if not price_str or price_str == 'N/A':
        return None
    
    try:
        # Remove currency symbols and extract numbers
        # Matches patterns like: "12.50", "AED 12.50", "12,50"
        match = re.search(r'(\d+[.,]\d+|\d+)', str(price_str).replace(',', '.'))
        if match:
            return float(match.group(1))
    except (ValueError, AttributeError):
        pass
    
    return None

def extract_quantity(product_name: str) -> Tuple[Optional[float], Optional[str]]:
    """
    Extract quantity value and unit from product name
    
    Args:
        product_name: Product name containing quantity info
    
    Returns:
        Tuple of (quantity_value, quantity_unit) or (None, None)
    """
    if not product_name:
        return None, None
    
    # Pattern matches: 1kg, 500g, 1.5L, 250ml, 1 kg, 500 g, etc.
    patterns = [
        r'(\d+\.?\d*)\s*(kg|g|l|ml|ltr|litre|liter|gram|grams|kilogram|kilograms)',
        r'(\d+\.?\d*)\s*x\s*(\d+\.?\d*)\s*(kg|g|l|ml|ltr)',  # 2 x 500g
        r'(\d+)\s*pack\s*x\s*(\d+\.?\d*)\s*(kg|g|l|ml)',      # 2 pack x 500g
    ]
    
    for pattern in patterns:
        match = re.search(pattern, product_name.lower())
        if match:
            groups = match.groups()
            if len(groups) >= 2:
                try:
                    value = float(groups[0])
                    unit = groups[-1].lower()
                    
                    # Normalize unit
                    if unit in ['kg', 'kilogram', 'kilograms']:
                        return value, 'kg'
                    elif unit in ['g', 'gram', 'grams']:
                        return value, 'g'
                    elif unit in ['l', 'ltr', 'litre', 'liter']:
                        return value, 'l'
                    elif unit in ['ml']:
                        return value, 'ml'
                    
                    return value, unit
                except (ValueError, IndexError):
                    continue
    
    return None, None

def normalize_quantity(value: float, unit: str) -> float:
    """
    Normalize quantity to base unit (g for weight, ml for volume)
    
    Args:
        value: Quantity value
        unit: Quantity unit (kg, g, l, ml)
    
    Returns:
        Normalized value in base unit
    """
    if not value or not unit:
        return 0
    
    unit = unit.lower()
    
    # Weight normalization to grams
    if unit == 'kg':
        return value * 1000
    elif unit == 'g':
        return value
    
    # Volume normalization to milliliters
    elif unit in ['l', 'ltr', 'litre', 'liter']:
        return value * 1000
    elif unit == 'ml':
        return value
    
    return value

def parse_products_with_ai(products: List[Dict], store_name: str, openrouter_api_key: str) -> List[Dict]:
    """
    Step 1: Parse individual products to extract structured data
    
    Args:
        products: List of products from a single store
        store_name: Name of the store
        openrouter_api_key: OpenRouter API key
    
    Returns:
        List of parsed products with extracted brand, name, quantity
    """
    if not products or not openrouter_api_key:
        return []
    
    try:
        # Limit to first 20 products to avoid token limits
        products_subset = products[:20]
        
        prompt = f"""Extract structured information from these grocery product names.

        For each product, identify:
        1. Brand name (e.g., "Bayara", "Nestle", "Almarai")
        2. Product name (e.g., "Moong Dal", "Milk", "Basmati Rice")
        3. Quantity value and unit (e.g., 1, "kg" or 500, "ml")

        Products from {store_name}:
        {json.dumps([p['name'] for p in products_subset], ensure_ascii=False)}

        Return JSON only (no other text):
        {{
        "parsed": [
            {{
            "original_name": "exact name from input",
            "brand": "Brand Name" or null,
            "product_name": "Product Name",
            "quantity_value": 1.0 or null,
            "quantity_unit": "kg" or null
            }}
        ]
        }}"""

        model = os.getenv('OPENROUTER_MODEL', 'meta-llama/llama-3.1-8b-instruct:free')
        
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {openrouter_api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            content = result['choices'][0]['message']['content']
            
            json_match = re.search(r'```(?:json)?\s*(.*?)\s*```', content, re.DOTALL)
            if json_match:
                content = json_match.group(1)
            
            parsed_data = json.loads(content)
            parsed_list = parsed_data.get('parsed', [])
            
            # Match back with original products to preserve price
            result_products = []
            for i, parsed in enumerate(parsed_list):
                if i < len(products_subset):
                    result_products.append({
                        'original_name': parsed.get('original_name', products_subset[i]['name']),
                        'brand': parsed.get('brand'),
                        'product_name': parsed.get('product_name'),
                        'quantity_value': parsed.get('quantity_value'),
                        'quantity_unit': parsed.get('quantity_unit'),
                        'price': products_subset[i].get('price'),
                        'store': store_name
                    })
            
            print(f"[AI Parse] {store_name} Parsed {len(result_products)} products")
            return result_products
        else:
            print(f"[AI Parse] {store_name} API error: {response.status_code}")
            return []
            
    except Exception as e:
        print(f"[AI Parse] {store_name} Error: {str(e)}")
        return []


def group_parsed_products(parsed_products: List[Dict]) -> List[Dict]:
    """
    Step 2: Group parsed products by matching brand + quantity + name similarity
    
    Args:
        parsed_products: List of parsed products from all stores
    
    Returns:
        List of matched product groups
    """
    if not parsed_products:
        return []
    
    # 1. Bucket by Brand + Quantity (Exact Match)
    buckets = {}
    for p in parsed_products:
        # Normalize brand
        brand = p.get('brand')
        if brand:
            brand = brand.strip().lower()
        else:
            brand = "unknown"
            
        # Get Quantity
        qty_val = p.get('quantity_value')
        qty_unit = p.get('quantity_unit')
        
        # Create a key tuple
        key = (brand, qty_val, qty_unit)
        
        if key not in buckets:
            buckets[key] = []
        buckets[key].append(p)
        
    matched_groups = []
    
    # 2. Cluster within buckets by Name Similarity
    for key, items in buckets.items():
        # If bucket has items from less than 2 distinct stores, skip it entirely
        # (We only want matches found in at least 2 stores)
        stores_in_bucket = {x.get('store') for x in items if x.get('store')}
        if len(stores_in_bucket) < 2:
            continue
            
        # Determine strictness based on whether brand is known
        brand_known = key[0] != "unknown"
        threshold = 0.6 if brand_known else 0.8
        
        # Simple clustering
        clusters = []
        processed_indexes = set()
        
        for i in range(len(items)):
            if i in processed_indexes:
                continue
            
            current_cluster = [items[i]]
            processed_indexes.add(i)
            
            base_name = items[i].get('original_name', '').lower()
            
            for j in range(i + 1, len(items)):
                if j in processed_indexes:
                    continue
                
                compare_name = items[j].get('original_name', '').lower()
                
                # Check similarity
                ratio = difflib.SequenceMatcher(None, base_name, compare_name).ratio()
                
                if ratio >= threshold:
                    current_cluster.append(items[j])
                    processed_indexes.add(j)
            
            clusters.append(current_cluster)
            
        # 3. Format valid clusters
        for cluster in clusters:
            stores_dict = {}
            for prod in cluster:
                store = prod.get('store')
                if store:
                    # Keep the lowest price if duplicate store in cluster
                    current_price = parse_price(prod.get('price', ''))
                    
                    if store not in stores_dict or (current_price is not None and 
                        (stores_dict[store]['price'] is None or current_price < stores_dict[store]['price'])):
                        
                        stores_dict[store] = {
                            'name': prod.get('original_name', ''),
                            'price': current_price
                        }
            
            # Final check: Must have at least 2 stores
            if len(stores_dict) >= 2:
                # Use the most common product name or the first one as the matched name
                # For simplicity, use the first product's name minus " - Store" if present
                clean_name = cluster[0].get('product_name') or cluster[0].get('original_name')
                
                matched_groups.append({
                    'matched_name': f"{key[0].title()} {clean_name} {key[1] or ''}{key[2] or ''}".strip(),
                    'brand': cluster[0].get('brand'),
                    'quantity_value': cluster[0].get('quantity_value'),
                    'quantity_unit': cluster[0].get('quantity_unit'),
                    'stores': stores_dict
                })

    return matched_groups


def match_products_with_ai(store_results: Dict[str, Dict], openrouter_api_key: str) -> List[Dict]:
    """
    Two-step AI matching: parse then group
    
    Args:
        store_results: Dict with keys 'carrefour', 'noon', 'talabat' containing product lists
        openrouter_api_key: OpenRouter API key
    
    Returns:
        List of matched products with unified structure
    """
    if not openrouter_api_key:
        print("[AI Matching] No API key provided, using fallback")
        return fallback_matching(store_results)
    
    try:
        # Parse products from each store sequentially
        print("[AI Matching] Parsing products sequentially...")
        all_parsed = []
        
        for store_name in ['carrefour', 'noon', 'talabat']:
            products = store_results.get(store_name, {}).get('products', [])
            products = [p for p in products if 'Error' not in p.get('name', '') and p.get('name') != 'No results found']
            
            if products:
                try:
                    result = parse_products_with_ai(products, store_name, openrouter_api_key)
                    if result:
                        all_parsed.extend(result)
                except Exception as e:
                    print(f"[AI Matching] Parse error for {store_name}: {str(e)}")
        
        if not all_parsed:
            print("[AI Matching] No products parsed, using fallback")
            return fallback_matching(store_results)
        
        print(f"[AI Matching] Parsed {len(all_parsed)} products")
        
        # Step 2: Group parsed products
        print("[AI Matching] Step 2: Grouping matches...")
        matched_products = group_parsed_products(all_parsed)
        
        print(f"[AI Matching] Successfully matched {len(matched_products)} product groups")
        return matched_products
            
    except Exception as e:
        print(f"[AI Matching] Error: {str(e)}")
        return fallback_matching(store_results)

def fallback_matching(store_results: Dict[str, Dict]) -> List[Dict]:
    """
    Simple fallback matching when AI is unavailable
    Groups products by extracted brand and quantity
    """
    print("[AI Matching] Using fallback matching")
    
    all_products = []
    
    # Collect all products with store info
    for store in ['carrefour', 'noon', 'talabat']:
        products = store_results.get(store, {}).get('products', [])
        for product in products:
            if 'Error' not in product.get('name', '') and product.get('name') != 'No results found':
                qty_value, qty_unit = extract_quantity(product['name'])
                price = parse_price(product.get('price', ''))
                
                all_products.append({
                    'store': store,
                    'name': product['name'],
                    'price': price,
                    'quantity_value': qty_value,
                    'quantity_unit': qty_unit,
                    'normalized_qty': normalize_quantity(qty_value, qty_unit) if qty_value and qty_unit else 0
                })
    
    # Group by similar characteristics
    matched = []
    processed = set()
    
    for i, prod in enumerate(all_products):
        if i in processed:
            continue
        
        group = {
            'matched_name': prod['name'],
            'brand': None,
            'quantity_value': prod['quantity_value'],
            'quantity_unit': prod['quantity_unit'],
            'stores': {
                prod['store']: {'name': prod['name'], 'price': prod['price']}
            }
        }
        processed.add(i)
        
        # Find similar products
        for j, other in enumerate(all_products[i+1:], start=i+1):
            if j in processed:
                continue
            
            # Simple matching: same normalized quantity
            if (prod['normalized_qty'] > 0 and 
                prod['normalized_qty'] == other['normalized_qty'] and
                other['store'] not in group['stores']):
                group['stores'][other['store']] = {
                    'name': other['name'],
                    'price': other['price']
                }
                processed.add(j)
        
        # Only include if found in at least 2 stores
        if len(group['stores']) >= 2:
            matched.append(group)
    
    return matched

def sort_products(matched_products: List[Dict], sort_by: str = 'price', ascending: bool = True) -> List[Dict]:
    """
    Sort matched products by price or quantity
    
    Args:
        matched_products: List of matched product dicts
        sort_by: 'price' or 'quantity'
        ascending: Sort order
    
    Returns:
        Sorted list of products
    """
    if sort_by == 'price':
        # Sort by lowest available price
        def get_min_price(product):
            prices = []
            for store_data in product.get('stores', {}).values():
                if store_data and store_data.get('price'):
                    prices.append(store_data['price'])
            return min(prices) if prices else float('inf')
        
        return sorted(matched_products, key=get_min_price, reverse=not ascending)
    
    elif sort_by == 'quantity':
        # Sort by normalized quantity
        def get_normalized_qty(product):
            value = product.get('quantity_value', 0)
            unit = product.get('quantity_unit', '')
            return normalize_quantity(value, unit) if value and unit else 0
        
        return sorted(matched_products, key=get_normalized_qty, reverse=not ascending)
    
    return matched_products
