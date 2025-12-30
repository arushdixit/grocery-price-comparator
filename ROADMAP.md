# PriceHunt UAE - Enhancement Roadmap

## 🎯 Your Ideas (Excellent!)

### 1. Scheduled Scraping for Tracked Items ⭐⭐⭐
**What**: Background job that periodically checks prices for your favorite products.
**Why**: Always-fresh data without manual searches.
**How**:
- [ ] Add a "Track this product" star/bookmark button
- [ ] Use Python `schedule` library or cron jobs
- [ ] Store tracked items in a new `tracked_items` table
- [ ] Run scraper every 6-12 hours for tracked items only

**Complexity**: Medium | **Impact**: High

---

### 2. Price Drop Notifications 🔔 ⭐⭐⭐
**What**: Alert when price falls below a threshold.
**Why**: Never miss a deal!
**How**:
- [ ] **Phase 1**: Email notifications (using `smtplib` or SendGrid)
- [ ] **Phase 2**: Browser push notifications (Web Push API)
- [ ] **Phase 3**: Telegram/WhatsApp bot integration
- [ ] Add "Notify me at AED X.XX" button per product

**Complexity**: Medium-High | **Impact**: Very High

---

### 3. Price Trend Indicators in Cards 📈 ⭐⭐
**What**: Mini sparkline or arrow showing if price is rising/falling/stable.
**Why**: Quick visual feedback in search results.
**How**:
- [x] Query last 7 days of price history
- [x] Show green ↓ (cheaper), red ↑ (more expensive), gray → (stable)
- [x] Optional: Mini Chart.js sparkline (10px tall) -> *Implemented as full History Modal with Chart.js*

**Complexity**: Low | **Impact**: Medium

---

## 🔍 Search Quality Improvements

### 4. Category-Aware Search Ranking ⭐⭐⭐⭐
**Problem**: "onion" returns chips and jams before actual onions.
**Solution A: Product Categories (Recommended)**
- [x] Classify products into categories using keywords
- [x] Boost fresh produce results when query matches produce keywords
- [x] Store category in database

**Solution B: LLM Classification (AI-Powered)**
- [ ] On first search, ask GPT-4 to classify each product
- [ ] Cache classifications in database

**Complexity**: Low (A) / Medium (B) | **Impact**: Very High

---

### 5. Smart Query Understanding ⭐⭐⭐
**What**: Detect user intent from query.
**Examples**:
- "fresh strawberries" → prioritize produce
- "strawberry jam" → prioritize pantry items
- "1kg rice" → filter by exact quantity

**How**:
- [x] Use regex to detect intent keywords: `fresh`, `organic`, `frozen`, `canned`
- [x] Adjust search weights accordingly
- [x] Show filtered category pills at top ("Showing: Fresh Produce") -> *Implemented as Query Word Filter Buttons in UI*

**Complexity**: Low | **Impact**: High

---

## 💡 Additional Next-Level Features

### 6. Shopping List Builder 🛒 ⭐⭐⭐⭐
**What**: Build a cart, see total at each store, find cheapest combo.
**Why**: Users want to optimize their entire grocery trip, not just one item.
**How**:
- [/] Add "Add to List" button on product cards -> *Implemented as "Add to Basket"*
- [ ] Shopping list sidebar/page
- [ ] **Smart feature**: Algorithm to find cheapest store combination
  - e.g., "Buy milk + eggs at Carrefour, rice at Noon = save AED 12"

**Complexity**: Medium-High | **Impact**: Very High (killer feature!)

---

### 8. Price Predictions 📊 ⭐⭐⭐
**What**: Predict if price will go up/down based on historical trends.
**Why**: "This item usually drops 15% next week—wait to buy!"
**How**:
- [ ] Simple: Moving average + seasonal trends
- [ ] Advanced: ML model (scikit-learn linear regression)

**Complexity**: Medium-High | **Impact**: Medium (cool factor!)

---

## 🏆 Recommended Implementation Priority

### Phase 1 (Quick Wins - 1-2 weeks)
1. [x] **Category-based search ranking** (solves your onion problem)
2. [x] **Price trend indicators** (visual polish)

### Phase 2 (Core Features - 2-4 weeks)
4. [/] **Shopping List Builder** (must-have for daily use) -> *Basket exists, needs summary page*
5. [ ] **Scheduled scraping for tracked items**
6. [ ] **Price drop notifications** (email first)

### Phase 3 (Advanced - 1-2 months)
7. [ ] **Price predictions**
8. [ ] **Smart cart optimizer** (find cheapest store combo)
9. [ ] **Shared lists**
