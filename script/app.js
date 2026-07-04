/* =========================================
   Aegis Client-Side Security Guard 
   ========================================= */
const token = sessionStorage.getItem('aegis_token');
if (token) {
    try {
        const payload = JSON.parse(atob(token.split('.')[1]));
        if (payload.exp * 1000 < Date.now()) {
            sessionStorage.removeItem('aegis_token');
            window.location.href = '/login';
        }
    } catch(e) {
        sessionStorage.removeItem('aegis_token');
        window.location.href = '/login';
    }
} else if (!window.location.pathname.includes('/login') && !window.location.pathname.includes('/register')) {
    window.location.href = '/login';
}

// 1. Helper function for making API requests without authentication headers
async function fetchWithAuth(url, options = {}) {
    const token = sessionStorage.getItem('aegis_token');
    options.headers = {
        ...options.headers,
        'Authorization': `Bearer ${token}`
    };
    
    const response = await fetch(url, options);
    if (response.status === 401) {
        // If the token is expired or invalid, we will clear it and return to the login screen.
        sessionStorage.removeItem('aegis_token');
        window.location.href = '/login';
    }
    return response;
}

/* =========================================
  Common code for all screens
   ========================================= */
// Click effect (micro-interaction) on each button in the system
document.querySelectorAll('button').forEach(btn => {
  btn.addEventListener('click', function() {
    const icon = this.querySelector('.material-symbols-outlined');
    if (icon) {
      icon.classList.add('scale-125');
      setTimeout(() => icon.classList.remove('scale-125'), 150);
    }
  });
});

/* =========================================
      System Config
   ========================================= */
// 1. Slider logic
const slider = document.getElementById('threshold-slider');
const sliderVal = document.getElementById('threshold-val');

// Test: Runs the slider code only if it is on the current page
if (slider && sliderVal) {
  slider.addEventListener('input', (e) => {
    sliderVal.textContent = `${e.target.value}%`;
    if(e.target.value < 50) {
      sliderVal.className = 'font-mono-label text-headline-sm text-error';
    } else if(e.target.value < 80) {
      sliderVal.className = 'font-mono-label text-headline-sm text-secondary';
    } else {
      sliderVal.className = 'font-mono-label text-headline-sm text-primary';
    }
  });
}

// 2. Toast pane logic
const saveBtn = Array.from(document.querySelectorAll('button')).find(el => el.textContent.includes('SAVE CONFIGURATION'));
const toast = document.getElementById('save-toast');

if (saveBtn && toast && slider) {
  saveBtn.addEventListener('click', async () => {
    // Convert percentages to decimals
    const thresholdDecimal = parseInt(slider.value) / 100.0;
    
   try {
        const response = await fetchWithAuth('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ confidence_threshold: thresholdDecimal })
        });
        
        const data = await response.json();
        
        if (data.status === 'success') {
            // Popping up the green success window
            toast.classList.remove('translate-y-24', 'opacity-0');
            toast.classList.add('translate-y-0', 'opacity-100');
            
            setTimeout(() => {
                toast.classList.add('translate-y-24', 'opacity-0');
                toast.classList.remove('translate-y-0', 'opacity-100');
            }, 3000);
            
            // Update the system log on the dashboard page
            if (typeof addSystemLog === 'function') {
                addSystemLog(`Confidence threshold updated to ${slider.value}%`, "SYS");
            }
        }
    } catch (error) {
        console.error("Error saving settings:", error);
        alert("⚠️ Failed to sync configuration with the server.");
    }
  });
}

// 3. Hover effect on settings areas
async function syncSettingsOnLoad() {
    if (slider && sliderVal) {
        try {
            const response = await fetchWithAuth('/api/settings');
            const data = await response.json();
            if (data.confidence_threshold) {
                const percent = Math.round(data.confidence_threshold * 100);
                slider.value = percent;
                // Enables the visual update of the number on the screen
                slider.dispatchEvent(new Event('input')); 
            }
        } catch(e) {}
    }
}

// 4. Reset to Default Logic
const resetBtn = document.getElementById('reset-default-btn');

if (resetBtn) {
  resetBtn.addEventListener('click', async () => {
    if (confirm('⚠️ Are you sure you want to reset to 85% Threshold?')) {
      try {
                const response = await fetchWithAuth('/api/settings/reset', { method: 'POST' });
                const data = await response.json();
                
                if (data.status === 'success') {
                    // Visual update of the on-screen slider to 85
                    const slider = document.getElementById('threshold-slider');
                    if (slider) {
                        slider.value = 85;
                        slider.dispatchEvent(new Event('input')); 
                    }
                    
                    // Popping up the green success pane below
                    const toast = document.getElementById('save-toast');
                    if (toast) {
                        toast.classList.remove('translate-y-24', 'opacity-0');
                        toast.classList.add('translate-y-0', 'opacity-100');
                        setTimeout(() => {
                            toast.classList.add('translate-y-24', 'opacity-0');
                            toast.classList.remove('translate-y-0', 'opacity-100');
                        }, 3000);
                    }
                } else {
                    alert("⚠️ Error: " + data.message);
                }
            } catch (error) {
                console.error("Reset error:", error);
                alert("⚠️ Failed to communicate with the server for reset.");
            }
        }
    });
}
document.addEventListener('DOMContentLoaded', syncSettingsOnLoad);

/* =========================================
      Alerts & Print History
   ========================================= */
// 1. Table row click effect
const tableRows = document.querySelectorAll('tr');
if (tableRows.length > 0) {
    tableRows.forEach(row => {
        row.addEventListener('click', () => {
            row.classList.add('bg-surface-bright/50');
            setTimeout(() => row.classList.remove('bg-surface-bright/50'), 300);
        });
    });
}

// 2. Refresh button 
const refreshBtn = document.getElementById('refresh-history-btn');

if (refreshBtn) {
    refreshBtn.addEventListener('click', async () => {
        const icon = refreshBtn.querySelector('span');
        if(icon) {
            icon.classList.add('animate-spin');
        }
        try{
            // Pulling the updated data from the database
            await loadHistoryTable();
        } catch(error){
            console.error("Error refreshing data:", error);
        }finally{
            // Stopping the animation after the data has loaded
          setTimeout(() => {
                if(icon) {
                    icon.classList.remove('animate-spin');
                }
            }, 500);
        }
    });
}

/* =========================================
      Emergency Stop Logic
   ========================================= */
// Search for all buttons that contain the text EMERGENCY STOP
const emergencyBtns = document.querySelectorAll('button');

emergencyBtns.forEach(btn => {
    if (btn.textContent.includes('EMERGENCY STOP')) {
        btn.addEventListener('click', async () => {
            // Added a confirmation window to prevent accidental stopping
            const confirmStop = confirm('⚠️ URGENT ACTION: Are you sure you want to abort the current print?');
            
            if (confirmStop) {
                try {
                    // Calling our FastAPI server
                    const response = await fetchWithAuth('/printer/emergency-stop', { method: 'POST' });
                    const result = await response.json();
                    
                    if (result.status === 'success') {
                        alert('✅ EMERGENCY STOP INITIATED.\nPrinter has been successfully halted.');
                    } else {
                        alert('❌ ERROR: Could not halt printer.\n' + result.message);
                    }
                } catch (error) {
                    console.error("Error triggering emergency stop:", error);
                    alert('❌ SYSTEM ERROR: Failed to communicate with the Backend API.');
                }
            }
        });
    }
});

/* =========================================
   Live Dashboard - Hardware Stream Controls
   ========================================= */

const startStreamBtn = document.getElementById('start-stream-btn');
const stopCaptureBtn = document.getElementById('stop-capture-btn');
const liveFeedImg = document.getElementById('live-feed-img'); 

if (startStreamBtn) {
    addSystemLog("Initializing camera hardware...", "SYS"); 
    startStreamBtn.addEventListener('click', async () => {
        try {
            // 1. Opening a new print session in the database
            const response = await fetchWithAuth('/session/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ printer_name: "Unit 01-Alpha", filament_type: "PLA" })
            });
            const data = await response.json();
            
            if (data.status === 'success') {
                alert('🟢 Live Hardware Monitoring Started!');
                
                // 2. Connecting the canvas to the hardware stream in real time
                if (liveFeedImg) {
                    // Setting the src triggers a persistent GET request to the video streaming path
                    liveFeedImg.src = '/video_feed'; 
                }
            } else {
                alert('⚠️ ' + data.message);
            }
        } catch (error) {
            console.error('Error starting hardware session:', error);
        }
    });
}

if (stopCaptureBtn) {
    addSystemLog("Hardware stream terminated", "SYS"); 
    stopCaptureBtn.addEventListener('click', async () => {
        try {
            // 1. Calling the API to end the session (updates the Backend)
            await fetchWithAuth('/session/stop', { method: 'POST' });
            
            // 2. Secure stopping and disconnecting of the current at the interface
            if (liveFeedImg) {
                liveFeedImg.src = ''; 
            }
            alert('🔴 Camera Capture Stopped.');
        } catch (error) {
            console.error('Error stopping capture:', error);
        }
    });
}


/* =========================================
   Live Alerts System (WebSocket)
   ========================================= */
// 1. Connecting to the server's open WebSocket channel
const ws = new WebSocket("ws://127.0.0.1:8000/ws/alerts");
ws.onopen = function() {
    addSystemLog("Telemetry live stream established", "OK");
};

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    // 1. Handling New AI Detection Alerts (Spaghetti, etc.)    
    if (data.type === "NEW_ALERT") {
       handleNewAlert(data);
    }
    // 2. Handling Live Telemetry Data (FPS, Time)
    else if (data.type === "TELEMETRY") {
        handleTelemetry(data);
    }
};

ws.onerror = function(error) {
    console.error("WebSocket Error:", error);
};

// ====================================================
//      Helper Functions 
// ====================================================
function handleNewAlert(data) {
     console.log("🚨 ALERT RECEIVED FROM AI:", data.defect_type, data.confidence);
        // Log the alert to the System Log panel
        addSystemLog(`Detection: ${data.defect_type} (${(data.confidence * 100).toFixed(1)}%)`, 'ALERT');
        addDynamicAlert(data.defect_type, data.confidence);
        // 2. Making the video frame red and glowing
        const liveFeedImg = document.getElementById('live-feed-img');
        if (liveFeedImg) {
            // Grab the DIV that wraps the image to apply the frame to it
            const container = liveFeedImg.parentElement;
            
            // Replacing the regular design with an emergency design
            container.classList.remove('border-outline-variant');
            container.classList.add('border-error', 'border-4', 'status-glow-error');
            
            // Reset to normal after 8 seconds so the screen doesn't stay red forever
            setTimeout(() => {
                container.classList.remove('border-error', 'border-4', 'status-glow-error');
                container.classList.add('border-outline-variant');
            }, 8000);
        }
        
        // 3. Update the Recent Alerts counter in the sidebar
        const alertBadge = document.getElementById('alert-counter');
        
        if (alertBadge) {
            const currentCount = parseInt(alertBadge.textContent);
            if (!isNaN(currentCount)) {
                alertBadge.textContent = `${currentCount + 1} NEW`;
                
                // Change the meter color to bright red
                alertBadge.classList.remove('bg-surface-variant', 'text-on-surface-variant');
                alertBadge.classList.add('bg-error', 'text-on-error');
                
                // Turns back to gray after 8 seconds
                setTimeout(() => {
                    alertBadge.classList.remove('bg-error', 'text-on-error');
                    alertBadge.classList.add('bg-surface-variant', 'text-on-surface-variant');
                }, 8000);
            }
        }
}

function handleTelemetry(data){
    // Update OSD (On-Screen Display) elements directly on the video feed
        const osdElements = document.querySelectorAll('.backdrop-blur-sm');
        if (osdElements.length >= 3) {
            osdElements[0].innerText = `FPS: ${data.fps}`;
            osdElements[1].innerText = `LATENCY: ${data.inference_time}ms`; 
      
            // Real-time system clock update (YYYY-MM-DD HH:MM:SS)
            const now = new Date();
            osdElements[2].innerText = now.getFullYear() + "-" + 
                String(now.getMonth() + 1).padStart(2, '0') + "-" + 
                String(now.getDate()).padStart(2, '0') + " " + 
                String(now.getHours()).padStart(2, '0') + ":" + 
                String(now.getMinutes()).padStart(2, '0') + ":" + 
                String(now.getSeconds()).padStart(2, '0');
        }
}

function addDynamicAlert(defectType, confidence, providedTime) {
    if (defectType && defectType.toLowerCase() === 'normal') {
        return;
    }
    
    const alertsFeed = document.getElementById('alerts-feed');
    if (!alertsFeed) return;

    // Converting confidence to percentage
    const confidencePercent = (confidence * 100).toFixed(1);
    
    // Setting the alert severity
    const isCritical = confidence > 0.90;

    const severityText = isCritical ? 'CRITICAL' : 'WARNING';
    const bgClass = isCritical ? 'bg-error-container/10 border-error/30' : 'bg-surface-container-high border-outline-variant';
    const hoverClass = isCritical ? 'hover:bg-error-container/20' : 'hover:bg-surface-variant';
    const badgeBg = isCritical ? 'bg-error' : 'bg-secondary-container';
    const badgeText = isCritical ? 'text-on-error' : 'text-on-secondary-container';
    const barColor = isCritical ? 'bg-error' : 'bg-secondary-container';
    const textColor = isCritical ? 'text-error' : 'text-secondary';
    
    // Creating the current timestamp (HH:MM:SS)
    let timeString;
    if (providedTime) {
        timeString = new Date(providedTime).toLocaleTimeString('en-US', { hour12: false });
    } else {
        timeString = new Date().toLocaleTimeString('en-US', { hour12: false });
    }

    // Creating the new element
    const alertDiv = document.createElement('div');
    alertDiv.className = `p-3 border rounded-lg group cursor-pointer transition-all ${bgClass} ${hoverClass}`;
    
    // Injecting the HTML with the variable data
    alertDiv.innerHTML = `
        <div class="flex items-center justify-between mb-2">
            <span class="px-2 py-0.5 ${badgeBg} ${badgeText} font-mono-label text-status-badge rounded">${severityText}</span>
            <span class="font-mono-label text-[10px] text-on-surface-variant">${timeString}</span>
        </div>
        <p class="font-mono-label text-mono-label text-on-surface mb-2">${defectType} Detected</p>
        <div class="flex items-center gap-3">
            <div class="flex-1 h-1 bg-surface-variant rounded-full overflow-hidden">
                <div class="h-full ${barColor}" style="width: ${confidencePercent}%"></div>
            </div>
            <span class="font-mono-label text-status-badge ${textColor}">${confidencePercent}%</span>
        </div>
    `;

    // Add the new alert to the top of the list
    alertsFeed.prepend(alertDiv);
    // Keeping a maximum of 50 notifications to avoid clogging up the browser
    if (alertsFeed.children.length > 50) {
        alertsFeed.removeChild(alertsFeed.lastChild);
    }
}


function addSystemLog(message, status = 'OK') {
    const logContainer = document.getElementById('system-log');
    if (!logContainer) return;

    const timeString = new Date().toLocaleTimeString('en-US', { hour12: false });
    const statusColor = status === 'ERROR' || status === 'ALERT' ? 'text-error' : 'text-primary';

    const logEntry = document.createElement('div');
    logEntry.className = 'flex justify-between border-b border-outline-variant/30 py-1';
    logEntry.innerHTML = `
        <span>[${timeString}] ${message}</span>
        <span class="${statusColor}">${status}</span>
    `;

    logContainer.appendChild(logEntry);
    // Automatic scrolling down to always see the new message
    logContainer.scrollTop = logContainer.scrollHeight; 
}

/* =========================================
   Video Player Interactions (Zoom, Grid, Snapshot)
   ========================================= */
let currentZoom = 1;
const zoomInBtn = document.querySelector('#zoom-in-btn, #zoom_in-btn');
const zoomOutBtn = document.querySelector('#zoom-out-btn, #zoom_out-btn');
const snapshotBtn = document.getElementById('snapshot-btn');
const toggleGridBtn = document.getElementById('toggle-grid-btn');
const liveFeed = document.getElementById('live-feed-img');
const videoContainer = liveFeed ? liveFeed.parentElement : null;

if (liveFeed) {
    liveFeed.style.transformOrigin = 'center center';
}

// Zoom In
if (zoomInBtn && liveFeed) {
    zoomInBtn.addEventListener('click', () => {
        if (currentZoom < 3){
            currentZoom += 0.2;
            liveFeed.style.transform = `scale(${currentZoom})`;
            liveFeed.style.transition = 'transform 0.3s ease cubic-bezier(0.4, 0, 0.2, 1)';
            if (typeof addSystemLog === 'function') addSystemLog(`Camera zoomed in to ${Math.round(currentZoom * 100)}%`, 'SYS');
        }
    });
}

// Zoom Out
if (zoomOutBtn && liveFeed) {
    zoomOutBtn.addEventListener('click', () => {
        if (currentZoom > 1){
            currentZoom -= 0.2;
        }else {
            currentZoom = 1;
        }
        liveFeed.style.transform = `scale(${currentZoom})`;
        if (typeof addSystemLog === 'function') addSystemLog(`Camera zoomed out to ${Math.round(currentZoom * 100)}%`, 'SYS');
    });
}

// Snapshot with Flash effect
if (snapshotBtn && liveFeed) {
    snapshotBtn.addEventListener('click', async () => {
        if (videoContainer) {
            // Create a white flash element
            const flash = document.createElement('div');
            flash.className = 'absolute inset-0 bg-white opacity-80 z-50 transition-opacity duration-300';
            videoContainer.appendChild(flash);
            
            // Fade it out
            setTimeout(() => flash.classList.remove('opacity-80'), 50);
            setTimeout(() => flash.classList.add('opacity-0'), 100);
            setTimeout(() => flash.remove(), 400);
        }
        // Capturing the image from the video and downloading it
        try {
            // Checks if the stream is working
            if (!liveFeed.src || liveFeed.src.endsWith('/')) {
                if (typeof addSystemLog === 'function') addSystemLog('Cannot take snapshot: No active video feed', 'ERROR');
                return;
            }

            // Creating a virtual canvas to convert the img tag to a file
            const canvas = document.createElement('canvas');
            canvas.width = liveFeed.naturalWidth || 640;
            canvas.height = liveFeed.naturalHeight || 480;
            const ctx = canvas.getContext('2d');
            // Drawing the current frame
            ctx.drawImage(liveFeed, 0, 0, canvas.width, canvas.height);
            // Convert the image to text format (Base64) without HTML prefix
            const dataURL = canvas.toDataURL('image/jpeg', 0.9);
            const base64Image = dataURL.split(',')[1];

            // Creating a hidden link for active download
            const link = document.createElement('a');
            // Create a filename that contains the current date and time
            const timeStamp = new Date().toISOString().replace(/[:.]/g, '-');
            link.download = `PrintGuard_Snapshot_${timeStamp}.jpg`;
            link.href = dataURL;
            link.click(); 

            if (typeof addSystemLog === 'function') addSystemLog('Snapshot saved locally', 'OK');

            // Sending the data to the server to be recorded in the DB
            const payload = {
                session_id: 1, 
                defect_type: "Manual Snapshot", 
                confidence: 1.0, // 100% confidence
                timestamp: new Date().toISOString(),
                image_base64: base64Image
            };

            const response = await fetch('/internal/detection', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (response.ok) {
                if (typeof addSystemLog === 'function') addSystemLog('Snapshot uploaded to History DB', 'OK');
                alert('📸 Snapshot saved securely to Print History!'); 
            } else {
                if (typeof addSystemLog === 'function') addSystemLog('Failed to sync snapshot to DB', 'ERROR');
            }

        } catch (err) {
            console.error("Snapshot error:", err);
            if (typeof addSystemLog === 'function') addSystemLog('Failed to save snapshot', 'ERROR');
        }
    });
}

// Toggle Grid Overlay
if (toggleGridBtn && videoContainer) {
    toggleGridBtn.addEventListener('click', () => {
        videoContainer.classList.toggle('grid-bg');
        
        // Toggle the icon
        const icon = toggleGridBtn.querySelector('span');
        if (icon) {
            icon.innerText = icon.innerText === 'grid_on' ? 'grid_off' : 'grid_on';
        }
    });
}

/* =========================================
   Dashboard Initialization (Recent Alerts & Logs)
   ========================================= */
async function loadInitialDashboardData() {
    const alertsFeed = document.getElementById('alerts-feed');
    if (!alertsFeed) return; // Ensures that it only runs on the dashboard screen

    addSystemLog("Dashboard connected securely", "OK");

    try {
        const statusRes = await fetchWithAuth('/api/session/status');
        const statusData = await statusRes.json();
        const liveFeedImg = document.getElementById('live-feed-img');
        
        if (statusData.is_monitoring && liveFeedImg) {
            liveFeedImg.src = '/video_feed'; // Reconnecting to the active stream
            liveFeedImg.src = '/video_feed?t=' + new Date().getTime();
            addSystemLog("Resumed active monitoring stream", "SYS");
        }
    } catch (error) {
       console.error("Failed to check session status:", error);
    }

    try {
        const response = await fetchWithAuth('/api/recent-alerts');
        const data = await response.json();
        
        if (data.status === 'success') {
            alertsFeed.innerHTML = ''; 
            [...data.alerts].reverse().forEach(alert => {
                addDynamicAlert(alert.defect_type, alert.confidence, alert.timestamp);
            });
            addSystemLog(`Loaded ${data.alerts.length} recent alerts from database`, "SYS");
        }
    } catch (error) {
        addSystemLog("Failed to sync historical alerts", "ERROR");
    }
}

// Running the function immediately
loadInitialDashboardData();

/* =========================================
   Authentication & Identity
   ========================================= */
// Finding all profile buttons in the system
const profileBtns = document.querySelectorAll('button span[data-icon="account_circle"]');

profileBtns.forEach(icon => {
    const btn = icon.parentElement;
    
    // Toggle the Secure Logout button action
    btn.onclick = (e) => {
        e.preventDefault();
        
        if (confirm('🔒 Are you sure you want to log out?')) {
            // Deleting identification data from the browser
            sessionStorage.removeItem('aegis_token');
            sessionStorage.removeItem('aegis_user');
            
            // Throwing the user back to the entry page
            window.location.href = '/login';
        }
    };
});

/* =========================================
   History Table Rendering & Filtering With CSV Export
   ========================================= */
let allHistoryEvents = []; // A repository of all events that came from the server
let currentFilteredEvents = []; // A temporary repository of events that passed the current filter

// Pulling data from the server once per load
async function loadHistoryTable() {
    const tableBody = document.getElementById('history-table-body');
    if (!tableBody) return; // Runs only if we are in the history screen

    try {
        const response = await fetchWithAuth('/api/history-data');
        const data = await response.json();
        
        if (data.status === 'success') {
            allHistoryEvents = data.events; // Save the data in the local database
            currentFilteredEvents = data.events; // By default, everything is displayed at the beginning
            renderHistoryTable(currentFilteredEvents);  // Draw everything for the first time
        }
    } catch (error) {
        console.error("Failed to load history data:", error);
    }
}

// Table drawing function (receives an array of events and draws them)
function renderHistoryTable(eventsToRender) {
    const tableBody = document.getElementById('history-table-body');
    if (!tableBody) return;
    
    tableBody.innerHTML = '';
    // Update the event summary row dynamically
    const paginationText = document.getElementById('pagination-text');
    if (paginationText) {
        const totalEvents = allHistoryEvents.length; // Total events in the database
        const renderedCount = eventsToRender.length; // The number of events that passed the current filter.
        
        if (renderedCount === 0) {
            paginationText.textContent = `Showing 0 of ${totalEvents} events`;
        } else {
            paginationText.textContent = `Showing 1-${renderedCount} of ${totalEvents} events`;
        }
    }

    if(eventsToRender.length === 0) {
         tableBody.innerHTML = '<tr><td colspan="5" class="p-8 text-center text-on-surface-variant font-mono-label">No matching events found.</td></tr>';
         return;
    }

    eventsToRender.forEach(event => {
        const confPercent = (event.confidence * 100).toFixed(1);
        const isCritical = event.confidence > 0.90;
        
        const severityText = isCritical ? `CRITICAL: ${event.defect_type}` : `WARNING: ${event.defect_type}`;
        const badgeBg = isCritical ? 'bg-error-container text-on-error-container' : 'bg-secondary-container text-on-secondary-container';
        const barColor = isCritical ? 'bg-error' : 'bg-secondary';
        const textColor = isCritical ? 'text-error' : 'text-secondary';
        
        const formattedTime = event.timestamp.replace('T', ' ').split('.')[0];

        const tr = document.createElement('tr');
        tr.className = 'border-b border-outline-variant hover:bg-surface-variant/30 transition-colors';
        tr.innerHTML = `
            <td class="p-4 font-mono-label text-center">${formattedTime}</td>
            <td class="p-4">
            <div class="flex justify-center">
                <div class="w-16 h-10 bg-surface-dim border border-outline-variant rounded overflow-hidden flex">
                    <img alt="Defect Snapshot" class="w-full h-full object-cover" src="${event.snapshot_url}"/>
                </div>
            </td>
            <td class="p-4">
                <div class="flex justify-center">
                <span class="${badgeBg} px-2 py-0.5 rounded-full font-status-badge text-status-badge">${severityText}</span>
            </td>
            <td class="p-4">
                <div class="flex justify-center items-center gap-2">
                    <div class="w-24 h-1 bg-surface-dim rounded-full overflow-hidden">
                        <div class="h-full ${barColor}" style="width: ${confPercent}%"></div>
                    </div>
                    <span class="font-mono-label ${textColor}">${confPercent}%</span>
                </div>
            </td>
            <td class="p-4">
                <div class="flex justify-center">
                <a href="${event.snapshot_url}" target="_blank" class="text-primary hover:underline font-bold">View Image</a>
            </td>
        `;
        tableBody.appendChild(tr);
    });
}

// The filter function that is activated every time something is changed
function applyFilters() {
    const defectFilter = document.getElementById('filter-defect')?.value || 'all';
    const confFilter = document.getElementById('filter-confidence')?.value || 'all';
    const timeFilter = document.getElementById('filter-time')?.value || 'all';

    currentFilteredEvents = allHistoryEvents.filter(event => {
        const matchesDefect = defectFilter === 'all' || event.defect_type.toLowerCase().includes(defectFilter);

        const confPercent = event.confidence * 100;
        let matchesConf = true;
        if (confFilter !== 'all') {
            matchesConf = confPercent >= parseInt(confFilter);
        }

        let matchesTime = true;
        if (timeFilter !== 'all') {
            const eventDate = new Date(event.timestamp);
            const now = new Date();
            const diffHours = (now - eventDate) / (1000 * 60 * 60); 
            
            if (timeFilter === '24h') matchesTime = diffHours <= 24;
            if (timeFilter === '7d') matchesTime = diffHours <= (24 * 7);
        }

        return matchesDefect && matchesConf && matchesTime;
    });

    renderHistoryTable(currentFilteredEvents);
}

// === Export only the filtered data to CSV ===
function exportFilteredCSV() {
    if (!currentFilteredEvents || currentFilteredEvents.length === 0) {
        alert("No matching records found to export.");
        return;
    }

    let csvContent = "\uFEFF"; 
    csvContent += 'PrintGuard System Export\n\n';
    csvContent += 'Timestamp,Printer Name,Defect Type,Confidence Score\n';

    currentFilteredEvents.forEach(event => {
        const timestamp = event.timestamp ? event.timestamp.replace('T', ' ').split('.')[0] : "Unknown Time";
        const printerName = "Unit 01-Alpha"; 
        const defectType = event.defect_type ? event.defect_type : "Unknown Defect";
        const confidence = event.confidence !== null ? `${(event.confidence * 100).toFixed(1)}%` : "N/A";

        csvContent += `"${timestamp}","${printerName}","${defectType}","${confidence}"\n`;
    });

    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement("a");
    const timeStamp = new Date().toISOString().slice(0, 10);
    
    link.href = URL.createObjectURL(blob);
    link.setAttribute("download", `PrintGuard_Filtered_History_${timeStamp}.csv`);
    document.body.appendChild(link);
    
    link.click(); 
    document.body.removeChild(link);
}

// Initializing the screen
document.addEventListener('DOMContentLoaded', () => {
    loadHistoryTable();

    const filterDefect = document.getElementById('filter-defect');
    const filterConf = document.getElementById('filter-confidence');
    const filterTime = document.getElementById('filter-time');

    if(filterDefect) filterDefect.addEventListener('change', applyFilters); 
    if(filterConf) filterConf.addEventListener('change', applyFilters);
    if(filterTime) filterTime.addEventListener('change', applyFilters);
    });

// === Clear Alerts & History Logic ===
const clearHistoryBtn = document.getElementById('clear-history-btn');

if (clearHistoryBtn) {
    clearHistoryBtn.addEventListener('click', async () => {
        // Request confirmation from the user before deletion
        const confirmDelete = confirm("⚠️ Are you sure you want to permanently delete all alerts and history? This action cannot be undone.");
        
        if (confirmDelete) {
            try {
                // Sending a deletion request to the server
                const response = await fetchWithAuth('/api/history', { method: 'DELETE' });
                const data = await response.json();
                
                if (data.status === 'success') {
                    alert("✅ All alerts have been successfully cleared.");
                    // Refresh the table to show it is empty
                    loadHistoryTable(); 
                } else {
                    alert("❌ Error clearing alerts: " + data.message);
                }
            } catch (e) {
                console.error("Failed to clear history:", e);
                alert("❌ System error while trying to clear alerts.");
            }
        }
    });
}
