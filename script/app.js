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
// הבדיקה: רק אם אנחנו במסך שיש בו את נתוני הוידאו, תפעיל את הלופ
if (osdElements.length >= 2) {
  setInterval(() => {
    const fps = (59 + Math.random() * 2).toFixed(1);
    const latency = (10 + Math.random() * 5).toFixed(0);
    osdElements[0].innerText = `FPS: ${fps}`;
    osdElements[1].innerText = `LATENCY: ${latency}ms`;
  }, 2000);
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
// חיפוש כל הכפתורים שמכילים את הטקסט EMERGENCY STOP
const emergencyBtns = document.querySelectorAll('button');

emergencyBtns.forEach(btn => {
    if (btn.textContent.includes('EMERGENCY STOP')) {
        btn.addEventListener('click', async () => {
            // הוספת חלון אישור כדי למנוע עצירה בטעות
            const confirmStop = confirm('⚠️ URGENT ACTION: Are you sure you want to abort the current print?');
            
            if (confirmStop) {
                try {
                    // קריאה לשרת ה-FastAPI שלנו
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