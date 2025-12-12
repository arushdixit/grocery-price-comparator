function toggleRawResults() {
    const section = document.getElementById('rawSection');
    const btn = document.getElementById('toggleRawBtn');

    if (section.classList.contains('hidden')) {
        section.classList.remove('hidden');
        btn.textContent = 'Hide Sidebar ⬅️';
    } else {
        section.classList.add('hidden');
        btn.textContent = 'Show Raw Results Sidebar ➡️';
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
        container.innerHTML = '<div class="text-center text-text-muted py-8">No exact SKU matches across stores yet. Try a more specific query like "bayara moong dal 1kg".</div>';
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
            section += `<div class="mt-6 mb-4"><h3 class="text-xl font-bold text-text-primary">${title}</h3></div>`;
            // Generate buttons from query
            const query = document.getElementById('searchInput').value.trim();
            if (query) {
                const words = query.split(/\\s+/).filter(w => w.length > 2); // Only words > 2 chars
                if (words.length > 0) {
                    section += `<div class="flex flex-wrap items-center gap-2 mb-4"><span class="text-sm text-text-muted font-medium">Filter matches by:</span><div class="flex flex-wrap gap-2">`;
                    words.forEach(word => {
                        // Check if this word is active
                        const isActive = activeFilterWord === word ? 'active' : '';
                        section += `<button class="px-3 py-1 text-sm rounded-full border transition-all ${isActive ? 'bg-primary text-white border-primary' : 'bg-white text-text-primary border-border hover:border-primary'}" onclick="filterMatches('${escapeHtml(word)}', this)">${escapeHtml(word)}</button>`;
                    });
                    section += `</div></div>`;
                }
            }
            section += '<div id="otherMatchesContainer">'; // Container for filtered rows
        } else {
            section += `<div class="mb-4"><h3 class="text-xl font-bold text-text-primary">${title}</h3></div>`;
        }
        // If filtering is active for "other matches", use filtered list
        let displayProducts = products;
        if (isOtherMatches && activeFilterWord) {
            const term = activeFilterWord.toLowerCase();
            displayProducts = products.filter(p => (p.matched_name || '').toLowerCase().includes(term));
        }
        if (displayProducts.length === 0) {
            if (isOtherMatches) return section + '<div class="text-center text-text-muted py-8">No matches containing "' + escapeHtml(activeFilterWord) + '"</div></div>';
            return '';
        }
        // Card-based layout
        section += '<div class="space-y-4">';
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
            // Product card
            section += '<div class="border border-gray-200 rounded-lg p-4 hover:shadow-md transition-shadow bg-white">';

            // Product header with image and name
            section += '<div class="flex items-start gap-4 mb-4">';

            // Product image
            let imgHtml = '';
            if (p.primary_image) {
                imgHtml = `<img src="${escapeHtml(p.primary_image)}" class="w-20 h-20 object-contain rounded bg-gray-50 flex-shrink-0" alt="img" onerror="this.style.display='none'">`;
            } else {
                imgHtml = '<div class="w-20 h-20 bg-gray-100 rounded flex items-center justify-center text-gray-400 text-xs flex-shrink-0">No image</div>';
            }
            section += imgHtml;

            // Product info
            section += '<div class="flex-1 min-w-0">';
            section += `<h3 class="font-semibold text-gray-900 text-base mb-2">${escapeHtml(p.matched_name || '')}</h3>`;

            // Quantity
            let qtyText = '';
            let baseQty = 0;
            let baseUnit = '';
            if (p.quantity_value && p.quantity_unit) {
                let dispVal = p.quantity_value;
                let dispUnit = p.quantity_unit.toUpperCase();
                if (dispUnit === 'G' && dispVal >= 1000) {
                    dispVal = dispVal / 1000;
                    dispUnit = 'KG';
                } else if (dispUnit === 'ML' && dispVal >= 1000) {
                    dispVal = dispVal / 1000;
                    dispUnit = 'L';
                } else if (dispUnit === 'L' || dispUnit === 'LITER' || dispUnit === 'LITRE') {
                    dispUnit = 'L';
                }
                qtyText = `${parseFloat(dispVal.toFixed(2))} ${dispUnit}`;
                // Base calc for unit price
                const u = p.quantity_unit.toLowerCase();
                if (u === 'g' || u === 'gram' || u === 'grams') {
                    baseQty = p.quantity_value / 1000;
                    baseUnit = 'kg';
                } else if (u === 'ml') {
                    baseQty = p.quantity_value / 1000;
                    baseUnit = 'L';
                } else if (u === 'kg' || u === 'kilogram') {
                    baseQty = p.quantity_value;
                    baseUnit = 'kg';
                } else if (u === 'l' || u === 'liter' || u === 'litre') {
                    baseQty = p.quantity_value;
                    baseUnit = 'L';
                } else if (['pack', 'packs', 'pcs', 'piece', 'pieces', 'pc'].includes(u)) {
                    baseQty = p.quantity_value;
                    baseUnit = 'pc';
                } else if (u === 'm') {
                    baseQty = p.quantity_value;
                    baseUnit = 'm';
                } else if (u === 'sqft' || u === 'sq ft' || u === 'sq.ft') {
                    baseQty = p.quantity_value;
                    baseUnit = 'sqft';
                }
            }

            if (qtyText) {
                section += `<span class="inline-block bg-gray-100 text-gray-700 rounded-full px-3 py-1 text-sm font-medium">${escapeHtml(qtyText)}</span>`;
            }

            section += '</div></div>'; // Close product info and header

            // Store price cards
            section += '<div class="grid grid-cols-1 md:grid-cols-3 gap-3">';

            // Store configurations
            const storeConfigs = {
                carrefour: { name: 'Carrefour', logo: '/static/logos/carrefour.png', color: 'blue', initial: 'C' },
                noon: { name: 'Noon', logo: '/static/logos/noon.png', color: 'gray', initial: 'N' },
                talabat: { name: 'Talabat', logo: '/static/logos/talabat.png', color: 'orange', initial: 'T' }
            };

            ['carrefour', 'noon', 'talabat'].forEach(store => {
                const info = stores[store];
                const config = storeConfigs[store];
                const isBest = bestStores.includes(store);

                if (info && typeof info.price === 'number') {
                    let unitPrice = '';
                    if (baseQty > 0) {
                        unitPrice = `${(info.price / baseQty).toFixed(4)} AED/${baseUnit}`;
                    }

                    // Best deal gets green border, others get gray
                    const borderClass = isBest ? 'border-2 border-green-500 bg-green-50' : 'border border-gray-200 bg-gray-50';

                    section += `<div class="${borderClass} rounded-lg p-3 relative">`;

                    // Best deal badge
                    if (isBest) {
                        section += '<div class="absolute -top-2 -right-2 bg-green-500 text-white text-xs font-bold px-2 py-1 rounded-full shadow">Best Deal</div>';
                    }

                    // Store logo/initial
                    section += '<div class="flex items-center gap-2 mb-2">';
                    const colorClasses = {
                        blue: 'bg-blue-500',
                        gray: 'bg-gray-800',
                        orange: 'bg-orange-500'
                    };
                    section += `<div class="${colorClasses[config.color]} text-white w-8 h-8 rounded-full flex items-center justify-center font-bold text-sm">${config.initial}</div>`;
                    section += `<span class="font-medium text-gray-700 text-sm">${config.name}</span>`;
                    section += '</div>';

                    // Price
                    section += `<div class="text-xl font-bold ${isBest ? 'text-green-700' : 'text-gray-900'} mb-1">AED ${info.price.toFixed(2)}</div>`;

                    // Unit price
                    if (unitPrice) {
                        section += `<div class="text-xs text-gray-500">${unitPrice}</div>`;
                    }

                    // View link
                    if (stores[store].product_url) {
                        section += `<a href="${escapeHtml(stores[store].product_url)}" target="_blank" class="text-xs text-blue-600 hover:underline mt-2 inline-block">View →</a>`;
                    }

                    section += '</div>';
                } else {
                    // Not available
                    section += `<div class="border border-gray-200 bg-gray-50 rounded-lg p-3 opacity-60">`;
                    section += '<div class="flex items-center gap-2 mb-2">';
                    const colorClasses = {
                        blue: 'bg-blue-500',
                        gray: 'bg-gray-800',
                        orange: 'bg-orange-500'
                    };
                    section += `<div class="${colorClasses[config.color]} text-white w-8 h-8 rounded-full flex items-center justify-center font-bold text-sm opacity-50">${config.initial}</div>`;
                    section += `<span class="font-medium text-gray-400 text-sm">${config.name}</span>`;
                    section += '</div>';
                    section += '<div class="text-sm text-gray-400">Not available</div>';
                    section += '</div>';
                }
            });

            section += '</div>'; // Close store cards grid
            section += '</div>'; // Close product card
        });

        section += '</div>'; // Close products container
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
        container.innerHTML = '<div class="text-center text-text-muted py-8">No matches found after filtering.</div>';
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

            // Store-specific colors
            const storeColors = {
                carrefour: { loading: 'bg-blue-100 text-blue-800', ready: 'bg-blue-100 text-blue-800', spinner: 'border-blue-800' },
                noon: { loading: 'bg-gray-100 text-gray-800', ready: 'bg-gray-100 text-gray-800', spinner: 'border-gray-800' },
                talabat: { loading: 'bg-orange-100 text-orange-800', ready: 'bg-orange-100 text-orange-800', spinner: 'border-orange-800' }
            };
            const colors = storeColors[store] || storeColors.carrefour;

            if (state === 'loading' || state === 'not_started') {
                statusElem.className = `store-status flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium ${colors.loading}`;
                statusElem.innerHTML = `<div class="w-4 h-4 border-2 ${colors.spinner} border-t-transparent rounded-full spinner"></div><span>${store.charAt(0).toUpperCase() + store.slice(1)}: Loading...</span>`;
            } else if (state === 'ready') {
                statusElem.className = `store-status flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium ${colors.ready}`;
                statusElem.innerHTML = `<span>✓ ${store.charAt(0).toUpperCase() + store.slice(1)}: Ready</span>`;
            } else if (state === 'error') {
                statusElem.className = `store-status flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium bg-red-100 text-red-800`;
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

        // Store-specific colors
        const storeColors = {
            carrefour: { loading: 'bg-blue-100 text-blue-800', ready: 'bg-blue-100 text-blue-800', spinner: 'border-blue-800' },
            noon: { loading: 'bg-gray-100 text-gray-800', ready: 'bg-gray-100 text-gray-800', spinner: 'border-gray-800' },
            talabat: { loading: 'bg-orange-100 text-orange-800', ready: 'bg-orange-100 text-orange-800', spinner: 'border-orange-800' }
        };
        const colors = storeColors[store] || storeColors.carrefour;

        if (state === 'searching') {
            statusElem.className = `store-status flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium ${colors.loading}`;
            statusElem.innerHTML = `<div class="w-4 h-4 border-2 ${colors.spinner} border-t-transparent rounded-full spinner"></div><span>${store.charAt(0).toUpperCase() + store.slice(1)}: Searching...</span>`;
        } else if (state === 'complete' || state === 'ready') {
            statusElem.className = `store-status flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium ${colors.ready}`;
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
    document.getElementById('rawSection').classList.add('hidden');
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
        card.className = `bg-white border border-gray-200 rounded-lg shadow p-4 ${store.className}`;

        let locationHTML = '';
        if (location) {
            locationHTML = `<div class="flex items-center text-sm text-gray-500 mt-1"><svg class="h-4 w-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 11c0 .667-.333 2-1 2s-1-1.333-1-2 .333-2 1-2 1 1.333 1 2z"/></svg> ${escapeHtml(location)}</div>`;
        }

        let productsHTML = '';
        if (!products || products.length === 0) {
            productsHTML = `<div class="text-center text-gray-400">No results found</div>`;
        } else {
            products.forEach(product => {
                let imgCode = '';
                if (product.image_url) {
                    imgCode = `<img src="${escapeHtml(product.image_url)}" class="w-10 h-10 object-contain rounded mr-2" alt="product">`;
                }
                let nameCode = highlightQueryMatch(product.name || '');
                if (product.product_url) {
                    nameCode = `<a href="${escapeHtml(product.product_url)}" target="_blank" class="text-primary-600 hover:underline">${nameCode}</a>`;
                }
                productsHTML += `
            <div class="flex justify-between items-center py-2 border-b border-gray-100">
                <div class="flex items-center">${imgCode}<span class="font-medium text-gray-800">${nameCode}</span></div>
                <div class="font-semibold text-gray-900">${escapeHtml(product.price || '')}</div>
            </div>`;
            });
        }

        card.innerHTML = `
    <div class="flex items-center justify-between mb-2">
        <h3 class="text-lg font-semibold text-gray-800">${store.name}</h3>
    </div>
    ${locationHTML}
    <div class="mt-2">${productsHTML}</div>`;

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
