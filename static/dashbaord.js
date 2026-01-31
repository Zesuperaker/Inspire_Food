let currentUser = null;
let currentSession = null;
let batchMode = false;
let isScanning = false;

async function initializeDashboard() {
    try {
        const response = await fetch('/api/auth/me', {
            method: 'GET',
            headers: { 'Content-Type': 'application/json' }
        });

        if (!response.ok) {
            window.location.href = '/';
            return;
        }

        const data = await response.json();
        currentUser = data;
        document.getElementById('user-email').innerText = data.email;

        // Load recent scans on init
        await loadRecentScans();
    } catch (error) {
        console.error('Auth check failed:', error);
        window.location.href = '/';
    }
}

async function startNewSession() {
    try {
        const response = await fetch('/api/scan/start-session', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        });

        const data = await response.json();
        if (data.success) {
            currentSession = data.session_id;
            document.getElementById('session-info').classList.remove('hidden');
            document.getElementById('session-id').innerText = `Session: ${currentSession}`;
            clearResults();
            showNotification('New session started', 'success');
        }
    } catch (error) {
        showNotification('Error starting session: ' + error.message, 'error');
    }
}

async function scanSingle() {
    if (!currentSession) {
        showNotification('Start a session first', 'warning');
        return;
    }

    const description = document.getElementById('produce-description').value.trim();
    if (!description) {
        showNotification('Please enter a produce description', 'warning');
        return;
    }

    isScanning = true;
    const btn = document.getElementById('scan-btn-text');
    btn.innerText = 'Scanning...';

    try {
        const response = await fetch('/api/scan/single', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                produce_description: description,
                session_id: currentSession
            })
        });

        const data = await response.json();
        if (data.success) {
            displaySingleResult(data.data);
            document.getElementById('produce-description').value = '';
            showNotification('Produce scanned successfully', 'success');
        } else {
            showNotification('Scan failed: ' + data.error, 'error');
        }
    } catch (error) {
        showNotification('Error scanning: ' + error.message, 'error');
    } finally {
        isScanning = false;
        btn.innerText = 'Scan Item';
    }
}

async function scanBatch() {
    if (!currentSession) {
        showNotification('Start a session first', 'warning');
        return;
    }

    const itemsText = document.getElementById('batch-items').value.trim();
    if (!itemsText) {
        showNotification('Please enter at least one produce item', 'warning');
        return;
    }

    const produceList = itemsText.split('\n').filter(item => item.trim().length > 0);
    if (produceList.length === 0) {
        showNotification('Please enter at least one produce item', 'warning');
        return;
    }

    isScanning = true;
    const btn = document.getElementById('batch-btn-text');
    btn.innerText = 'Scanning...';

    try {
        const response = await fetch('/api/scan/batch', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                produce_list: produceList,
                session_id: currentSession
            })
        });

        const data = await response.json();
        if (data.success) {
            displayBatchResults(data);
            document.getElementById('batch-items').value = '';
            showNotification(`Scanned ${data.scans.length} items successfully`, 'success');
        } else {
            showNotification('Batch scan failed: ' + data.error, 'error');
        }
    } catch (error) {
        showNotification('Error scanning batch: ' + error.message, 'error');
    } finally {
        isScanning = false;
        btn.innerText = 'Scan Batch';
    }
}

function displaySingleResult(result) {
    document.getElementById('results-section').classList.remove('hidden');
    const container = document.getElementById('results-container');
    container.innerHTML = '';

    const card = createResultCard(result);
    container.appendChild(card);
}

function displayBatchResults(data) {
    document.getElementById('results-section').classList.remove('hidden');
    document.getElementById('summary-section').classList.remove('hidden');

    const container = document.getElementById('results-container');
    container.innerHTML = '';

    data.scans.forEach(scan => {
        const card = createResultCard(scan);
        container.appendChild(card);
    });

    // Update summary
    document.getElementById('summary-total').innerText = data.summary.total_scanned;
    document.getElementById('summary-expiring').innerText = data.summary.expiring_soon_count;
    document.getElementById('summary-expired').innerText = data.summary.expired_count;
    document.getElementById('summary-healthy').innerText = data.summary.healthy_count;
}

function createResultCard(result) {
    const card = document.createElement('div');
    card.className = 'pop-card !opacity-100 !transform-none';

    const statusColor = result.is_expired ? 'red' : result.is_expiring_soon ? 'orange' : 'green';
    const statusBg = statusColor === 'red' ? 'bg-red-500/10' :
        statusColor === 'orange' ? 'bg-orange-500/10' : 'bg-green-500/10';
    const statusText = statusColor === 'red' ? 'text-red-400' :
        statusColor === 'orange' ? 'text-orange-400' : 'text-green-400';
    const statusLabel = result.is_expired ? 'EXPIRED' :
        result.is_expiring_soon ? 'EXPIRING SOON' : 'FRESH';

    card.innerHTML = `
        <div class="flex items-start justify-between mb-4">
            <div>
                <h3 class="text-2xl font-900 text-white">${escapeHtml(result.produce_name)}</h3>
                <p class="text-slate-400 text-sm mt-1">${escapeHtml(result.notes)}</p>
            </div>
            <span class="${statusBg} ${statusText} px-3 py-1 rounded-full text-xs font-900 uppercase tracking-widest">
                ${statusLabel}
            </span>
        </div>
        <div class="grid grid-cols-2 gap-4 mb-6">
            <div class="bg-white/5 rounded-xl p-4">
                <p class="text-[10px] font-900 uppercase tracking-widest text-slate-400 mb-2">Shelf Life</p>
                <p class="text-3xl font-900">${result.shelf_life_days}</p>
                <p class="text-xs text-slate-500">days remaining</p>
            </div>
            <div class="bg-white/5 rounded-xl p-4">
                <p class="text-[10px] font-900 uppercase tracking-widest text-slate-400 mb-2">Scanned</p>
                <p class="text-sm text-slate-300">${new Date(result.scanned_at).toLocaleDateString()}</p>
                <p class="text-xs text-slate-500">${new Date(result.scanned_at).toLocaleTimeString()}</p>
            </div>
        </div>
        <button onclick="getStorageTips('${escapeHtml(result.produce_name)}')"
            class="w-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-4 py-3 rounded-xl font-900 text-xs uppercase tracking-widest hover:bg-emerald-500 hover:text-black transition-all">
            Storage Tips
        </button>
    `;

    return card;
}

async function getStorageTips(produceName) {
    try {
        const response = await fetch('/api/scan/storage-tips', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                produce_name: produceName
            })
        });

        const data = await response.json();
        if (data.success) {
            document.getElementById('tips-produce').innerText = data.produce;
            document.getElementById('tips-content').innerText = data.recommendations;
            document.getElementById('tips-modal').classList.add('opacity-100', 'pointer-events-auto');
        } else {
            showNotification('Could not fetch tips: ' + data.error, 'error');
        }
    } catch (error) {
        showNotification('Error fetching tips: ' + error.message, 'error');
    }
}

function closeTipsModal() {
    document.getElementById('tips-modal').classList.remove('opacity-100', 'pointer-events-auto');
}

async function loadRecentScans() {
    try {
        const response = await fetch('/api/scan/recent?limit=10', {
            method: 'GET',
            headers: { 'Content-Type': 'application/json' }
        });

        const data = await response.json();
        if (data.success && data.scans.length > 0) {
            const container = document.getElementById('recent-container');
            container.innerHTML = '';

            data.scans.forEach(scan => {
                const item = document.createElement('div');
                item.className = 'bg-white/5 border border-white/10 rounded-xl p-4 flex items-center justify-between hover:bg-white/10 transition-colors';

                const statusColor = scan.is_expired ? 'red' : scan.is_expiring_soon ? 'orange' : 'green';
                const statusBg = statusColor === 'red' ? 'bg-red-500/20 text-red-400' :
                    statusColor === 'orange' ? 'bg-orange-500/20 text-orange-400' : 'bg-green-500/20 text-green-400';

                item.innerHTML = `
                    <div>
                        <p class="font-600 text-white">${escapeHtml(scan.produce_name)}</p>
                        <p class="text-[10px] text-slate-400 uppercase tracking-widest font-800 mt-1">
                            ${new Date(scan.scanned_at).toLocaleDateString()} at ${new Date(scan.scanned_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                        </p>
                    </div>
                    <div class="flex items-center gap-3">
                        <div class="text-right">
                            <p class="text-2xl font-900">${scan.shelf_life_days}</p>
                            <p class="text-[10px] text-slate-400">days</p>
                        </div>
                        <span class="${statusBg} px-3 py-1 rounded-full text-xs font-900 uppercase tracking-widest">
                            ${statusColor === 'red' ? 'Expired' : statusColor === 'orange' ? 'Soon' : 'Fresh'}
                        </span>
                    </div>
                `;

                container.appendChild(item);
            });
        } else {
            document.getElementById('recent-container').innerHTML = `
                <div class="text-center py-12 text-slate-400">
                    <p class="text-sm">No scans yet. Start scanning to see your history.</p>
                </div>
            `;
        }
    } catch (error) {
        console.error('Error loading recent scans:', error);
    }
}

function clearResults() {
    document.getElementById('results-section').classList.add('hidden');
    document.getElementById('summary-section').classList.add('hidden');
    document.getElementById('results-container').innerHTML = '';
}

function toggleBatchMode() {
    batchMode = !batchMode;
    document.getElementById('batch-section').classList.toggle('hidden');
    if (batchMode) {
        document.getElementById('batch-items').focus();
    }
}

async function logout() {
    try {
        await fetch('/api/auth/logout', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        window.location.href = '/';
    } catch (error) {
        showNotification('Logout error: ' + error.message, 'error');
    }
}

function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    const colors = {
        success: 'bg-green-500',
        error: 'bg-red-500',
        warning: 'bg-orange-500',
        info: 'bg-blue-500'
    };

    notification.className = `fixed bottom-6 right-6 ${colors[type] || colors.info} text-white px-6 py-4 rounded-xl font-900 uppercase tracking-widest text-xs z-[600] animate-pulse`;
    notification.innerText = message;
    document.body.appendChild(notification);

    setTimeout(() => {
        notification.remove();
    }, 3000);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Initialize dashboard on page load
window.addEventListener('DOMContentLoaded', initializeDashboard);

// Auto-refresh recent scans every 30 seconds
setInterval(() => {
    if (!isScanning) {
        loadRecentScans();
    }
}, 30000);