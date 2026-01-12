"""Database models and initialization for price tracking with PostgreSQL (Supabase)"""
import psycopg2
from psycopg2.extras import DictCursor
import os
from datetime import date, datetime
from contextlib import contextmanager
from typing import List, Dict, Optional, Any
from dotenv import load_dotenv

load_dotenv()

# Use DATABASE_URL from environment
DATABASE_URL = os.environ.get('DATABASE_URL')

def init_database():
    """Initialize database with required tables using PostgreSQL schema"""
    if not DATABASE_URL:
        print("[Database] Skipping initialization: DATABASE_URL not set")
        return

    try:
        conn = psycopg2.connect(DATABASE_URL)
        cursor = conn.cursor()
        
        # Products table - canonical product identity
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS products (
                id SERIAL PRIMARY KEY,
                normalized_name TEXT UNIQUE NOT NULL,
                brand TEXT,
                quantity_value REAL,
                quantity_unit TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Store products table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS store_products (
                id SERIAL PRIMARY KEY,
                product_id INTEGER NOT NULL REFERENCES products(id),
                store_name TEXT NOT NULL,
                store_product_name TEXT NOT NULL,
                product_url TEXT,
                image_url TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(product_id, store_name)
            )
        ''')
        
        # Price history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS price_history (
                id SERIAL PRIMARY KEY,
                store_product_id INTEGER NOT NULL REFERENCES store_products(id),
                price REAL NOT NULL,
                effective_date DATE NOT NULL,
                is_current BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(store_product_id, effective_date)
            )
        ''')
        
        # Create indexes
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_price_history_store_product ON price_history(store_product_id, effective_date DESC)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_store_products_product ON store_products(product_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_price_history_current ON price_history(is_current, store_product_id)')
        
        conn.commit()
        cursor.close()
        conn.close()
        print("[Database] Initialized PostgreSQL schema")
    except Exception as e:
        print(f"[Database] Error initializing database: {e}")

@contextmanager
def get_db_connection():
    """Context manager for PostgreSQL database connections"""
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=DictCursor)
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def upsert_product(cursor, normalized_name: str, brand: str = None, 
                   quantity_value: float = None, quantity_unit: str = None) -> int:
    """Insert or get product ID"""
    cursor.execute('''
        INSERT INTO products (normalized_name, brand, quantity_value, quantity_unit)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (normalized_name) DO UPDATE SET
            brand = COALESCE(excluded.brand, products.brand),
            quantity_value = COALESCE(excluded.quantity_value, products.quantity_value),
            quantity_unit = COALESCE(excluded.quantity_unit, products.quantity_unit)
        RETURNING id
    ''', (normalized_name, brand, quantity_value, quantity_unit))
    return cursor.fetchone()[0]

def upsert_store_product(cursor, product_id: int, store_name: str, 
                         store_product_name: str, product_url: str = None,
                         image_url: str = None) -> int:
    """Insert or get store product ID"""
    cursor.execute('''
        INSERT INTO store_products (product_id, store_name, store_product_name, product_url, image_url)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT(product_id, store_name) DO UPDATE SET
            store_product_name = excluded.store_product_name,
            product_url = COALESCE(excluded.product_url, store_products.product_url),
            image_url = COALESCE(excluded.image_url, store_products.image_url)
        RETURNING id
    ''', (product_id, store_name, store_product_name, product_url, image_url))
    return cursor.fetchone()[0]

def record_price(cursor, store_product_id: int, price: float, effective_date: date = None):
    """Record a price using CDC Type 2 logic."""
    if effective_date is None:
        effective_date = date.today()
    
    # Upsert price for this date
    cursor.execute('''
        INSERT INTO price_history (store_product_id, price, effective_date, is_current)
        VALUES (%s, %s, %s, TRUE)
        ON CONFLICT(store_product_id, effective_date) DO UPDATE SET
            price = excluded.price,
            is_current = TRUE,
            created_at = CURRENT_TIMESTAMP
    ''', (store_product_id, price, effective_date))
    
    # Mark older records as not current
    cursor.execute('''
        UPDATE price_history 
        SET is_current = FALSE 
        WHERE store_product_id = %s AND effective_date < %s
    ''', (store_product_id, effective_date))

def save_search_results(matched_products: List[Dict]) -> int:
    """Save matched products and prices from a search."""
    if not matched_products:
        return 0
    
    saved_count = 0
    today = date.today()
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        for product in matched_products:
            matched_name = product.get('matched_name')
            if not matched_name:
                continue
            
            product_id = upsert_product(
                cursor,
                normalized_name=matched_name,
                brand=product.get('brand'),
                quantity_value=product.get('quantity_value'),
                quantity_unit=product.get('quantity_unit')
            )
            
            stores = product.get('stores', {})
            primary_image = product.get('primary_image')
            
            for store_name, store_data in stores.items():
                if not store_data or store_data.get('price') is None:
                    continue
                
                store_product_id = upsert_store_product(
                    cursor,
                    product_id=product_id,
                    store_name=store_name,
                    store_product_name=store_data.get('name', matched_name),
                    product_url=store_data.get('product_url'),
                    image_url=primary_image
                )
                
                record_price(cursor, store_product_id, store_data['price'], today)
            
            saved_count += 1
    
    print(f"[Database] Saved {saved_count} products with prices")
    return saved_count

def get_price_history(product_id: int, days: int = 30) -> List[Dict]:
    """Get price history for a product across all stores."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                sp.store_name,
                ph.effective_date,
                ph.price,
                sp.store_product_name
            FROM price_history ph
            JOIN store_products sp ON ph.store_product_id = sp.id
            WHERE sp.product_id = %s
            AND ph.effective_date >= CURRENT_DATE - (%s || ' days')::INTERVAL
            ORDER BY ph.effective_date DESC, sp.store_name
        ''', (product_id, days))
        
        return [dict(row) for row in cursor.fetchall()]

def get_db_stats() -> Dict[str, int]:
    """Get total counts for products and price history records"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM products")
        product_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM price_history")
        price_count = cursor.fetchone()[0]
        
        return {
            'product_count': product_count,
            'price_count': price_count
        }

def get_product_by_name(matched_name: str) -> Optional[Dict]:
    """Get product by its normalized/matched name"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT id, normalized_name, brand, quantity_value, quantity_unit
            FROM products WHERE normalized_name = %s
        ''', (matched_name,))
        row = cursor.fetchone()
        return dict(row) if row else None

def get_all_tracked_products(limit: Optional[int] = None) -> List[Dict]:
    """Get all tracked products with their latest prices."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        query = '''
            SELECT 
                p.id,
                p.normalized_name,
                p.brand,
                p.quantity_value,
                p.quantity_unit,
                p.created_at,
                (
                    SELECT STRING_AGG(sp2.store_name || ':' || ph2.price, '|')
                    FROM store_products sp2
                    JOIN price_history ph2 ON sp2.id = ph2.store_product_id AND ph2.is_current = TRUE
                    WHERE sp2.product_id = p.id
                ) as current_prices
            FROM products p
            ORDER BY p.normalized_name ASC
        '''
        
        if limit is not None:
            query += " LIMIT %s"
            cursor.execute(query, (limit,))
        else:
            cursor.execute(query)
        
        results = []
        for row in cursor.fetchall():
            item = dict(row)
            prices_str = item.pop('current_prices', '')
            item['stores'] = {}
            if prices_str:
                for pair in prices_str.split('|'):
                    if ':' in pair:
                        store, price = pair.split(':', 1)
                        try:
                            item['stores'][store] = float(price)
                        except ValueError:
                            pass
            results.append(item)
        
        return results

def get_price_comparison(product_id: int) -> Dict:
    """Get current prices for a product across all stores"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM products WHERE id = %s', (product_id,))
        product_row = cursor.fetchone()
        if not product_row:
            return {}
        
        result = dict(product_row)
        
        cursor.execute('''
            SELECT 
                sp.store_name,
                sp.store_product_name,
                sp.product_url,
                sp.image_url,
                ph.price,
                ph.effective_date
            FROM store_products sp
            JOIN price_history ph ON sp.id = ph.store_product_id AND ph.is_current = TRUE
            WHERE sp.product_id = %s
        ''', (product_id,))
        
        result['stores'] = {}
        for row in cursor.fetchall():
            result['stores'][row['store_name']] = {
                'name': row['store_product_name'],
                'price': row['price'],
                'product_url': row['product_url'],
                'image_url': row['image_url'],
                'last_updated': row['effective_date']
            }
        
        return result

def get_price_trends(product_id: int) -> Dict[str, str]:
    """Compare current prices with previous prices to determine trends."""
    trends = {}
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id, store_name FROM store_products WHERE product_id = %s', (product_id,))
            rows = cursor.fetchall()
            
            for row in rows:
                sp_id, store_name = row['id'], row['store_name']
                cursor.execute('''
                    SELECT price FROM price_history 
                    WHERE store_product_id = %s 
                    ORDER BY effective_date DESC, created_at DESC 
                    LIMIT 2
                ''', (sp_id,))
                prices = [r[0] for r in cursor.fetchall()]
                
                if len(prices) >= 2:
                    curr, prev = prices[0], prices[1]
                    if curr < prev:
                        trends[store_name] = 'down'
                    elif curr > prev:
                        trends[store_name] = 'up'
                    else:
                        trends[store_name] = 'stable'
                else:
                    trends[store_name] = 'new'
    except Exception as e:
        print(f"Error fetching trends: {e}")
    return trends

# Initialize database on import if URL is present
if DATABASE_URL:
    init_database()
