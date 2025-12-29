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
        // Add filter buttons only for Other Matches
        if (isOtherMatches) {
            section += `<div class="mb-4 pt-2 border-b border-gray-100 pb-4"><h2 class="text-2xl font-bold text-text-primary mb-4">${title}</h2>`;
            // Generate buttons from query
            const query = document.getElementById('searchInput').value.trim();
            if (query) {
                const words = query.split(/\s+/).filter(w => w.length > 0); // All words filter
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
            section += '</div>'; // Close header/filter section
            section += '<div id="otherMatchesContainer">'; // Container for filtered rows
        } else {
            if (title) section += `<div class="mb-4"><h2 class="text-2xl font-bold text-text-primary">${title}</h2></div>`;
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
        section += '<div class="space-y-6">';
        displayProducts.forEach(p => {
            const stores = p.stores || {};
            const prices = [];
            ['carrefour', 'noon', 'amazon', 'talabat'].forEach(s => {
                const info = stores[s];
                if (info && typeof info.price === 'number') {
                    prices.push({ store: s, price: info.price });
                }
            });
            const hasPrices = prices.length > 0;
            const minPrice = hasPrices ? Math.min(...prices.map(x => x.price)) : null;
            const bestStores = hasPrices ? prices.filter(x => x.price === minPrice).map(x => x.store) : [];

            // Calculate quantities for display
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

            // Main Card Container (Flex Row)
            section += '<div class="flex flex-col md:flex-row items-stretch border border-gray-200 rounded-xl bg-white shadow-sm overflow-hidden hover:shadow-md transition-shadow group">';

            // 1. LEFT COLUMN: Image - Smaller
            section += '<div class="w-full md:w-32 bg-gray-50 flex items-center justify-center p-2 border-b md:border-b-0 md:border-r border-gray-100">';
            if (p.primary_image) {
                section += `<img src="${escapeHtml(p.primary_image)}" class="w-28 h-28 object-contain mix-blend-multiply" alt="img" onerror="this.style.display='none'">`;
            } else {
                section += '<div class="w-24 h-24 flex items-center justify-center text-gray-300"><svg class="w-12 h-12" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"></path></svg></div>';
            }
            section += '</div>';

            // 2. MIDDLE COLUMN: Info & Store Cards - Compact
            section += '<div class="flex-1 p-2 flex flex-col justify-between">';

            // Top: Header
            section += '<div class="mb-2">';
            section += `<h3 class="font-bold text-gray-900 text-lg mb-0.5 leading-tight line-clamp-1">${escapeHtml(p.matched_name || '')}</h3>`;
            if (qtyText) {
                section += `<span class="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">${escapeHtml(qtyText)}</span>`;
            }
            section += '</div>';

            // Bottom: Store Cards Grid
            section += '<div class="grid grid-cols-1 md:grid-cols-4 gap-4">';

            const storeConfigs = {
                carrefour: { name: 'Carrefour', logo: '/static/logos/carrefour.png', color: 'blue', initial: 'C' },
                noon: { name: 'Noon', logo: '/static/logos/noon.png', color: 'gray', initial: 'N' },
                amazon: { name: 'Amazon', logo: '/static/logos/amazon.png', color: 'orange', initial: 'A' },
                talabat: { name: 'Talabat', logo: '/static/logos/talabat.png', color: 'orange', initial: 'T' }
            };

            ['amazon', 'carrefour', 'noon', 'talabat'].forEach(store => {
                const info = stores[store];
                const config = storeConfigs[store];
                const isBest = bestStores.includes(store);

                if (info && typeof info.price === 'number') {
                    // Active Store Card
                    section += `<div class="relative border ${isBest ? 'border-green-500 bg-green-50/30' : 'border-gray-200 bg-white'} rounded-lg p-2 transition-all duration-200 hover:scale-105 hover:shadow-lg cursor-default">`;

                    // Best Deal Badge (Small, inside card)
                    if (isBest) {
                        section += '<div class="absolute -top-2 -right-2 bg-green-500 text-white text-[10px] font-bold px-2 py-0.5 rounded-full shadow-sm z-10">BEST DEAL</div>';
                    }

                    section += '<div class="flex items-center justify-start mb-1 h-6">';
                    // Logo Only
                    section += `<img src="${escapeHtml(config.logo)}" alt="${config.name}" class="h-5 w-auto object-contain" />`;
                    section += '</div>';

                    // Price
                    section += `<div class="text-base font-bold ${isBest ? 'text-green-700' : 'text-gray-900'}">AED ${info.price.toFixed(2)}</div>`;

                    // View Link
                    if (stores[store].product_url) {
                        section += `<a href="${escapeHtml(stores[store].product_url)}" target="_blank" class="absolute inset-0 z-0"></a>`; // Full card clickable
                    }

                    section += '</div>';

                } else {
                    // Inactive Store Card
                    section += '<div class="border border-gray-100 bg-gray-50/50 rounded-lg p-2 opacity-60 grayscale">';
                    section += '<div class="flex items-center justify-start mb-1 h-6">';
                    section += `<img src="${escapeHtml(config.logo)}" alt="${config.name}" class="h-5 w-auto object-contain opacity-50" />`;
                    section += '</div>';
                    section += '<div class="text-xs text-gray-300 font-medium">Not available</div>';
                    section += '</div>';
                }
            });
            section += '</div>'; // End Store Grid
            section += '</div>'; // End Middle Column

            // 3. RIGHT COLUMN: Best Deal Showcase
            if (minPrice !== null) {
                const bestUnitPrice = baseQty > 0 ? (minPrice / baseQty).toFixed(2) : null;

                section += '<div class="w-full md:w-40 bg-gray-50 border-l border-gray-100 p-3 flex flex-col justify-center">';
                section += '<div class="text-gray-400 text-xs font-medium mb-1 uppercase tracking-wider">Best Deal</div>';
                section += `<div class="text-2xl font-bold text-gray-900 leading-none mb-1">${minPrice.toFixed(2)}</div>`;
                section += '<div class="text-xs text-gray-500 font-medium">AED</div>';

                if (bestUnitPrice) {
                    section += `<div class="mt-2 pt-2 border-t border-gray-200">`;
                    section += `<div class="text-[10px] text-gray-400">Unit Price</div>`;
                    section += `<div class="text-xs font-semibold text-gray-600">${bestUnitPrice} AED/${baseUnit}</div>`;
                    section += `</div>`;
                }

                // Price History Button
                const safeName = (p.matched_name || '').replace(/'/g, "\\'");
                const escapedName = escapeHtml(safeName);
                section += `<button onclick="showPriceHistory('${escapedName}')" class="mt-3 w-full text-xs px-2 py-1.5 bg-white border border-gray-200 rounded-lg hover:bg-gray-50 hover:border-primary transition-colors flex items-center justify-center gap-1">
                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z"/>
                    </svg>
                    Price History
                </button>`;

                section += '</div>';
            } else {
                // Empty state for right column if no prices
                section += '<div class="w-full md:w-40 bg-gray-50 border-l border-gray-100 p-3 flex items-center justify-center text-gray-300 text-xs">No prices</div>';
            }

            section += '</div>'; // Close Main Card
        });

        section += '</div>'; // Close products container wrapper
        if (isOtherMatches) section += '</div>'; // Close otherMatchesContainer
        // Wrap in white container
        section = `<div class="bg-white rounded-2xl shadow-lg p-6 mb-8">${section}</div>`;
        return section;
    };

    // Render Exact Matches
    if (exactMatches.length > 0) {
        html += buildTable(exactMatches, '', false);
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
// Initial Preload Check
async function checkPreloadStatus() {
    try {
        const response = await fetch('/status');
        const status = await response.json();

        Object.keys(status).forEach(store => {
            const state = status[store];
            // Update duration for preloading if needed
            if (store === 'noon') searchProgressState.noon.duration = 10000;
            if (store === 'carrefour') searchProgressState.carrefour.duration = 15000;
            if (store === 'amazon') searchProgressState.amazon.duration = 12000;
            if (store === 'talabat') searchProgressState.talabat.duration = 2000; // Keep fast

            if (state === 'loading' || state === 'not_started') {
                // Start progress
                const label = document.getElementById(`label-${store}`);
                if (label && label.textContent !== 'Preloading...') {
                    label.textContent = 'Preloading...';
                    startSearchProgress(store);
                }
            } else if (state === 'ready') {
                completeSearchProgress(store, false);
            } else if (state === 'error') {
                completeSearchProgress(store, true);
            }
        });

        const stillLoading = Object.values(status).some(s => s === 'loading' || s === 'not_started');
        if (stillLoading) {
            setTimeout(checkPreloadStatus, 500);
        } else {
            // Reset durations for search phase after preloading is done
            searchProgressState.noon.duration = 7000;
            searchProgressState.carrefour.duration = 15000;
            searchProgressState.amazon.duration = 12000;
        }
    } catch (error) {
        console.error('Error checking preload status:', error);
    }
}

window.addEventListener('DOMContentLoaded', checkPreloadStatus);

let searchStatusInterval = null;

const searchProgressState = {
    carrefour: { active: false, interval: null, startTime: null, duration: 15000 },
    noon: { active: false, interval: null, startTime: null, duration: 7000 },
    amazon: { active: false, interval: null, startTime: null, duration: 12000 },
    talabat: { active: false, interval: null, startTime: null, duration: 2000 }
};

function startSearchProgress(store) {
    if (searchProgressState[store].active) return;

    // Reset UI
    const progressElem = document.getElementById(`progress-${store}`);
    const labelElem = document.getElementById(`label-${store}`);
    if (progressElem) progressElem.style.width = '0%';
    if (labelElem) labelElem.textContent = 'Searching...';

    // Start Animation
    searchProgressState[store].active = true;
    searchProgressState[store].startTime = Date.now();

    clearInterval(searchProgressState[store].interval);
    searchProgressState[store].interval = setInterval(() => {
        const state = searchProgressState[store];
        const elapsed = Date.now() - state.startTime;
        const targetDuration = state.duration - 1000; // Reach 90% 1s before end

        let percent = (elapsed / targetDuration) * 90;

        if (percent > 90) percent = 90; // Hold at 90%
        if (percent < 0) percent = 0;

        const el = document.getElementById(`progress-${store}`);
        if (el) el.style.width = `${percent}%`;

    }, 100);
}

function completeSearchProgress(store, isError = false) {
    const state = searchProgressState[store];
    clearInterval(state.interval);
    state.active = false;

    const progressElem = document.getElementById(`progress-${store}`);
    const labelElem = document.getElementById(`label-${store}`);
    const cardElem = document.getElementById(`card-${store}`);

    if (isError) {
        if (progressElem) progressElem.style.width = '100%';
        if (progressElem) progressElem.classList.add('bg-red-500');
        if (labelElem) {
            labelElem.textContent = 'Error';
            labelElem.classList.add('text-red-500');
        }
    } else {
        if (progressElem) progressElem.style.width = '100%';
        if (progressElem) progressElem.classList.add('bg-green-500');
        if (labelElem) {
            labelElem.textContent = 'Ready';
            labelElem.classList.add('text-green-600', 'font-bold');
        }
        if (cardElem) cardElem.classList.add('ring-2', 'ring-green-500', 'ring-offset-2');
    }
}

function updateSearchStatusUI(status) {
    Object.keys(status).forEach(store => {
        const state = status[store];

        if (state === 'searching') {
            startSearchProgress(store);
        } else if (state === 'complete' || state === 'ready') {
            completeSearchProgress(store, false);
        } else if (state === 'error') {
            completeSearchProgress(store, true);
        } else if (state === 'loading') {
            // Preload state - maybe just partial bar?
            const label = document.getElementById(`label-${store}`);
            if (label) label.textContent = 'Preloading...';
        }
    });

    // Clean up if all complete
    const allDone = Object.values(status).every(s => s === 'complete' || s === 'ready' || s === 'error');
    if (allDone && searchStatusInterval) {
        clearInterval(searchStatusInterval);
        searchStatusInterval = null;
    }
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
        if (locations.amazon) {
            parts.push(`Amazon: ${locations.amazon}`);
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
        { name: 'Amazon', key: 'amazon', className: 'amazon' },
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


// ==================== PRICE HISTORY MODAL ====================

let priceHistoryChart = null;

function showPriceHistory(productName) {
    const modal = document.getElementById('priceHistoryModal');
    const loading = document.getElementById('priceHistoryLoading');
    const content = document.getElementById('priceHistoryContent');
    const noData = document.getElementById('priceHistoryNoData');
    const title = document.getElementById('priceHistoryTitle');

    // Show modal with loading state
    modal.classList.remove('hidden');
    loading.classList.remove('hidden');
    content.classList.add('hidden');
    noData.classList.add('hidden');
    title.textContent = productName;

    // Destroy existing chart if any
    if (priceHistoryChart) {
        priceHistoryChart.destroy();
        priceHistoryChart = null;
    }

    // Fetch price history
    fetch(`/api/analytics/price-history-by-name?name=${encodeURIComponent(productName)}&days=30`)
        .then(response => response.json())
        .then(data => {
            loading.classList.add('hidden');
            content.classList.remove('hidden');

            if (!data.history || data.history.length === 0) {
                noData.classList.remove('hidden');
                document.getElementById('priceHistoryChart').style.display = 'none';
                return;
            }

            document.getElementById('priceHistoryChart').style.display = 'block';
            noData.classList.add('hidden');
            renderPriceHistoryChart(data.history);
        })
        .catch(error => {
            console.error('Error fetching price history:', error);
            loading.classList.add('hidden');
            content.classList.remove('hidden');
            noData.classList.remove('hidden');
        });
}

function closePriceHistoryModal() {
    const modal = document.getElementById('priceHistoryModal');
    modal.classList.add('hidden');

    if (priceHistoryChart) {
        priceHistoryChart.destroy();
        priceHistoryChart = null;
    }
}

function renderPriceHistoryChart(history) {
    // Group by store and date
    const storeData = {};
    const allDates = new Set();

    history.forEach(item => {
        const store = item.store_name;
        const date = item.effective_date;

        if (!storeData[store]) {
            storeData[store] = {};
        }
        storeData[store][date] = item.price;
        allDates.add(date);
    });

    // Sort dates
    const sortedDates = Array.from(allDates).sort();

    // Store colors
    const storeColors = {
        carrefour: { bg: 'rgba(59, 130, 246, 0.1)', border: 'rgb(59, 130, 246)' },
        noon: { bg: 'rgba(17, 24, 39, 0.1)', border: 'rgb(17, 24, 39)' },
        amazon: { bg: 'rgba(255, 153, 0, 0.1)', border: 'rgb(255, 153, 0)' },
        talabat: { bg: 'rgba(255, 90, 0, 0.1)', border: 'rgb(255, 90, 0)' }
    };

    // Build datasets
    const datasets = Object.keys(storeData).map(store => {
        const colors = storeColors[store] || { bg: 'rgba(156, 163, 175, 0.1)', border: 'rgb(156, 163, 175)' };
        return {
            label: store.charAt(0).toUpperCase() + store.slice(1),
            data: sortedDates.map(date => storeData[store][date] || null),
            borderColor: colors.border,
            backgroundColor: colors.bg,
            tension: 0.3,
            fill: false,
            spanGaps: true,
            pointRadius: 4,
            pointHoverRadius: 6
        };
    });

    // Format dates for display
    const labels = sortedDates.map(date => {
        const d = new Date(date);
        return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short' });
    });

    const ctx = document.getElementById('priceHistoryChart').getContext('2d');
    priceHistoryChart = new Chart(ctx, {
        type: 'line',
        data: { labels, datasets },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            interaction: {
                intersect: false,
                mode: 'index'
            },
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        usePointStyle: true,
                        padding: 20
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function (context) {
                            return `${context.dataset.label}: AED ${context.parsed.y?.toFixed(2) || 'N/A'}`;
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: false,
                    ticks: {
                        callback: function (value) {
                            return 'AED ' + value.toFixed(2);
                        }
                    }
                }
            }
        }
    });
}

// URL Parameter Search Handling
document.addEventListener('DOMContentLoaded', () => {
    const urlParams = new URLSearchParams(window.location.search);
    const query = urlParams.get('q');
    if (query) {
        const input = document.getElementById('searchInput');
        if (input) {
            input.value = query;
            searchGrocery();
        }
    }
});

// Close modal on escape key
document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
        closePriceHistoryModal();
    }
});

// Close modal on backdrop click
document.getElementById('priceHistoryModal')?.addEventListener('click', function (e) {
    if (e.target === this) {
        closePriceHistoryModal();
    }
});