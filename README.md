# Grocy - Dubai's Smart Grocery Comparator

A powerful web application that compares real-time grocery prices across major Dubai retailers: **Carrefour**, **Noon**, **Amazon.ae**, and **Talabat**.

## 🚀 Key Features

- **Real-Time Price Comparison**: Live scraping and API integration to fetch up-to-the-minute prices from Carrefour, Noon, Amazon, and Talabat.
- **Price History & Trends**: Every search tracks prices using **CDC Type 2** logic, recording daily snapshots of product costs.
- **Interactive Analytics Dashboard**: A dedicated dashboard (`/analytics`) to track historical trends, see the number of tracked products, and view price fluctuations over time.
- **Smart Product Matching**: Uses token-based **Jaccard similarity** and intelligent regex patterns to group identical products across different stores, even with varying naming conventions.
- **Unit Normalization**: Automatically converts units (g, kg, ml, L, packs) to a standard base unit to calculate and compare price per unit (e.g., AED/kg).
- **Visualization**: Built-in **Chart.js** integration to visualize price history directly within search results and the analytics dashboard.
- **Clean UI**: A premium, responsive web interface built with Tailwind CSS, featuring visual progress indicators and "Best Deal" highlighting.

## 🛠️ Tech Stack

- **Backend**: Python (Flask)
- **Web Scraping**: Selenium (Carrefour, Noon, Amazon), Requests (Talabat API)
- **Database**: SQLite with custom CDC Type 2 implementation for historical tracking
- **Frontend**: HTML5, Tailwind CSS, Vanilla JavaScript, Chart.js
- **Matching Logic**: Jaccard Similarity, Regex Parsing (Optional OpenRouter/LLM support)

## 📋 Prerequisites

- Python 3.8+
- Chrome Browser (for Selenium automation)
- [Optional] OpenRouter API Key (to enable LLM-based parsing)

## 📦 Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/yourusername/grocery-price-comparator.git
    cd grocery-price-comparator
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Set up Environment Variables:**
    Create a `.env` file in the root directory (optional but recommended for AI features):
    ```env
    OPENROUTER_API_KEY=your_openrouter_key_here
    ```

## ▶️ Usage

1.  **Start the application:**
    ```bash
    python app.py
    ```
    *Note: The application pre-loads browser sessions in the background to ensure fast search response times.*

2.  **Access the Web Interface:**
    - **Search**: Open `http://127.0.0.1:5000`
    - **Analytics**: Open `http://127.0.0.1:5000/analytics`

3.  **Search & Track**:
    Enter a product (e.g., "Al Ain Milk 1L"). The app will:
    - Scrape all 4 stores in parallel.
    - Match and group the products.
    - Save the latest prices to the database.
    - Provide a "Price History" button to see how the price has changed over the last 30 days.

## 🏗️ Project Structure

```
grocery-price-comparator/
├── app.py                 # Main Flask application & routing
├── utils.py               # Matching algorithms, unit normalization, parsing
├── database.py            # SQLite schema, CDC Type 2 logic, analytics queries
├── requirements.txt       # Project dependencies
├── static/                # CSS, JS, and Assets
│   ├── js/main.js         # Core frontend search & matching logic
│   └── logos/             # Store logos
└── templates/             # UI Templates
    ├── index.html         # Main search interface
    └── analytics.html     # Historical data dashboard
```

## ⚠️ Disclaimer

This tool is for educational purposes only. Please respect the Terms of Service of the respective retailers. Automated scraping should be done responsibly and within legal boundaries.
