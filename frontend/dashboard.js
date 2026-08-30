/**
 * CivicPulse Dashboard JavaScript
 * Fetches and displays hotspot data from the analytics API
 */

const ANALYTICS_API = '/hotspots';
const COMPLAINTS_API = '/complaints';

const summaryText = document.getElementById('summary-text');
const categoryChart = document.getElementById('category-chart');
const hotspotsList = document.getElementById('hotspots-list');
const refreshBtn = document.getElementById('refresh-btn');

async function fetchHotspots() {
    try {
        const response = await fetch(ANALYTICS_API);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error('Error fetching hotspots:', error);
        return null;
    }
}

async function fetchComplaints() {
    try {
        const response = await fetch(COMPLAINTS_API);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error('Error fetching complaints:', error);
        return [];
    }
}

function renderSummary(data) {
    if (!data || !data.summary) {
        summaryText.textContent = 'No data available';
        return;
    }
    summaryText.textContent = data.summary;
}

function renderCategoryBreakdown(data) {
    if (!data || !data.category_breakdown) {
        categoryChart.innerHTML = '<p>No category data available</p>';
        return;
    }

    const breakdown = data.category_breakdown;
    const total = Object.values(breakdown).reduce((a, b) => a + b, 0);

    if (total === 0) {
        categoryChart.innerHTML = '<p>No complaints logged yet</p>';
        return;
    }

    const colors = {
        road: '#e74c3c',
        water: '#3498db',
        electricity: '#f39c12',
        sanitation: '#27ae60',
    };

    let html = '<div class="category-breakdown">';
    for (const [category, count] of Object.entries(breakdown)) {
        const percentage = ((count / total) * 100).toFixed(1);
        const color = colors[category] || '#95a5a6';
        html += `
            <div class="category-bar">
                <div class="category-label">
                    <span class="category-color" style="background-color: ${color}"></span>
                    ${category.charAt(0).toUpperCase() + category.slice(1)}
                </div>
                <div class="category-progress">
                    <div class="category-fill" style="width: ${percentage}%; background-color: ${color}"></div>
                </div>
                <div class="category-count">${count} (${percentage}%)</div>
            </div>
        `;
    }
    html += '</div>';
    categoryChart.innerHTML = html;
}

function renderHotspots(data) {
    if (!data || !data.ranked_districts || data.ranked_districts.length === 0) {
        hotspotsList.innerHTML = '<p>No hotspot data available</p>';
        return;
    }

    let html = '<table class="hotspots-table"><thead><tr><th>Rank</th><th>District</th><th>Complaints</th><th>Urgency</th><th>Action Priority</th></tr></thead><tbody>';

    data.ranked_districts.forEach((district, index) => {
        const urgency = district.urgency || 'unknown';
        const urgencyClass = `urgency-${urgency.toLowerCase()}`;
        const actionPriority = district.action_priority || 'Monitor';

        html += `
            <tr>
                <td>${index + 1}</td>
                <td>${district.district || district.name || 'Unknown'}</td>
                <td>${district.count || 0}</td>
                <td><span class="urgency-badge ${urgencyClass}">${urgency.charAt(0).toUpperCase() + urgency.slice(1)}</span></td>
                <td>${actionPriority}</td>
            </tr>
        `;
    });

    html += '</tbody></table>';
    hotspotsList.innerHTML = html;
}

async function loadDashboard() {
    summaryText.textContent = 'Loading...';
    categoryChart.innerHTML = 'Loading...';
    hotspotsList.innerHTML = 'Loading...';

    const [hotspotsData, complaints] = await Promise.all([
        fetchHotspots(),
        fetchComplaints(),
    ]);

    if (hotspotsData) {
        renderSummary(hotspotsData);
        renderCategoryBreakdown(hotspotsData);
        renderHotspots(hotspotsData);
    } else {
        summaryText.textContent = 'Failed to load hotspot data';
        categoryChart.innerHTML = '<p>Error loading data</p>';
        hotspotsList.innerHTML = '<p>Error loading data</p>';
    }
}

refreshBtn.addEventListener('click', loadDashboard);

// Initial load
loadDashboard();