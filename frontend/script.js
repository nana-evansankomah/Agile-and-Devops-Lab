// Dashboard JavaScript

// Auto-refresh every 60 seconds (CoinGecko free tier allows ~10-50 requests/min)
const AUTO_REFRESH_INTERVAL = 60000;
let autoRefreshTimer = null;

// Initialize dashboard on page load
document.addEventListener('DOMContentLoaded', () => {
    console.log('Dashboard initialized');
    refreshData();
    startAutoRefresh();
});

// Refresh button click handler
document.getElementById('refreshBtn').addEventListener('click', refreshData);

/**
 * Refresh data from API
 */
async function refreshData() {
    console.log('Refreshing data...');
    updateStatus('loading', 'Loading...');

    try {
        const response = await fetch('/api/refresh');
        const result = await response.json();

        if (response.ok) {
            updateDashboard(result.data);
            updateStatus('healthy', 'Connected');
            console.log('Data refreshed successfully');
        } else {
            updateStatus('error', 'Error: ' + result.message);
            console.error('API error:', result.message);
        }
    } catch (error) {
        updateStatus('error', 'Connection Error');
        console.error('Fetch error:', error);
    }
}

/**
 * Update dashboard with new data
 */
function updateDashboard(data) {
    if (!data) {
        console.warn('No data to display');
        return;
    }

    // Update stats
    const summary = data.summary || {};
    document.getElementById('totalCount').textContent = summary.total_count || 0;
    document.getElementById('validCount').textContent = summary.valid_count || 0;
    document.getElementById('qualityScore').textContent = (summary.data_quality_score || 0).toFixed(1) + '%';

    // Update timestamp
    const lastUpdate = new Date(data.timestamp);
    const formattedTime = lastUpdate.toLocaleString();
    document.getElementById('lastUpdate').textContent = `Last update: ${formattedTime}`;
    document.getElementById('footerTime').textContent = formattedTime;

    // Update table
    const tableBody = document.getElementById('tableBody');
    tableBody.innerHTML = '';

    if (data.cryptos && data.cryptos.length > 0) {
        data.cryptos.forEach(crypto => {
            const row = createTableRow(crypto);
            tableBody.appendChild(row);
        });
    } else {
        tableBody.innerHTML = '<tr class="empty-row"><td colspan="5">No data available</td></tr>';
    }

    // Fetch and update stats and alerts
    fetchStats();
    fetchAndDisplayAlerts();
}

/**
 * Create table row for cryptocurrency
 */
function createTableRow(crypto) {
    const row = document.createElement('tr');
    
    const priceFormatted = formatCurrency(crypto.price_usd);
    const marketCapFormatted = formatCurrency(crypto.market_cap_usd);
    const volumeFormatted = formatCurrency(crypto.volume_24h_usd);
    const change24h = crypto.change_24h_percent || 0;
    const changeClassName = change24h >= 0 ? 'positive-change' : 'negative-change';
    const changeSymbol = change24h >= 0 ? '↑' : '↓';
    
    row.innerHTML = `
        <td>${crypto.name}</td>
        <td>$${priceFormatted}</td>
        <td>${marketCapFormatted}</td>
        <td>${volumeFormatted}</td>
        <td class="${changeClassName}">${changeSymbol} ${change24h.toFixed(2)}%</td>
    `;
    
    return row;
}

/**
 * Format number as currency
 */
function formatCurrency(value) {
    if (!value) return 'N/A';
    
    if (value >= 1e12) {
        return (value / 1e12).toFixed(2) + 'T';
    } else if (value >= 1e9) {
        return (value / 1e9).toFixed(2) + 'B';
    } else if (value >= 1e6) {
        return (value / 1e6).toFixed(2) + 'M';
    } else if (value >= 1e3) {
        return (value / 1e3).toFixed(2) + 'K';
    } else {
        return value.toFixed(2);
    }
}

/**
 * Update status indicator
 */
function updateStatus(status, message) {
    const statusEl = document.getElementById('status');
    statusEl.className = `status-indicator ${status}`;
    statusEl.title = message;
}

/**
 * Fetch and display quality alerts
 */
async function fetchAndDisplayAlerts() {
    try {
        const response = await fetch('/api/quality/alerts?type=active');
        const result = await response.json();
        
        if (result.alerts && result.alerts.length > 0) {
            displayAlerts(result.alerts);
        } else {
            hideAlerts();
        }
    } catch (error) {
        console.warn('Could not fetch alerts:', error);
        hideAlerts();
    }
}

/**
 * Display quality alerts on dashboard
 */
function displayAlerts(alerts) {
    const alertsSection = document.getElementById('alertsSection');
    const alertsList = document.getElementById('alertsList');
    
    alertsList.innerHTML = '';
    
    alerts.forEach(alert => {
        const alertEl = document.createElement('div');
        alertEl.className = `alert-item ${alert.severity || 'warning'}`;
        
        alertEl.innerHTML = `
            <div class="alert-content">
                <div class="alert-message">${alert.message}</div>
                <div class="alert-meta">
                    <strong>${alert.crypto}</strong> • 
                    <span class="alert-badge ${alert.severity || 'warning'}">${(alert.alert_type || 'unknown').toUpperCase()}</span>
                </div>
            </div>
        `;
        
        alertsList.appendChild(alertEl);
    });
    
    alertsSection.style.display = 'block';
}

/**
 * Hide quality alerts section
 */
function hideAlerts() {
    const alertsSection = document.getElementById('alertsSection');
    alertsSection.style.display = 'none';
}

/**
 * Fetch and update statistics
 */
async function fetchStats() {
    try {
        const response = await fetch('/api/data');
        const result = await response.json();
        
        if (result.stats) {
            document.getElementById('updateCount').textContent = result.stats.update_count || 0;
        }
    } catch (error) {
        console.warn('Could not fetch stats:', error);
    }
}

/**
 * Start auto-refresh timer
 */
function startAutoRefresh() {
    if (autoRefreshTimer) {
        clearInterval(autoRefreshTimer);
    }
    
    autoRefreshTimer = setInterval(refreshData, AUTO_REFRESH_INTERVAL);
    console.log(`Auto-refresh started (every ${AUTO_REFRESH_INTERVAL / 1000}s)`);
}

/**
 * Stop auto-refresh timer
 */
function stopAutoRefresh() {
    if (autoRefreshTimer) {
        clearInterval(autoRefreshTimer);
        console.log('Auto-refresh stopped');
    }
}

// Cleanup on page unload
window.addEventListener('beforeunload', stopAutoRefresh);
