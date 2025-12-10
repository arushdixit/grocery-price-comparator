// ... existing script ...

function toggleRawResults() {
    const section = document.getElementById('rawSection');
    const btn = document.getElementById('toggleRawBtn');

    if (section.classList.contains('visible')) {
        section.classList.remove('visible');
        btn.textContent = 'Show Raw Results Sidebar ➡️';
    } else {
        section.classList.add('visible');
        btn.textContent = 'Hide Sidebar ⬅️';
    }
}

// Filter Logic
let activeFilterWord = null;
let cachedOtherMatches = [];

function filterMatches(word, btnElement) {
    if (activeFilterWord === word) {
        // Toggle off
        activeFilterWord = null;
        if (btnElement) btnElement.classList.remove('active');
    } else {
        // Toggle on
        activeFilterWord = word;
        // Update active class
        document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
        if (btnElement) btnElement.classList.add('active');
    }

    renderOtherMatchesTable();
}

function renderOtherMatchesTable() {
    const container = document.getElementById('otherMatchesContainer');
    if (!container) return; // Should exist if strict matches exist

    // Filter
    let filtered = cachedOtherMatches;
    if (activeFilterWord) {
        const term = activeFilterWord.toLowerCase();
        filtered = cachedOtherMatches.filter(p => {
            const name = (p.matched_name || '').toLowerCase();
            return name.includes(term);
        });
    }

    // Re-render the 'Other Matches' section with filtered results
    // This requires re-calling buildTable for the 'Other Matches' part
    // We need the original matchedProducts and locations to do this properly
    // For simplicity, I will re-implement strict/other split inside renderMatchedProducts properly.
    // The current structure of renderMatchedProducts will handle this by re-rendering the whole section.
    // So, we just need to call renderMatchedProducts again with the cached data.
    renderMatchedProducts(
        [...document.getElementById('matchedResults')._exactMatches, ...cachedOtherMatches], // Reconstruct full list
        document.getElementById('matchedResults')._locations // Use cached locations
    );
}

function renderMatchedProducts(matchedProducts, locations) {
    const container = document.getElementById('matchedResults');

    // Cache for re-rendering during filtering
    container._exactMatches = matchedProducts.filter(p => p.match_type === 'exact');
    container._locations = locations;

    if (!matchedProducts || matchedProducts.length === 0) {
        container.innerHTML = '<div class="no-matches">No exact SKU matches across stores yet. Try a more specific query like "bayara moong dal 1kg".</div>';
        return;
    }

    // Split into Exact Match and Other Match
    const exactMatches = matchedProducts.filter(p => p.match_type === 'exact');
    const otherMatches = matchedProducts.filter(p => p.match_type !== 'exact');

    // Store for filtering
    cachedOtherMatches = otherMatches;

    let html = '';

    // --- Helper to build table ---
    const buildTable = (products, title, isOtherMatches = false) => {
        if (products.length === 0 && !isOtherMatches) return ''; // Skip empty strict

        let section = '';

        // Add filter buttons only for Other Matches
        if (isOtherMatches) {
            section += `<div class="section-header" style="margin-top: 24px;"><div class="section-title">${title}</div></div>`;

            // Generate buttons from query
            const query = document.getElementById('searchInput').value.trim();
            if (query) {
                const words = query.split(/\s+/).filter(w => w.length > 2); // Only words > 2 chars
                if (words.length > 0) {
                    section += `<div class="filter-container"><span class="filter-label">Filter matches by:</span><div class="filter-buttons">`;
                    words.forEach(word => {
                        // Check if this word is active
                        const isActive = activeFilterWord === word ? 'active' : '';
                        section += `<button class="filter-btn ${isActive}" onclick="filterMatches('${escapeHtml(word)}', this)">${escapeHtml(word)}</button>`;
                    });
                    section += `</div></div>`;
                }
            }

            section += '<div id="otherMatchesContainer">'; // Container for filtered rows
        } else {
            section += `<div class="section-header"><div class="section-title">${title}</div></div>`;
        }

        // If filtering is active for "other matches", use filtered list
        let displayProducts = products;
        if (isOtherMatches && activeFilterWord) {
            const term = activeFilterWord.toLowerCase();
            displayProducts = products.filter(p => (p.matched_name || '').toLowerCase().includes(term));
        }

        if (displayProducts.length === 0) {
            if (isOtherMatches) return section + '<div class="no-matches">No matches containing "' + escapeHtml(activeFilterWord) + '"</div></div>';
            return '';
        }

        section += '<div class="comparison-table-wrapper"><table class="comparison-table">';
        section += '<thead><tr>' +
            '<th>Product</th>' +
            '<th>Quantity</th>' +
            '<th style="text-align: center;"><div style="display: flex; flex-direction: column; align-items: center; gap: 4px;"><img src="/static/logos/carrefour.png" alt="Carrefour" style="height: 24px; vertical-align: middle;"><span>Carrefour</span></div></th>' +
            '<th style="text-align: center;"><div style="display: flex; flex-direction: column; align-items: center; gap: 4px;"><img src="/static/logos/noon.png" alt="Noon" style="height: 24px; vertical-align: middle;"><span>Noon</span></div></th>' +
            '<th style="text-align: center;"><div style="display: flex; flex-direction: column; align-items: center; gap: 4px;"><img src="/static/logos/talabat.png" alt="Talabat" style="height: 24px; vertical-align: middle;"><span>Talabat</span></div></th>' +
            '<th>Best price</th>' +
            '</tr></thead><tbody>';

        displayProducts.forEach(p => {
            const stores = p.stores || {};
            const prices = [];
            ['carrefour', 'noon', 'talabat'].forEach(s => {
                const info = stores[s];
                if (info && typeof info.price === 'number') {
                    prices.push({ store: s, price: info.price });
                }
            });

            const hasPrices = prices.length > 0;
            const minPrice = hasPrices ? Math.min(...prices.map(x => x.price)) : null;
            const bestStores = hasPrices ? prices.filter(x => x.price === minPrice).map(x => x.store) : [];

            section += '<tr>';

            // Product name
            section += `<td class="product-name-cell">${escapeHtml(p.matched_name || '')}</td>`;

            // Quantity
            let qtyText = '';
            let baseQty = 0;
            let baseUnit = '';

            if (p.quantity_value && p.quantity_unit) {
                // Normalize for display
                let dispVal = p.quantity_value;
                let dispUnit = p.quantity_unit.toUpperCase(); // KG, G, L, ML, PACK, M

                // User Request: "only use L, KG, and M", "1L, 1000ml... make it consistent"
                // Logic: 
                // 1. If >= 1000 G -> KG
                // 2. If >= 1000 ML -> L
                // 3. Ensure L/KG/ML/G/PACK/M are capitalized.

                if (dispUnit === 'G' && dispVal >= 1000) {
                    dispVal = dispVal / 1000;
                    dispUnit = 'KG';
                } else if (dispUnit === 'ML') {
                    if (dispVal >= 1000) {
                        dispVal = dispVal / 1000;
                        dispUnit = 'L';
                    }
                    // If user meant 'M' strictly instead of 'ML', replace here.
                    // "L, KG, and M". Assuming M means ML from context of similar size. 
                    // But standard is ML. I'll stick to 'ML' for clarity unless 'M' is forced.
                    // Wait, user said "only use L, KG, and M".
                    // If I use 'ML', is checking user request "L, KG, and M".
                    // Maybe "M" stands for "Milliliters"? Or "Meters"? 
                    // Context "L, KG, M". I'll use "ML" because "M" is ambiguous (Meter?). 
                    // But I will respect capitalization.
                } else if (dispUnit === 'L' || dispUnit === 'LITER' || dispUnit === 'LITRE') {
                    dispUnit = 'L';
                }

                qtyText = `${parseFloat(dispVal.toFixed(2))} ${dispUnit}`;

                // Base calc for unit price
                const u = p.quantity_unit.toLowerCase();
                if (u === 'g' || u === 'gram' || u === 'grams') {
                    baseQty = p.quantity_value / 1000;
                    baseUnit = 'kg';
                } else if (u === 'ml' || u === 'm') {
                    baseQty = p.quantity_value / 1000;
                    baseUnit = 'L';
                } else if (u === 'kg' || u === 'kilogram') {
                    baseQty = p.quantity_value;
                    baseUnit = 'kg';
                } else if (u === 'l' || u === 'liter' || u === 'litre') {
                    baseQty = p.quantity_value;
                    baseUnit = 'L';
                } else if (u === 'pack') {
                    baseQty = p.quantity_value;
                    baseUnit = 'pack';
                }
            }
            section += `<td>${qtyText ? `<span class="quantity-badge">${escapeHtml(qtyText)}</span>` : '<span class="muted">n/a</span>'}</td>`;



            // Store price cells
            ['carrefour', 'noon', 'talabat'].forEach(store => {
                const info = stores[store];
                if (info && typeof info.price === 'number') {
                    const isBest = bestStores.includes(store);
                    let unitPrice = '';
                    if (baseQty > 0) {
                        unitPrice = `(AED ${(info.price / baseQty).toFixed(2)} / ${baseUnit})`;
                    }

                    section += `<td class="price-cell${isBest ? ' best-price' : ''}">` +
                        `<div class="price-value">AED ${info.price.toFixed(2)}</div>` +
                        (unitPrice ? `<div class="unit-price-footnote">${unitPrice}</div>` : '') +
                        '</td>';
                } else {
                    section += '<td class="price-cell muted">—</td>';
                }
            });

            // Best price summary
            if (hasPrices) {
                const bestStoreNames = bestStores.map(s => s.charAt(0).toUpperCase() + s.slice(1));

                let bestUnitPrice = '';
                if (baseQty > 0) {
                    bestUnitPrice = `(AED ${(minPrice / baseQty).toFixed(2)} / ${baseUnit})`;
                }

                section += '<td class="price-cell">' +
                    `<div class="price-value">AED ${minPrice.toFixed(2)}</div>` +
                    (bestUnitPrice ? `<div class="unit-price-footnote">${bestUnitPrice}</div>` : '') +
                    '</td>';
            } else {
                section += '<td class="price-cell muted">n/a</td>';
            }

            section += '</tr>';
        });
        section += '</tbody></table></div>';

        if (isOtherMatches) section += '</div>'; // Close otherMatchesContainer
        return section;
    };

    // Render Exact Matches
    if (exactMatches.length > 0) {
        html += buildTable(exactMatches, 'Exact Product Match Found', false);
    }

    // Render Other Matches
    if (otherMatches.length > 0) {
        html += buildTable(otherMatches, 'Other Matches', true);
    } else if (exactMatches.length > 0) {
        // No other matches, but exact matches exist, so no need for a "no matches" message for the whole section
    }

    if (!html) {
        container.innerHTML = '<div class="no-matches">No matches found after filtering.</div>';
    } else {
        container.innerHTML = html;
    }
}


// ---------- Status polling ----------
async function checkPreloadStatus() {
    try {
        const response = await fetch('/status');
        const status = await response.json();

        Object.keys(status).forEach(store => {
            const statusElem = document.getElementById(`status-${store}`);
            if (!statusElem) return;

            const state = status[store];
            statusElem.className = 'store-status';

            if (state === 'loading' || state === 'not_started') {
                statusElem.className += ' status-loading';
                statusElem.innerHTML = `<div class="spinner"></div><span>${store.charAt(0).toUpperCase() + store.slice(1)}: Loading...</span>`;
            } else if (state === 'ready') {
                statusElem.className += ' status-ready';
                statusElem.innerHTML = `<span>✓ ${store.charAt(0).toUpperCase() + store.slice(1)}: Ready</span>`;
            } else if (state === 'error') {
                statusElem.className += ' status-error';
                statusElem.innerHTML = `<span>✗ ${store.charAt(0).toUpperCase() + store.slice(1)}: Error</span>`;
            }
        });

        const stillLoading = Object.values(status).some(s => s === 'loading' || s === 'not_started');
        if (stillLoading) {
            setTimeout(checkPreloadStatus, 600);
        }
    } catch (error) {
        console.error('Error checking preload status:', error);
    }
}

window.addEventListener('DOMContentLoaded', checkPreloadStatus);

let searchStatusInterval = null;

function updateSearchStatusUI(status) {
    Object.keys(status).forEach(store => {
        const statusElem = document.getElementById(`status-${store}`);
        if (!statusElem) return;

        const state = status[store];
        statusElem.className = 'store-status';

        if (state === 'searching') {
            statusElem.className += ' status-loading';
            statusElem.innerHTML = `<div class="spinner"></div><span>${store.charAt(0).toUpperCase() + store.slice(1)}: Searching...</span>`;
        } else if (state === 'complete' || state === 'ready') {
            statusElem.className += ' status-ready';
            statusElem.innerHTML = `<span>✓ ${store.charAt(0).toUpperCase() + store.slice(1)}: Ready</span>`;
        }
    });
}

async function pollSearchStatus() {
    try {
        const response = await fetch('/search-status');
        const status = await response.json();
        updateSearchStatusUI(status);
    } catch (error) {
        console.error('Error polling search status:', error);
    }
}

// Store raw results globally for matching
let currentRawResults = null;

// ---------- Search & display ----------
async function searchGrocery() {
    const input = document.getElementById('searchInput');
    const searchBtn = document.getElementById('searchBtn');
    const loading = document.getElementById('loading');
    const errorDiv = document.getElementById('error');
    const matchedResults = document.getElementById('matchedResults');
    const rawResults = document.getElementById('rawResults');
    const mainColumn = document.getElementById('mainColumn');

    const item = input.value.trim();
    if (!item) {
        errorDiv.innerHTML = '<div class="error">Please enter an item to search.</div>';
        return;
    }

    errorDiv.innerHTML = '';
    matchedResults.innerHTML = '';
    rawResults.innerHTML = '';

    // Reset UI state
    mainColumn.style.display = 'none';
    document.getElementById('toggleRawBtn').style.display = 'none';

    loading.style.display = 'block';
    searchBtn.disabled = true;

    searchStatusInterval = setInterval(pollSearchStatus, 400);

    try {
        const response = await fetch('/search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ item })
        });

        if (!response.ok) {
            const data = await response.json().catch(() => ({}));
            throw new Error(data.error || 'Search failed');
        }

        const data = await response.json();
        currentRawResults = data;
        renderRawResults(data.raw_results || data);

        // Show location note
        const locations = data.locations || {};
        const locationNote = document.getElementById('locationNote');
        const parts = [];
        if (locations.carrefour) {
            parts.push(`Carrefour: ${locations.carrefour}`);
        }
        if (locations.noon) {
            parts.push(`Noon: ${locations.noon}`);
        }
        locationNote.textContent = parts.length ? `Search locations · ${parts.join(' · ')}` : '';

        locationNote.textContent = parts.length ? `Search locations · ${parts.join(' · ')}` : '';

        // Hide Match button, trigger automatically
        // matchBtn.style.display = 'block';
        await matchProducts();

        // Show toggle raw results button
        document.getElementById('toggleRawBtn').style.display = 'inline-flex';

    } catch (error) {
        console.error(error);
        errorDiv.innerHTML = '<div class="error">Error: ' + (error.message || 'Something went wrong') + '</div>';
    } finally {
        loading.style.display = 'none';
        searchBtn.disabled = false;
        if (searchStatusInterval) {
            clearInterval(searchStatusInterval);
            searchStatusInterval = null;
        }
        await pollSearchStatus();
    }
}

async function matchProducts() {
    // const matchBtn = document.getElementById('matchBtn');
    const matchingLoading = document.getElementById('matchingLoading');
    const errorDiv = document.getElementById('error');
    const matchedResults = document.getElementById('matchedResults');

    if (!currentRawResults) {
        errorDiv.innerHTML = '<div class="error">No search results to match.</div>';
        return;
    }

    // Parse sort options
    const sortValue = document.getElementById('sortOptions').value;
    let sortBy = 'price';
    let sortOrder = 'asc';

    if (sortValue === 'price_desc') { sortBy = 'price'; sortOrder = 'desc'; }
    else if (sortValue === 'name_asc') { sortBy = 'name'; sortOrder = 'asc'; }
    else if (sortValue === 'name_desc') { sortBy = 'name'; sortOrder = 'desc'; }

    matchingLoading.style.display = 'block';
    matchedResults.innerHTML = '';

    // Show main column
    document.getElementById('mainColumn').style.display = 'block';

    // Ensure raw results are hidden during matching to focus on results
    document.getElementById('rawSection').classList.remove('visible');
    document.getElementById('toggleRawBtn').textContent = 'Show Raw Results Sidebar ➡️';

    try {
        const response = await fetch('/match', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                raw_results: currentRawResults.raw_results,
                sort_by: sortBy,
                sort_order: sortOrder,
                product_name: document.getElementById('searchInput').value.trim()
            })
        })

        if (!response.ok) {
            const data = await response.json().catch(() => ({}));
            throw new Error(data.error || 'Matching failed');
        }

        const data = await response.json();
        renderMatchedProducts(data.matched_products || [], currentRawResults.locations || {});
        // matchedSection.style.display = 'block'; // Removed as element doesn't exist
    } catch (error) {
        console.error(error);
        errorDiv.innerHTML = '<div class="error">Error matching products: ' + (error.message || 'Something went wrong') + '</div>';
    } finally {
        matchingLoading.style.display = 'none';
    }
}





function renderRawResults(rawData) {
    const results = document.getElementById('rawResults');
    results.innerHTML = '';

    const stores = [
        { name: 'Carrefour', key: 'carrefour', className: 'carrefour' },
        { name: 'Noon', key: 'noon', className: 'noon' },
        { name: 'Talabat', key: 'talabat', className: 'talabat' }
    ];

    stores.forEach(store => {
        const storeData = rawData[store.key] || {};
        const products = Array.isArray(storeData.products) ? storeData.products : (Array.isArray(storeData) ? storeData : []);
        const location = storeData.location;

        const card = document.createElement('div');
        card.className = `store-card ${store.className}`;

        let locationHTML = '';
        if (location) {
            locationHTML = `<div class="store-location">📍 ${escapeHtml(location)}</div>`;
        }

        let productsHTML = '';
        if (!products || products.length === 0) {
            productsHTML = '<div class="no-results">No results found</div>';
        } else {
            products.forEach(product => {
                productsHTML += `
                            <div class="product-row" style="display: flex; justify-content: space-between; align-items: baseline; gap: 8px;">
                                <div class="product-row-name" style="flex: 1;">${highlightQueryMatch(product.name || '')}</div>
                                <div class="product-row-price" style="white-space: nowrap; font-weight: 600;">${escapeHtml(product.price || '')}</div>
                            </div>
                        `;
            });
        }

        card.innerHTML = `
                    <div class="store-header">
                        ${store.name}
                        ${locationHTML}
                    </div>
                    ${productsHTML}
                `;

        results.appendChild(card);
    });
}

function highlightQueryMatch(text) {
    const query = document.getElementById('searchInput').value.trim();
    if (!query) return escapeHtml(text);

    // Escape HTML in text first to be safe, then apply highlighting
    let safeText = escapeHtml(text);

    // Simple split by space to get words
    const words = query.split(/\s+/).filter(w => w.length > 1);

    words.forEach(word => {
        // Case insensitive replacement avoiding HTML tags
        // For strict matching: only highlight if the text contains ALL words.
        // But highlighting is about visual feedback.
        // User request: "highlight all the entries that have both the words... highlight only 'masur' or only 'dal' [in those entries]"
        // But this function processes TEXT, not the entry filtering.
        // The filtering happens elsewhere? No, this is just for display.
        // User wants: only highlight words IF the whole query is present in this text?
        // "if the query is 'masur dal,' then highlight all the entries that have both the words 'masur dal.' Highlight only 'masur' or only 'dal.'"
        // This likely means: If the text contains both "masur" and "dal", highlight both. If it only contains "masur", highlight NOTHING (implied).

        // Check if text contains ALL words from query
        const textLower = safeText.toLowerCase();
        const allPresent = words.every(w => textLower.includes(w.toLowerCase()));

        if (allPresent) {
            const regex = new RegExp(`(${word})`, 'gi');
            safeText = safeText.replace(regex, '<mark>$1</mark>');
        }
    });

    return safeText;
}


function escapeHtml(str) {
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}
