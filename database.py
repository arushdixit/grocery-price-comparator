"""Database models and initialization for price tracking with CDC Type 2"""
import sqlite3
import os
from datetime import date, datetime
from contextlib import contextmanager
from typing import List, Dict, Optional, Any

DB_PATH = 'grocery_prices.db'


def init_database():
    """Initialize database with required tables using CDC Type 2 schema"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Products table - canonical product identity (matched across stores)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            normalized_name TEXT UNIQUE NOT NULL,
            brand TEXT,
            quantity_value REAL,
            quantity_unit TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Store products table - store-specific product information
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS store_products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            store_name TEXT NOT NULL,
            store_product_name TEXT NOT NULL,
            product_url TEXT,
            image_url TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(product_id) REFERENCES products(id),
            UNIQUE(product_id, store_name)
        )
    ''')
    
    # Price history table - CDC Type 2 with effective_date
    # Only one price per store_product per day (latest wins)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            store_product_id INTEGER NOT NULL,
            price REAL NOT NULL,
            effective_date DATE NOT NULL,
            is_current BOOLEAN DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(store_product_id) REFERENCES store_products(id),
            UNIQUE(store_product_id, effective_date)
        )
    ''')
    
    # Create indexes for performance
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_price_history_store_product 
        ON price_history(store_product_id, effective_date DESC)
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_store_products_product 
        ON store_products(product_id)
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_price_history_current 
        ON price_history(is_current, store_product_id)
    ''')
    
    conn.commit()
    conn.close()
    print("[Database] Initialized with CDC Type 2 schema")


@contextmanager
def get_db_connection():
    """Context manager for database connections"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
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
        INSERT OR IGNORE INTO products (normalized_name, brand, quantity_value, quantity_unit)
        VALUES (?, ?, ?, ?)
    ''', (normalized_name, brand, quantity_value, quantity_unit))
    
    cursor.execute('SELECT id FROM products WHERE normalized_name = ?', (normalized_name,))
    return cursor.fetchone()[0]


def upsert_store_product(cursor, product_id: int, store_name: str, 
                         store_product_name: str, product_url: str = None,
                         image_url: str = None) -> int:
    """Insert or get store product ID"""
    cursor.execute('''
        INSERT INTO store_products (product_id, store_name, store_product_name, product_url, image_url)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(product_id, store_name) DO UPDATE SET
            store_product_name = excluded.store_product_name,
            product_url = COALESCE(excluded.product_url, store_products.product_url),
            image_url = COALESCE(excluded.image_url, store_products.image_url)
    ''', (product_id, store_name, store_product_name, product_url, image_url))
    
    cursor.execute('''
        SELECT id FROM store_products WHERE product_id = ? AND store_name = ?
    ''', (product_id, store_name))
    return cursor.fetchone()[0]


def record_price(cursor, store_product_id: int, price: float, effective_date: date = None):
    """
    Record a price using CDC Type 2 logic.
    - If no price exists for this date, insert new row
    - If price exists for this date, update it (last wins)
    - Mark previous prices as not current
    """
    if effective_date is None:
        effective_date = date.today()
    
    # Upsert price for this date (INSERT or UPDATE if same date)
    cursor.execute('''
        INSERT INTO price_history (store_product_id, price, effective_date, is_current)
        VALUES (?, ?, ?, 1)
        ON CONFLICT(store_product_id, effective_date) DO UPDATE SET
            price = excluded.price,
            is_current = 1,
            created_at = CURRENT_TIMESTAMP
    ''', (store_product_id, price, effective_date.isoformat()))
    
    # Mark older records as not current (keep only latest as current)
    cursor.execute('''
        UPDATE price_history 
        SET is_current = 0 
        WHERE store_product_id = ? AND effective_date < ?
    ''', (store_product_id, effective_date.isoformat()))


def save_search_results(matched_products: List[Dict]) -> int:
    """
    Save matched products and prices from a search.
    Returns the number of products saved.
    
    Args:
        matched_products: List from match_products() with structure:
            {
                'matched_name': str,
                'brand': str,
                'quantity_value': float,
                'quantity_unit': str,
                'primary_image': str,
                'stores': {
                    'carrefour': {'name': str, 'price': float, 'product_url': str},
                    ...
                }
            }
    """
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
            
            # 1. Upsert canonical product
            product_id = upsert_product(
                cursor,
                normalized_name=matched_name,
                brand=product.get('brand'),
                quantity_value=product.get('quantity_value'),
                quantity_unit=product.get('quantity_unit')
            )
            
            # 2. Process each store
            stores = product.get('stores', {})
            primary_image = product.get('primary_image')
            
            for store_name, store_data in stores.items():
                if not store_data or store_data.get('price') is None:
                    continue
                
                # Upsert store-specific product
                store_product_id = upsert_store_product(
                    cursor,
                    product_id=product_id,
                    store_name=store_name,
                    store_product_name=store_data.get('name', matched_name),
                    product_url=store_data.get('product_url'),
                    image_url=primary_image
                )
                
                # Record price (CDC Type 2)
                record_price(cursor, store_product_id, store_data['price'], today)
            
            saved_count += 1
    
    print(f"[Database] Saved {saved_count} products with prices")
    return saved_count


def get_price_history(product_id: int, days: int = 30) -> List[Dict]:
    """
    Get price history for a product across all stores.
    Returns list of {store_name, date, price} records.
    """
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
            WHERE sp.product_id = ?
            AND ph.effective_date >= date('now', '-' || ? || ' days')
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
            FROM products WHERE normalized_name = ?
        ''', (matched_name,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_all_tracked_products(limit: int = 100) -> List[Dict]:
    """
    Get all tracked products with their latest prices from each store.
    For analytics dashboard.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                p.id,
                p.normalized_name,
                p.brand,
                p.quantity_value,
                p.quantity_unit,
                p.created_at,
                (
                    SELECT GROUP_CONCAT(sp2.store_name || ':' || ph2.price, '|')
                    FROM store_products sp2
                    JOIN price_history ph2 ON sp2.id = ph2.store_product_id AND ph2.is_current = 1
                    WHERE sp2.product_id = p.id
                ) as current_prices
            FROM products p
            ORDER BY p.id DESC
            LIMIT ?
        ''', (limit,))
        
        results = []
        for row in cursor.fetchall():
            item = dict(row)
            # Parse current_prices string into dict
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
        
        # Get product info
        cursor.execute('SELECT * FROM products WHERE id = ?', (product_id,))
        product_row = cursor.fetchone()
        if not product_row:
            return {}
        
        result = dict(product_row)
        
        # Get current prices
        cursor.execute('''
            SELECT 
                sp.store_name,
                sp.store_product_name,
                sp.product_url,
                sp.image_url,
                ph.price,
                ph.effective_date
            FROM store_products sp
            JOIN price_history ph ON sp.id = ph.store_product_id AND ph.is_current = 1
            WHERE sp.product_id = ?
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


# Initialize database on import
if not os.path.exists(DB_PATH):
    init_database()
