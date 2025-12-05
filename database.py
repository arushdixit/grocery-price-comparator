"""Database models and initialization for price tracking"""
import sqlite3
import os
from datetime import datetime
from contextlib import contextmanager

DB_PATH = 'grocery_prices.db'

def init_database():
    """Initialize database with required tables"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Products table - stores matched/unified product info
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            matched_name TEXT UNIQUE NOT NULL,
            brand TEXT,
            quantity_value REAL,
            quantity_unit TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Prices table - stores historical price data
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            store TEXT NOT NULL,
            price REAL NOT NULL,
            raw_name TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(product_id) REFERENCES products(id)
        )
    ''')
    
    # Create indexes for better query performance
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_prices_product_store 
        ON prices(product_id, store, timestamp DESC)
    ''')
    
    cursor.execute('''
        CREATE INDEX IF NOT EXISTS idx_prices_timestamp 
        ON prices(timestamp DESC)
    ''')
    
    # Search logs table - tracks user searches
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS search_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            result_count INTEGER
        )
    ''')
    
    conn.commit()
    conn.close()
    print("[Database] Initialized successfully")

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

def save_product_and_prices(matched_products):
    """
    Save matched products and their prices to database
    
    Args:
        matched_products: List of dicts with structure:
            {
                'matched_name': str,
                'brand': str,
                'quantity_value': float,
                'quantity_unit': str,
                'stores': {
                    'carrefour': {'name': str, 'price': float} or None,
                    'noon': {'name': str, 'price': float} or None,
                    'talabat': {'name': str, 'price': float} or None
                }
            }
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        for product in matched_products:
            # Insert or get product ID
            cursor.execute('''
                INSERT OR IGNORE INTO products (matched_name, brand, quantity_value, quantity_unit)
                VALUES (?, ?, ?, ?)
            ''', (
                product['matched_name'],
                product.get('brand'),
                product.get('quantity_value'),
                product.get('quantity_unit')
            ))
            
            cursor.execute('SELECT id FROM products WHERE matched_name = ?', 
                          (product['matched_name'],))
            product_id = cursor.fetchone()[0]
            
            # Insert prices for each store
            for store, data in product.get('stores', {}).items():
                if data and data.get('price') is not None:
                    cursor.execute('''
                        INSERT INTO prices (product_id, store, price, raw_name)
                        VALUES (?, ?, ?, ?)
                    ''', (
                        product_id,
                        store,
                        data['price'],
                        data.get('name', '')
                    ))

def log_search(query, result_count):
    """Log a search query"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO search_logs (query, result_count)
            VALUES (?, ?)
        ''', (query, result_count))

def get_price_history(product_id, days=30):
    """Get price history for a product across all stores"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT store, price, timestamp
            FROM prices
            WHERE product_id = ?
            AND timestamp >= datetime('now', '-' || ? || ' days')
            ORDER BY timestamp DESC
        ''', (product_id, days))
        return cursor.fetchall()

def get_product_analytics(limit=100):
    """Get analytics data for dashboard"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Get products with latest prices from each store
        cursor.execute('''
            SELECT 
                p.id,
                p.matched_name,
                p.brand,
                p.quantity_value,
                p.quantity_unit,
                MAX(CASE WHEN pr.store = 'carrefour' THEN pr.price END) as carrefour_price,
                MAX(CASE WHEN pr.store = 'carrefour' THEN pr.timestamp END) as carrefour_time,
                MAX(CASE WHEN pr.store = 'noon' THEN pr.price END) as noon_price,
                MAX(CASE WHEN pr.store = 'noon' THEN pr.timestamp END) as noon_time,
                MAX(CASE WHEN pr.store = 'talabat' THEN pr.price END) as talabat_price,
                MAX(CASE WHEN pr.store = 'talabat' THEN pr.timestamp END) as talabat_time
            FROM products p
            LEFT JOIN (
                SELECT product_id, store, price, timestamp
                FROM prices
                WHERE (product_id, store, timestamp) IN (
                    SELECT product_id, store, MAX(timestamp)
                    FROM prices
                    GROUP BY product_id, store
                )
            ) pr ON p.id = pr.product_id
            GROUP BY p.id, p.matched_name, p.brand, p.quantity_value, p.quantity_unit
            ORDER BY p.id DESC
            LIMIT ?
        ''', (limit,))
        
        return cursor.fetchall()

def get_search_trends(days=7, limit=20):
    """Get most popular search queries"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT query, COUNT(*) as count, MAX(timestamp) as last_search
            FROM search_logs
            WHERE timestamp >= datetime('now', '-' || ? || ' days')
            GROUP BY LOWER(query)
            ORDER BY count DESC
            LIMIT ?
        ''', (days, limit))
        return cursor.fetchall()

# Initialize database on import
if not os.path.exists(DB_PATH):
    init_database()
