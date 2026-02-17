// Enhanced Dashboard with Tabs and Charts

const AUTO_REFRESH_INTERVAL = 60000;
let autoRefreshTimer = null;
let charts = {};

// Initialize dashboard on page load
document.addEventListener('DOMContentLoaded', () => {
    console.log('Dashboard initialized');
    setupTabNavigation();
    refreshData();
    startAutoRefresh();
});

// Setup tab navigation
function setupTabNavigation() {
    const tabButtons = document.querySelectorAll('.tab-btn');
    const tabContents = document.querySelectorAll('.tab-content');

    tabButtons.forEach(button => {
        button.addEventListener('click', () => {
            const tabName = button.getAttribute('data-tab');
            
            // Deactivate all tabs and contents
            tabButtons.forEach(btn => btn.classList.remove('active'));
            tabContents.forEach(content => content.classList.remove('active'));
            
            // Activate selected tab
            button.classList.add('active');
            document.getElementById(tabName).classList.add('active');
            
            // Refresh charts if dashboard tab opened
            if (tabName === 'dashboard') {
                setTimeout(() => {
                    Object.values(charts).forEach(chart => {
                        if (chart) chart.resize();
                    });
                }, 100);
            }
        });
    });
}

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
        
        // Update charts with new data
        updateCharts(data.cryptos);
    } else {
        tableBody.innerHTML = '<tr class="empty-row"><td colspan="5">No data available</td></tr>';
    }

    // Fetch and update stats and quality data
    fetchStats();
    fetchAndDisplayAlerts();
    fetchAndDisplayQualityMetrics();
}

/**
 * Update charts with new data
 */
function updateCharts(cryptos) {
    if (!cryptos || cryptos.length === 0) return;

    // Price Chart
    updatePriceChart(cryptos);
    
    // Market Cap Chart
    updateMarketCapChart(cryptos);
    
    // Change Chart
    updateChangeChart(cryptos);
    
    // Quality Trend Chart
    updateQualityTrendChart();
}

/**
 * Update price comparison chart
 */
function updatePriceChart(cryptos) {
    const ctx = document.getElementById('priceChart');
    if (!ctx) return;

    const labels = cryptos.map(c => c.name);
    const prices = cryptos.map(c => c.price_usd || 0);

    // Destroy existing chart
    if (charts.priceChart) {
        charts.priceChart.destroy();
    }

    charts.priceChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Price (USD)',
                data: prices,
                backgroundColor: 'rgba(102, 126, 234, 0.6)',
                borderColor: 'rgba(102, 126, 234, 1)',
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    display: false
                }
            },
            scales: {
                y: {
                    beginAtZero: true
                }
            }
        }
    });
}

/**
 * Update market cap distribution chart
 */
function updateMarketCapChart(cryptos) {
    const ctx = document.getElementById('marketCapChart');
    if (!ctx) return;

    const labels = cryptos.map(c => c.name);
    const marketCaps = cryptos.map(c => c.market_cap_usd || 0);
    const colors = ['#667eea', '#764ba2', '#f093fb', '#4facfe', '#43e97b'];

    // Destroy existing chart
    if (charts.marketCapChart) {
        charts.marketCapChart.destroy();
    }

    charts.marketCapChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: marketCaps,
                backgroundColor: colors.slice(0, labels.length),
                borderColor: '#fff',
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    position: 'bottom'
                }
            }
        }
    });
}

/**
 * Update 24h change chart
 */
function updateChangeChart(cryptos) {
    const ctx = document.getElementById('changeChart');
    if (!ctx) return;

    const labels = cryptos.map(c => c.name);
    const changes = cryptos.map(c => c.change_24h_percent || 0);

    // Destroy existing chart
    if (charts.changeChart) {
        charts.changeChart.destroy();
    }

    charts.changeChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: '24h Change (%)',
                data: changes,
                borderColor: 'rgba(102, 126, 234, 1)',
                backgroundColor: 'rgba(102, 126, 234, 0.1)',
                tension: 0.4,
                fill: true,
                pointRadius: 5,
                pointBackgroundColor: changes.map(v => v >= 0 ? '#28a745' : '#dc3545'),
                pointBorderColor: '#fff',
                pointBorderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    display: true
                }
            },
            scales: {
                y: {
                    ticks: {
                        callback: function(value) {
                            return value + '%';
                        }
                    }
                }
            }
        }
    });
}

/**
 * Update quality trend chart (placeholder - would need historical data)
 */
function updateQualityTrendChart() {
    const ctx = document.getElementById('qualityTrendChart');
    if (!ctx) return;

    // This would show historical quality scores if we have time-series data
    // For now, just show a placeholder
    if (charts.qualityTrendChart) {
        charts.qualityTrendChart.destroy();
    }

    charts.qualityTrendChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: ['Sample 1', 'Sample 2', 'Sample 3'],
            datasets: [{
                label: 'Quality Score',
                data: [95, 93, 92],
                borderColor: '#28a745',
                backgroundColor: 'rgba(40, 167, 69, 0.1)',
                tension: 0.4,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    display: true
                }
            },
            scales: {
                y: {
                    min: 0,
                    max: 100
                }
            }
        }
    });
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
 * Display quality alerts
 */
function displayAlerts(alerts) {
    const alertsSection = document.getElementById('alertsSection');
    const noAlertsSection = document.getElementById('noAlertsSection');
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
    noAlertsSection.style.display = 'none';
}

/**
 * Hide quality alerts section
 */
function hideAlerts() {
    const alertsSection = document.getElementById('alertsSection');
    const noAlertsSection = document.getElementById('noAlertsSection');
    alertsSection.style.display = 'none';
    noAlertsSection.style.display = 'block';
}

/**
 * Fetch and display quality metrics
 */
async function fetchAndDisplayQualityMetrics() {
    try {
        const response = await fetch('/api/quality/metrics');
        const result = await response.json();
        
        if (result.metrics) {
            displayQualityMetrics(result.metrics);
        }
    } catch (error) {
        console.warn('Could not fetch quality metrics:', error);
    }
}

/**
 * Display quality metrics grid
 */
function displayQualityMetrics(metrics) {
    const grid = document.getElementById('qualityMetricsGrid');
    grid.innerHTML = '';
    
    if (typeof metrics === 'object') {
        Object.values(metrics).forEach(metric => {
            const card = document.createElement('div');
            card.className = 'quality-metric-card';
            
            const qualityClass = metric.quality_score >= 80 ? 'good' : 
                               metric.quality_score >= 60 ? 'warning' : 'critical';
            
            card.innerHTML = `
                <h4>${metric.crypto}</h4>
                <div class="metric-row">
                    <span class="metric-label">Quality Score</span>
                    <span class="metric-value ${qualityClass}">${metric.quality_score.toFixed(1)}%</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">Null Rate</span>
                    <span class="metric-value">${metric.null_rate.toFixed(1)}%</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">Duplicate Rate</span>
                    <span class="metric-value">${metric.duplicate_rate.toFixed(1)}%</span>
                </div>
                <div class="metric-row">
                    <span class="metric-label">Valid Records</span>
                    <span class="metric-value">${metric.total_records - metric.null_count}</span>
                </div>
            `;
            
            grid.appendChild(card);
        });
    }
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
