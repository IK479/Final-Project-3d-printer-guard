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
     Live Monitor
   ========================================= */
const osdElements = document.querySelectorAll('.backdrop-blur-sm');
// Test: Only if we are on a screen that has the video data, will the loop be activated.
if (osdElements.length >= 3) {
  setInterval(() => {
    const fps = (24 + Math.random() * 5).toFixed(1);
    const latency = (30 + Math.random() * 15).toFixed(0);
    osdElements[0].innerText = `FPS: ${fps}`;
    osdElements[1].innerText = `LATENCY: ${latency}ms`;

    const now = new Date();
    const timeString = now.getFullYear() + "-" + 
                       String(now.getMonth() + 1).padStart(2, '0') + "-" + 
                       String(now.getDate()).padStart(2, '0') + " " + 
                       String(now.getHours()).padStart(2, '0') + ":" + 
                       String(now.getMinutes()).padStart(2, '0') + ":" + 
                       String(now.getSeconds()).padStart(2, '0');
                       
    osdElements[2].innerText = timeString;
  }, 2000);

  const tempEl = document.getElementById('nozzle-temp-val');
    if (tempEl) {
        const temp = (214 + Math.random() * 2).toFixed(1);
        tempEl.innerText = `${temp}°C`;
    }

    // סימולציית זמן אינפרנס של מודל (בין 12 ל-25 מילי-שניות)
    const infEl = document.getElementById('inference-time-val');
    if (infEl) {
        const infTime = (12 + Math.random() * 13).toFixed(1);
        infEl.innerText = `${infTime}ms`;
    }
    
}

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

if (saveBtn && toast) {
  saveBtn.addEventListener('click', () => {
    toast.classList.remove('translate-y-24', 'opacity-0');
    toast.classList.add('translate-y-0', 'opacity-100');
    
    setTimeout(() => {
      toast.classList.add('translate-y-24', 'opacity-0');
      toast.classList.remove('translate-y-0', 'opacity-100');
    }, 3000);
  });
}

// 3. Hover effect on settings areas
const sections = document.querySelectorAll('section');
if (sections.length > 0) {
  sections.forEach(section => {
    section.addEventListener('mouseenter', () => {
      const container = section.querySelector('.bg-surface-container');
      if(container) container.classList.add('border-primary/50');
    });
    section.addEventListener('mouseleave', () => {
      const container = section.querySelector('.bg-surface-container');
      if(container) container.classList.remove('border-primary/50');
    });
  });
}

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

// 2. Refresh button animation
const allButtons = Array.from(document.querySelectorAll('button'));
const refreshBtn = allButtons.find(btn => {
    const icon = btn.querySelector('span[data-icon="refresh"]');
    return icon !== null;
});

if (refreshBtn) {
    refreshBtn.addEventListener('click', () => {
        const icon = refreshBtn.querySelector('span');
        if(icon) {
            icon.style.transition = 'transform 0.5s ease';
            icon.style.transform = 'rotate(360deg)';
            setTimeout(() => {
                icon.style.transform = 'rotate(0deg)';
                alert('Data updated successfully');
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
                    const response = await fetch('/printer/emergency-stop', { method: 'POST' });
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
const liveFeedImg = document.getElementById('live-feed-img'); // תגית ה-<img> בתוך מסך המעקב

if (startStreamBtn) {
    startStreamBtn.addEventListener('click', async () => {
        try {
            // 1. Opening a new print session in the database
            const response = await fetch('/session/start', {
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
    stopCaptureBtn.addEventListener('click', async () => {
        try {
            // 1. Calling the API to end the session (updates the Backend)
            await fetch('/session/stop', { method: 'POST' });
            
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

ws.onmessage = function(event) {
    const alertData = JSON.parse(event.data);
    
    if (alertData.type === "NEW_ALERT") {
        console.log("🚨 ALERT RECEIVED FROM AI:", alertData.defect_type, alertData.confidence);
        
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
        // Find the tag that says "4 NEW" and change its number and color
        const alertBadge = Array.from(document.querySelectorAll('span')).find(
            el => el.textContent.includes('NEW') && el.classList.contains('text-status-badge')
        );
        
        if (alertBadge) {
            const currentCount = parseInt(alertBadge.textContent);
            if (!isNaN(currentCount)) {
                alertBadge.textContent = `${currentCount + 1} NEW`;
                
                // Change the meter color to bright red
                alertBadge.classList.replace('bg-surface-variant', 'bg-error');
                alertBadge.classList.replace('text-on-surface-variant', 'text-on-error');
                
                // Turns back to gray after 8 seconds
                setTimeout(() => {
                    alertBadge.classList.replace('bg-error', 'bg-surface-variant');
                    alertBadge.classList.replace('text-on-error', 'text-on-surface-variant');
                }, 8000);
            }
        }
    }
};

ws.onerror = function(error) {
    console.error("WebSocket Error:", error);
};

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