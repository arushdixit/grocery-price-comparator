# Dubai Grocery Price Comparator

A powerful web application that compares real-time grocery prices across major Dubai retailers: **Carrefour**, **Noon**, and **Talabat**.

## 🚀 Key Features

- **Real-Time Price Comparison**: Live scraping and API integration to fetch up-to-the-minute prices.
- **AI-Powered Product Matching**: Uses LLMs (via OpenRouter) and intelligent regex patterns to match the same product across different stores despite naming variations.
- **Smart Unit Normalization**: Automatically converts various units (g, kg, ml, L, packs) to a standard base unit to calculate and compare price per unit (e.g., AED/kg).
- **Intelligent Sorting**: Sort results by "Best Price" (unit price), raw price, or product name.
- **Multipack Handling**: Correctly detects and calculates value for multipacks (e.g., "1kg x 2", "Pack of 3").
- **Clean UI**: Responsive web interface with visual indicators for loading states and store availability.
- **Historical Data**: Architecture supports logging prices to a SQLite database for analytics.

## 🛠️ Tech Stack

- **Backend**: Python (Flask)
- **Web Scraping**: Selenium (Carrefour, Noon), Requests (Talabat API)
- **Data Processing**: BeautifulSoup4, Regex, OpenRouter API (LLM for matching)
- **Database**: SQLite (SQLAlchemy)
- **Frontend**: HTML5, CSS3, Vanilla JavaScript

## 📋 Prerequisites

- Python 3.8+
- Chrome Browser (for Selenium automation)
- [Optional] OpenRouter API Key (for AI features)

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
    Create a `.env` file in the root directory:
    ```env
    OPENROUTER_API_KEY=your_openrouter_key_here
    ```

## ▶️ Usage

1.  **Start the application:**
    ```bash
    python app.py
    ```
    *Note: On first run, the application may pre-load browser sessions in the background.*

2.  **Access the Web Interface:**
    Open your browser and navigate to `http://127.0.0.1:5000`.

3.  **Search**:
    Enter a product name (e.g., "Masoor Dal", "Milk", "Dove Soap") and hit Enter. The app will fetch results from all stores, normalize them, and display the best deals.

## 🏗️ Project Structure

```
grocery-price-comparator/
├── app.py                 # Main Flask application & routing
├── utils.py               # Core logic: AI matching, unit normalization, parsing
├── database.py            # Database models & interaction
├── requirements.txt       # Project dependencies
├── static/                # CSS, JS, and Images
│   ├── css/
│   ├── js/
│   └── logos/
└── templates/             # HTML templates
```

## ⚠️ Disclaimer

This tool is for educational purposes only. Please respect the Terms of Service of the respective retailers. Automated scraping should be done responsibly.
