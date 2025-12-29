"""Utility functions for product matching, parsing, and sorting"""
import re
import os
import requests
import json
from typing import List, Dict, Optional, Tuple

# PRODUCT CATEGORY MAPPING
# Loaded from categories.json for easier management
def load_category_config():
    config_path = os.path.join(os.path.dirname(__file__), 'categories.json')
    defaults = {
        "CATEGORIES": {
            "Fresh Produce": ["onion", "potato", "tomato", "carrot", "apple", "banana", "garlic"],
            "Dairy & Eggs": ["milk", "egg", "cheese", "yogurt"],
            "Meat & Seafood": ["chicken", "beef", "fish"],
            "Bakery": ["bread"],
            "Snacks & Sweets": ["chip", "cookie", "chocolate"],
            "Beverages": ["water", "juice", "soda"],
            "Pantry": ["rice", "pasta", "oil"]
        },
        "FRESH_DISQUALIFIERS": ["chip", "powder", "sauce", "paste", "jam", "pickle"]
    }
    
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"[Matcher] Error loading categories.json: {e}")
            
    return defaults

_config = load_category_config()
CATEGORIES = _config.get("CATEGORIES", {})
FRESH_DISQUALIFIERS = _config.get("FRESH_DISQUALIFIERS", [])

def classify_text(text: str) -> Optional[str]:
    """Classify a product name or query into a category based on keywords."""
    if not text:
        return None
    
    text = text.lower()
    
    # Special check for Fresh Produce disqualifiers
    is_processed = any(dq in text for dq in FRESH_DISQUALIFIERS)
    
    # Sort categories to prioritize specific ones if needed
    for category, keywords in CATEGORIES.items():
        if category == "Fresh Produce" and is_processed:
            continue
            
        for kw in keywords:
            # Match whole words or boundaries to avoid 'pear' in 'pearl'
            pattern = r'\b' + re.escape(kw) + r'\b'
            if re.search(pattern, text):
                return category
    
    return None

def calculate_relevance_score(product_name: str, query: str) -> float:
    """
    Calculate a relevance score (0.0 to 1.0) for a product given a query.
    Boosts items that are 'purer' matches for the query.
    """
    name = product_name.lower()
    query = query.lower()
    query_terms = query.split()
    
    if not query_terms:
        return 0.0
    
    score = 0.0
    
    # CHECK: Do all query terms exist as whole words?
    all_terms_as_words = all(re.search(r'\b' + re.escape(term) + r'\b', name) for term in query_terms)
    
    # 1. Exact Name Match (very rare in groceries but high boost)
    if name == query:
        score += 0.5
        
    # 2. Query matches start of name (e.g. "Onion - Red" for query "Onion")
    if name.startswith(query):
        score += 0.3
        
    # 3. Category Match Boost & Processed Item Penalty
    q_cat = classify_text(query)
    p_cat = classify_text(name)
    
    # Check if the product contains any disqualifiers for its query category
    is_processed = any(dq in name for dq in FRESH_DISQUALIFIERS)
    
    if q_cat == "Fresh Produce":
        if is_processed:
            # Massive penalty for chips/wraps when looking for fresh veg
            score -= 0.5
        elif p_cat == "Fresh Produce" and all_terms_as_words:
            # Only give category boost if ALL query terms are whole words
            score += 0.2
            
            # Better Noise Removal for Exact Identity Check
            # Remove weights, units, and symbols like -, (, ), bunch, pack
            noise_pat = r'\b(\d+\s*(kg|g|l|ml|pcs|pack|pk|bunch|grams|kilogram|oz|cm|mm|mtr))\b|[\(\)\-\,\+]'
            clean_name = re.sub(noise_pat, '', name).strip()
            # Remove extra spaces
            clean_name = ' '.join(clean_name.split())
            
            if clean_name == query:
                score += 0.4
    elif q_cat and p_cat == q_cat and all_terms_as_words:
        score += 0.2
    
    # 4. Word Position & Match Quality Boost
    for i, term in enumerate(query_terms):
        # Check for whole-word match first
        is_whole_word = re.search(r'\b' + re.escape(term) + r'\b', name) is not None
        
        if is_whole_word:
            # Significant bonus for whole-word match
            pos = name.find(term)
            if pos < 20:  # Near start
                score += (0.15 / (i + 1))
            else:
                score += 0.05
        elif term in name:
            # Small penalty for substring-only match (e.g., "peas" in "chickpeas")
            # This ensures "peas" >> "chickpeas" when searching "peas"
            score -= 0.1

    return max(0.0, min(score, 1.0))

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
        # Matches patterns like: "12.50", "AED 12.50", "12,50", "1,200.50"
        clean_str = str(price_str).replace(',', '')
        match = re.search(r'(\d+\.?\d*|\d+)', clean_str)
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
    
    # PRIORITY: Check for weight/volume in parentheses first (most reliable)
    # e.g., "Baby Potato - 10-15 Pieces (220-250g)" -> prioritize (220-250g)
    units_regex = r'(kg|kilograms|kilogram|gm|g|grams|gram|l|litres|liters|litre|liter|ltr|ml|pcs|pieces|piece|pc|packs|pack|pck|m|sqft|sq\.ft|sq\s*ft)\b'
    
    paren_pattern = r'\((\d+(?:-\d+)?)\s*' + units_regex + r'\)'
    paren_match = re.search(paren_pattern, product_name.lower())
    if paren_match:
        try:
            quantity_str = paren_match.group(1)
            unit = paren_match.group(2).lower()
            
            # Handle range: take the midpoint
            if '-' in quantity_str:
                parts = quantity_str.split('-')
                value = (float(parts[0]) + float(parts[1])) / 2
            else:
                value = float(quantity_str)
            
            # Normalize unit
            if unit in ['kg', 'kilogram', 'kilograms']:
                return value, 'kg'
            elif unit in ['gm', 'g', 'gram', 'grams']:
                return value, 'g'
            elif unit in ['l', 'ltr', 'litre', 'liter', 'litres', 'liters']:
                return value, 'l'
            elif unit in ['ml']:
                return value, 'ml'
            elif unit in ['pcs', 'piece', 'pieces', 'pc']:
                return value, 'pcs'
            elif unit in ['sqft', 'sq.ft', 'sq ft']:
                return value, 'sqft'
            return value, unit
        except (ValueError, IndexError):
            pass
    
    # Pattern matches: 1kg, 500g, 1.5L, 250ml, 1 kg, 500 g, etc.
    # ORDER MATTERS: precise multipack patterns first
        
    patterns = [
        # ------------------------------------------------------
        # MULTIPACK PATTERNS (Must come before single unit patterns)
        # ------------------------------------------------------

        # 1. SIZE x COUNT (Explicit 'x')
        # e.g., "1kg x 2"
        (r'(\d+\.?\d*)\s*' + units_regex + r'\s*[xX]\s*(\d+\.?\d*)\b', True),

        # 2. COUNT x SIZE (Explicit 'x')
        # e.g., "2 x 500g", "2 packs x 500g"
        (r'(\d+\.?\d*)\s*(?:packs?|pcs|pieces?|sets?)?\s*[xX]\s*(\d+\.?\d*)\s*' + units_regex + r'\b', True),
        
        # 3. SIZE ... COUNT (Implicit multiplication with keywords)
        # e.g., "1kg Pack of 2", "21g 6 PCS"
        # RESTRICTION: Only if COUNT is not part of a range (no hyphen before it)
        (r'(\d+\.?\d*)\s*' + units_regex + r'(?!.*\d+-\d+).*?(?<!-)(\ d+)(?!-)\s*(?:packs?|pcs|pieces?|sets?)\b', True),
        
        # 4. SIZE ... PACK OF COUNT
        # e.g., "1kg Pack of 2" (Specific "Pack of" variant if #3 misses)
        (r'(\d+\.?\d*)\s*' + units_regex + r'.*?pack of\s*(\d+)\b', True),

        # 5. COUNT ... SIZE (Implicit multiplication)
        # e.g., "4 Pieces - 8grams", "3 pack 200g"
        # RESTRICTION: Only if COUNT is NOT a range and SIZE is NOT in parentheses
        (r'(?<!\d-)(\d+)(?!-\d)\s*(?:packs?|pcs|pieces?|sets?)\s*(?:of|-)?(?!\s*\().*?(\d+\.?\d*)\s*' + units_regex + r'\b', True),
        
        # ------------------------------------------------------
        # SINGLE UNIT PATTERNS
        # ------------------------------------------------------
        # Standard: 1.5kg or 0.9-1kg with range support (with boundary check)
        (r'(\d+\.?\d*(?:-\d+\.?\d*)?)\s*' + units_regex + r'\b', False),
    ]
    
    for pattern, is_multipack in patterns:
        match = re.search(pattern, product_name.lower())
        if match:
            # Fix for "Approx 4 pieces": If 'approx' is in the name, treat as single unit
            # "Seed Potato - 750g - Approx 4 pieces per KG" -> Should be 750g, not 3kg (750*4)
            if is_multipack and 'approx' in product_name.lower():
                continue

            groups = match.groups()
            try:
                if is_multipack and len(groups) >= 3:
                     # DEDUPLICATION CHECK: If size and count are the same, treat as single unit
                     # e.g., "30 Pieces - 30 Pieces" should be 30, not 900
                     size_or_count_1 = float(groups[0])
                     if groups[1] in ['kg', 'g', 'l', 'ml', 'm', 'ltr', 'litre', 'liter', 'gram', 'grams', 'kilogram', 'kilograms']:
                         # SIZE x COUNT format
                         size = size_or_count_1
                         unit = groups[1].lower()
                         count = float(groups[2])
                         
                         # If size == count, it's likely a duplicate (e.g., "30 pieces - 30 pieces")
                         if size == count:
                             value = size  # Don't multiply duplicates
                         else:
                             value = size * count
                     else:
                         # COUNT x SIZE format
                         count = size_or_count_1
                         size = float(groups[1])
                         unit = groups[2].lower()
                         
                         # If count == size, it's likely a duplicate
                         if count == size:
                             value = size  # Don't multiply duplicates
                         else:
                             value = count * size
                else:
                    quantity_str = groups[0]
                    unit = groups[-1].lower()
                    
                    # Handle range in single unit (e.g., "0.9-1 kg" or "220-250g")
                    if '-' in str(quantity_str):
                        parts = str(quantity_str).split('-')
                        value = (float(parts[0]) + float(parts[1])) / 2
                    else:
                        value = float(quantity_str)
                                
                # Normalize unit strings
                if unit in ['kg', 'kilogram', 'kilograms']:
                    return value, 'kg'
                elif unit in ['gm', 'g', 'gram', 'grams']:
                    return value, 'g'
                elif unit in ['l', 'ltr', 'litre', 'liter', 'litres', 'liters']:
                    return value, 'l'
                elif unit in ['ml']: # Removed 'm' mapping to 'ml' implicitly here, checking explicit 'ml'
                    return value, 'ml'
                elif unit in ['pcs', 'piece', 'pieces', 'pc', 'pck', 'pack', 'packs']:
                    return value, 'pcs'
                elif unit in ['sqft', 'sq.ft', 'sq ft']:
                    return value, 'sqft'
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
        return value
    elif unit == 'g':
        return value/1000
    
    # Volume normalization to milliliters
    elif unit in ['l', 'ltr', 'litre', 'liter']:
        return value
    elif unit == 'ml':
        return value/1000
    
    return value

def jaccard_similarity(name1: str, name2: str) -> float:
    """
    Calculate order-independent word similarity using Jaccard index.
    Strips quantity information before comparison to focus on product identity.
    
    Args:
        name1: First product name
        name2: Second product name
    
    Returns:
        Jaccard similarity score (0.0 to 1.0)
    """
    # Patterns to remove quantity-related tokens (numbers with units)
    # Order matters: more specific patterns first
    qty_patterns = [
        # Combined multipack: 6x330ml, 330mlx6, 6 x 330 ml
        r'\d+\.?\d*\s*[xX]\s*\d+\.?\d*\s*(kg|g|l|ml|ltr)?\b',
        r'\d+\.?\d*\s*(kg|g|l|ml|ltr)\s*[xX]\s*\d+\.?\d*\b',
        # Standard: 500ml, 1.5kg, 1 L, etc.
        r'\d+\.?\d*\s*(kg|kilograms?|g|grams?|l|ltr|litres?|liters?|ml|pcs|pieces?|pc|packs?|pck|sqft|sq\\.?\\s*ft)\b',
        # Standalone numbers that look like quantities (e.g., "x6", "x 12")
        r'\b[xX]\s*\d+\b',
        # Pack descriptions
        r'\b(pack of|set of|box of)\s*\d+\b',
    ]
    
    clean1 = name1.lower()
    clean2 = name2.lower()
    
    for pattern in qty_patterns:
        clean1 = re.sub(pattern, ' ', clean1)
        clean2 = re.sub(pattern, ' ', clean2)
    
    # Remove special characters and extra spaces
    clean1 = re.sub(r'[^a-z0-9\\s]', ' ', clean1)
    clean2 = re.sub(r'[^a-z0-9\\s]', ' ', clean2)
    
    # Create word sets (filtering out empty strings)
    tokens1 = set(w for w in clean1.split() if w)
    tokens2 = set(w for w in clean2.split() if w)
    
    if not tokens1 or not tokens2:
        return 0.0
    
    intersection = tokens1 & tokens2
    union = tokens1 | tokens2
    
    return len(intersection) / len(union) if union else 0.0

def parse_products_regex(products: List[Dict], store_name: str) -> List[Dict]:
    """
    Step 1: Parse individual products to extract structured data using Regex/Heuristics
    Switched from AI to Python logic to avoid API rate limits.
    
    Args:
        products: List of products from a single store
        store_name: Name of the store
    
    Returns:
        List of parsed products with extracted brand, name, quantity
    """
    if not products:
        return []
    
    print(f"[Parser] Parsing {len(products)} products from {store_name} using regex...")
    result_products = []
    
    for product in products:
        original_name = product.get('name', '')
        if not original_name:
            continue
            
        # 1. Extract Quantity
        qty_val, qty_unit = extract_quantity(original_name)
        
        # 2. Extract Brand & Product Name
        # Strict Rule 1: Brand is ALWAYS the first word
        parts = original_name.strip().split(' ', 1)
        brand = parts[0].strip()
        
        # Strict Rule 2: Product Name is alphanumeric only (preserved spaces)
        raw_name = parts[1].strip() if len(parts) > 1 else ""
        # Remove anything that isn't alphanumeric or space
        product_name = re.sub(r'[^a-zA-Z0-9\s]', '', raw_name)
        # Clean up multiple spaces
        product_name = re.sub(r'\s+', ' ', product_name).strip()

        result_products.append({
            'original_name': original_name,
            'brand': brand,
            'product_name': product_name,
            'quantity_value': qty_val,
            'quantity_unit': qty_unit,
            'price': product.get('price'),
            'image_url': product.get('image_url'),
            'product_url': product.get('product_url'),
            'store': store_name
        })
            
    return result_products

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
        # Determine strictness based on whether brand is known
        brand_known = key[0] != "unknown"
        threshold = 0.8 # Jaccard threshold (0.8 = 80% word overlap required)
        
        # Simple clustering
        clusters = []
        processed_indexes = set()
        
        for i in range(len(items)):
            if i in processed_indexes:
                continue
            
            current_cluster = [items[i]]
            processed_indexes.add(i)
            
            base_name = items[i].get('original_name', '')
            
            for j in range(i + 1, len(items)):
                if j in processed_indexes:
                    continue
                
                compare_name = items[j].get('original_name', '')
                
                # Check similarity using Jaccard (order-independent word matching)
                ratio = jaccard_similarity(base_name, compare_name)
                
                if ratio >= threshold:
                    current_cluster.append(items[j])
                    processed_indexes.add(j)
            
            clusters.append(current_cluster)
            
        # 3. Format valid clusters
        for cluster in clusters:
            stores_dict = {}
            min_price = float('inf')
            
            for prod in cluster:
                store = prod.get('store')
                if store:
                    # Keep the lowest price if duplicate store in cluster
                    current_price = parse_price(prod.get('price', ''))
                    
                    if current_price is not None and current_price < min_price:
                        min_price = current_price
                    
                    if store not in stores_dict or (current_price is not None and 
                        (stores_dict[store]['price'] is None or current_price < stores_dict[store]['price'])):
                        
                        stores_dict[store] = {
                            'name': prod.get('original_name', ''),
                            'price': current_price,
                            'product_url': prod.get('product_url')
                        }
            
            # Select primary image for the group (first available)
            primary_image = None
            for prod in cluster:
                if prod.get('image_url'):
                    primary_image = prod.get('image_url')
                    break
            
            # Calculate normalized unit price (Price per base unit)
            normalized_qty = 0
            unit_price = None
            
            qty_val = cluster[0].get('quantity_value')
            qty_unit = cluster[0].get('quantity_unit')
            
            if qty_val and qty_unit:
                normalized_qty = normalize_quantity(qty_val, qty_unit)
                if normalized_qty > 0 and min_price != float('inf'):
                    # Calculate price per kg or per L (normalized_qty is in g or ml)
                    unit_price = (min_price / normalized_qty)

            # Use the most common product name or the first one as the matched name
            # clean_name = cluster[0].get('product_name') or cluster[0].get('original_name')
            
            # Key is (brand, qty_val, qty_unit)
            matched_groups.append({
                'matched_name': cluster[0].get('original_name', ''),
                # 'matched_name': f"{key[0].title()} {clean_name} {key[1] or ''}{key[2] or ''}".strip(),
                'brand': cluster[0].get('brand'),
                'primary_image': primary_image,
                'quantity_value': qty_val,
                'quantity_unit': qty_unit,
                'normalized_unit_price': unit_price,
                'stores': stores_dict
            })

    return matched_groups

def match_products(store_results: Dict[str, Dict], openrouter_api_key: str, query: str = None) -> List[Dict]:
    """
    Two-step product matching:
    1. Parse products (using Regex/Heuristics now)
    2. Group products (using Python logic)
    3. Sort by Unit Price and identify Exact Matches
    
    Args:
        store_results: Dict with keys 'carrefour', 'noon', 'talabat' containing product lists
        openrouter_api_key: Unused now, kept for signature compatibility
        query: Search query string to identify exact matches
    
    Returns:
        List of matched products with unified structure
    """
    try:
        # Parse products from each store sequentially
        print("[Matcher] Parsing products sequentially using Python logic...")
        all_parsed = []
        
        for store_name in ['carrefour', 'noon', 'talabat', 'amazon']:
            products = store_results.get(store_name, {}).get('products', [])
            products = [p for p in products if 'Error' not in p.get('name', '') and p.get('name') != 'No results found']
            
            if products:
                try:
                    # Switch parsers here:
                    # Option A: Use AI Parser
                    # result = parse_products_ai(products, store_name, openrouter_api_key)
                    # Option B: Use Regex Parser (Default)
                    result = parse_products_regex(products, store_name)
                    
                    if result:
                        all_parsed.extend(result)
                except Exception as e:
                    print(f"[Matcher] Parse error for {store_name}: {str(e)}")
        
        if not all_parsed:
            print("[Matcher] No products parsed, returning empty list.")
            return []
        
        print(f"[Matcher] Parsed {len(all_parsed)} products")
        
        # Step 2: Group parsed products
        print("[Matcher] Step 2: Grouping matches...")
        matched_products = group_parsed_products(all_parsed)
        
        # Step 3: Sort by Relevance Score (Category-Aware Ranking)
        if matched_products:
            query_terms = query.lower().split() if query else []
            
            for item in matched_products:
                # Determine match type and relevance
                match_type = 'partial'
                relevance = 0.0
                
                if query:
                    name = item.get('matched_name', '').lower()
                    present_count = sum(1 for term in query_terms if term in name)
                    
                    # Calculate structured relevance score
                    relevance = calculate_relevance_score(name, query)
                    
                    # SMART EXACT MATCH CRITERIA:
                    # Mark as 'exact' if all query terms are present AND:
                    # - Relevance score is POSITIVE (not a penalized processed item) AND
                    # - Either has decent score (>0.25) OR is Fresh Produce with any positive score
                    if present_count == len(query_terms) and relevance > 0:
                        q_cat = classify_text(query)
                        if relevance > 0.25 or q_cat == "Fresh Produce":
                            match_type = 'exact'
                
                item['match_type'] = match_type
                item['relevance_score'] = relevance
            
            def get_sort_key(item):
                # PRIMARY SORT: Relevance Score (Descending)
                # This is now the MAIN ranking criterion
                rel_score = -item.get('relevance_score', 0)
                
                # SECONDARY SORT: Match Type (exact first, but only matters if relevance tied)
                match_val = 0 if item.get('match_type') == 'exact' else 1
                
                # TERTIARY SORT: Normalized Unit Price (Ascending)
                unit_price = item.get('normalized_unit_price')
                if unit_price is None:
                    unit_price = float('inf')
                
                return (rel_score, match_val, unit_price)
            
            # Sort all items by relevance first
            matched_products.sort(key=get_sort_key)
        
        print(f"[Matcher] Successfully matched {len(matched_products)} product groups")
        return matched_products
            
    except Exception as e:
        print(f"[Matcher] Error: {str(e)}")
        return []

def parse_products_ai(products: List[Dict], store_name: str, openrouter_api_key: str) -> List[Dict]:
    """
    Step 1: Parse individual products to extract structured data (AI Version)
    
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
                "reasoning": {
                    "effort": 'low'
                },
                "max_output_tokens": 2000,
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

def fallback_matching(store_results: Dict[str, Dict]) -> List[Dict]:
    """
    Simple fallback matching when AI is unavailable
    Groups products by extracted brand and quantity
    """
    print("[AI Matching] Using fallback matching")
    
    all_products = []
    
    # Collect all products with store info
    for store in ['carrefour', 'noon', 'talabat', 'amazon']:
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
        # Sort by normalized unit price (Best Value)
        def get_unit_price(product):
            p = product.get('normalized_unit_price')
            return p if p is not None else float('inf')
        
        return sorted(matched_products, key=get_unit_price, reverse=not ascending)
    
    elif sort_by == 'quantity':
        # Sort by normalized quantity
        def get_normalized_qty(product):
            value = product.get('quantity_value', 0)
            unit = product.get('quantity_unit', '')
            return normalize_quantity(value, unit) if value and unit else 0
        
        return sorted(matched_products, key=get_normalized_qty, reverse=not ascending)

    elif sort_by == 'name':
         # Sort by matched name
        return sorted(matched_products, key=lambda x: (x.get('matched_name') or '').lower(), reverse=not ascending)
    
    return matched_products