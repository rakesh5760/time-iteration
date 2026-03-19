const API_URL = 'http://localhost:5000';

const startBtn = document.getElementById('startBtn');
const stopBtn = document.getElementById('stopBtn');
const intervalInput = document.getElementById('interval');
const statusBadge = document.getElementById('statusBadge');
const extractedTime = document.getElementById('extractedTime');
const lastUpdated = document.getElementById('lastUpdated');
const statusMessage = document.getElementById('statusMessage');

let pollingInterval = null;

async function startExtraction() {
    const interval = parseFloat(intervalInput.value);
    if (isNaN(interval) || interval <= 0) {
        alert("Please enter a valid iteration time.");
        return;
    }

    // Disable UI immediately to prevent double-clicks
    updateUI(true);
    
    try {
        const response = await fetch(`${API_URL}/start`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ interval })
        });
        
        const data = await response.json();
        if (response.ok) {
            statusBadge.innerText = 'Starting...';
            statusMessage.innerText = 'Initializing scraper...';
            startPolling();
        } else {
            alert(data.message);
            updateUI(false);
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Failed to connect to backend server. Make sure app.py is running.');
        updateUI(false);
    }
}

async function stopExtraction() {
    try {
        const response = await fetch(`${API_URL}/stop`, { method: 'POST' });
        if (response.ok) {
            updateUI(false);
            stopPolling();
        }
    } catch (error) {
        console.error('Error:', error);
    }
}

async function fetchStatus() {
    try {
        const response = await fetch(`${API_URL}/status`);
        const data = await response.json();
        
        extractedTime.innerText = data.latest_data || '--:--:--';
        lastUpdated.innerText = data.last_updated_time || 'Never';
        statusMessage.innerText = data.status_message;
        
        if (data.is_running) {
            statusBadge.innerText = 'Running';
            statusBadge.className = 'badge running';
            updateUI(true);
        } else {
            statusBadge.innerText = 'Idle';
            statusBadge.className = 'badge idle';
            updateUI(false);
        }
    } catch (error) {
        console.error('Error fetching status:', error);
    }
}

function updateUI(isRunning) {
    startBtn.disabled = isRunning;
    stopBtn.disabled = !isRunning;
    intervalInput.disabled = isRunning;
}

function startPolling() {
    if (!pollingInterval) {
        pollingInterval = setInterval(fetchStatus, 2000);
    }
}

function stopPolling() {
    // We can keep polling for a bit to show the "Stopped" status, then clear
    setTimeout(() => {
        // clearInterval(pollingInterval);
        // pollingInterval = null;
    }, 5000);
}

startBtn.addEventListener('click', startExtraction);
stopBtn.addEventListener('click', stopExtraction);

// Initial check
fetchStatus();
startPolling();
