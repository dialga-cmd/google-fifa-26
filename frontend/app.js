/**
 * CivicPulse Complaint Form JavaScript
 * Handles complaint submission and displays recent complaints
 */

const COMPLAINT_API = '/log_complaint';
const COMPLAINTS_API = '/complaints';

const form = document.getElementById('complaint-form-element');
const formMessage = document.getElementById('form-message');
const complaintsList = document.getElementById('complaints-list');
const submitBtn = document.getElementById('submit-btn');

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

function renderComplaints(complaints) {
    if (!complaints || complaints.length === 0) {
        complaintsList.innerHTML = '<p>No complaints logged yet.</p>';
        return;
    }

    // Show only the 10 most recent
    const recent = complaints.slice(0, 10);

    let html = '<ul class="complaints-list">';
    recent.forEach(complaint => {
        const urgencyClass = `urgency-${(complaint.urgency || 'medium').toLowerCase()}`;
        const date = new Date(complaint.created_at).toLocaleDateString();
        html += `
            <li class="complaint-item">
                <div class="complaint-header">
                    <span class="complaint-category">${complaint.category}</span>
                    <span class="urgency-badge ${urgencyClass}">${(complaint.urgency || 'medium').charAt(0).toUpperCase() + (complaint.urgency || 'medium').slice(1)}</span>
                </div>
                <div class="complaint-location">${complaint.location}</div>
                <div class="complaint-description">${complaint.description}</div>
                <div class="complaint-meta">
                    <span>Reported: ${date}</span>
                    ${complaint.citizen_name ? `<span>By: ${complaint.citizen_name}</span>` : ''}
                </div>
            </li>
        `;
    });
    html += '</ul>';
    complaintsList.innerHTML = html;
}

async function loadComplaints() {
    complaintsList.innerHTML = 'Loading...';
    const complaints = await fetchComplaints();
    renderComplaints(complaints);
}

function showMessage(message, isError = false) {
    formMessage.textContent = message;
    formMessage.className = isError ? 'error' : 'success';
    formMessage.style.display = 'block';

    // Hide after 5 seconds
    setTimeout(() => {
        formMessage.style.display = 'none';
    }, 5000);
}

form.addEventListener('submit', async (e) => {
    e.preventDefault();

    const formData = new FormData(form);
    const complaint = {
        category: formData.get('category'),
        location: formData.get('location'),
        description: formData.get('description'),
        urgency: formData.get('urgency'),
        citizen_name: formData.get('citizen_name') || null,
        contact: formData.get('contact') || null,
    };

    // Validate required fields
    if (!complaint.category || !complaint.location || !complaint.description) {
        showMessage('Please fill in all required fields', true);
        return;
    }

    submitBtn.disabled = true;
    submitBtn.textContent = 'Submitting...';
    formMessage.style.display = 'none';

    try {
        const response = await fetch(COMPLAINT_API, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(complaint),
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.detail || `HTTP error! status: ${response.status}`);
        }

        showMessage(`Complaint submitted successfully! Reference #${data.id}`);
        form.reset();
        await loadComplaints();
    } catch (error) {
        console.error('Error submitting complaint:', error);
        showMessage(`Error: ${error.message}`, true);
    } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Submit Complaint';
    }
});

// Initial load
loadComplaints();