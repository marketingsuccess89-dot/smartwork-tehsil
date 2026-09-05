// State Variables
let ws = null;
let userEmail = '';
let userPin = '';
let pingInterval = null;
let autoReconnect = true;
let lastHandledDocId = null;
let lastHandledTime = 0;

// DOM Elements
const loginContainer = document.getElementById('login-container');
const syncContainer = document.getElementById('sync-container');
const userEmailInput = document.getElementById('user-email');
const userPinInput = document.getElementById('user-pin');
const connectBtn = document.getElementById('connect-btn');
const disconnectBtn = document.getElementById('disconnect-btn');

const syncBadge = document.getElementById('sync-badge');
const activeUserDisplay = document.getElementById('active-user-display');
const autoInsertToggle = document.getElementById('auto-insert-toggle');
const incomingTextPreview = document.getElementById('incoming-text-preview');
const insertManualBtn = document.getElementById('insert-manual-btn');

// Office.js Initialization
Office.onReady((info) => {
    if (info.host === Office.HostType.Word) {
        console.log("Office.js is ready!");
        
        // Auto-load previous login email & PIN if exists
        const savedEmail = localStorage.getItem('tehsil_sync_email');
        const savedPin = localStorage.getItem('tehsil_sync_pin') || '';
        if (savedEmail) {
            userEmailInput.value = savedEmail;
            if (userPinInput) userPinInput.value = savedPin;
            connectSync(savedEmail, savedPin);
        }
    }
});

// Event Listeners
connectBtn.addEventListener('click', () => {
    const email = userEmailInput.value.trim().toLowerCase();
    const pin = userPinInput ? userPinInput.value.trim() : '';
    if (!email) {
        alert("कृपया एक वैध ईमेल आईडी दर्ज करें।");
        return;
    }
    if (!email.includes('@')) {
        alert("ईमेल आईडी अमान्य है।");
        return;
    }
    localStorage.setItem('tehsil_sync_email', email);
    localStorage.setItem('tehsil_sync_pin', pin);
    autoReconnect = true;
    connectSync(email, pin);
});

disconnectBtn.addEventListener('click', () => {
    autoReconnect = false;
    disconnectSync();
});

insertManualBtn.addEventListener('click', () => {
    const text = incomingTextPreview.value;
    if (text) {
        insertTextIntoWord(text);
    }
});

// Connect to WebSocket Server
function connectSync(email, pin = '') {
    userEmail = email;
    userPin = pin;
    activeUserDisplay.innerText = email;
    
    updateBadgeStatus('connecting');
    loginContainer.classList.add('hidden');
    syncContainer.classList.remove('hidden');
    
    // Connect WebSocket
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const pinParam = userPin ? `?pin=${encodeURIComponent(userPin)}` : '';
    const wsUrl = `${protocol}//${window.location.host}/ws/desktop/${encodeURIComponent(email)}${pinParam}`;
    
    try {
        ws = new WebSocket(wsUrl);
        
        ws.onopen = () => {
            console.log("WebSocket connected!");
            updateBadgeStatus('connected');
            
            // Setup Keepalive Ping (every 20s) to keep local connections alive
            if (pingInterval) clearInterval(pingInterval);
            pingInterval = setInterval(() => {
                if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send("ping");
                }
            }, 20000);
        };
        
        ws.onmessage = (event) => {
            // Check for pong
            if (event.data === 'pong') return;
            
            try {
                const message = JSON.parse(event.data);
                
                if (message.event === 'transcription_ready' || message.event === 'open_in_word') {
                    const docId = message.doc_id;
                    const now = Date.now();
                    // Prevent duplicate execution if server sends both events for the same document within 2.5s window
                    if (docId && docId === lastHandledDocId && (now - lastHandledTime < 2500)) {
                        return;
                    }
                    if (docId) {
                        lastHandledDocId = docId;
                        lastHandledTime = now;
                    }

                    const text = message.text || '';
                    if (text) {
                        incomingTextPreview.value = text;
                        insertManualBtn.removeAttribute('disabled');
                        
                        // Auto-insert into active Word document if toggle is checked
                        if (autoInsertToggle && autoInsertToggle.checked) {
                            insertTextIntoWord(text);
                        }
                    }
                }
            } catch (err) {
                console.error("Failed to parse websocket message:", err);
            }
        };
        
        ws.onclose = () => {
            console.log("WebSocket disconnected!");
            updateBadgeStatus('disconnected');
            if (pingInterval) clearInterval(pingInterval);
            
            // Auto reconnect logic
            if (autoReconnect) {
                setTimeout(() => {
                    if (autoReconnect) {
                        console.log("Attempting to reconnect...");
                        connectSync(userEmail, userPin);
                    }
                }, 3000);
            }
        };
        
        ws.onerror = (error) => {
            console.error("WebSocket error:", error);
            updateBadgeStatus('disconnected');
        };
        
    } catch (e) {
        console.error("Failed to establish websocket connection:", e);
        updateBadgeStatus('disconnected');
    }
}

// Disconnect from WebSocket Server
function disconnectSync() {
    if (ws) {
        ws.close();
        ws = null;
    }
    if (pingInterval) {
        clearInterval(pingInterval);
        pingInterval = null;
    }
    updateBadgeStatus('disconnected');
    loginContainer.classList.remove('hidden');
    syncContainer.classList.add('hidden');
    incomingTextPreview.value = '';
    insertManualBtn.setAttribute('disabled', 'true');
}

// Update Sync Badge UI Status
function updateBadgeStatus(status) {
    if (status === 'connected') {
        syncBadge.className = "text-[10px] font-bold px-2 py-0.5 rounded-full flex items-center bg-emerald-100 text-emerald-800 border border-emerald-200";
        syncBadge.innerHTML = `<span class="h-1.5 w-1.5 bg-emerald-500 rounded-full mr-1"></span><span>Connected</span>`;
    } else if (status === 'connecting') {
        syncBadge.className = "text-[10px] font-bold px-2 py-0.5 rounded-full flex items-center bg-amber-100 text-amber-800 border border-amber-200";
        syncBadge.innerHTML = `<span class="h-1.5 w-1.5 bg-amber-500 rounded-full animate-ping mr-1"></span><span>Connecting</span>`;
    } else {
        syncBadge.className = "text-[10px] font-bold px-2 py-0.5 rounded-full flex items-center bg-rose-100 text-rose-700 border border-rose-200";
        syncBadge.innerHTML = `<span class="h-1.5 w-1.5 bg-red-500 rounded-full mr-1"></span><span>Offline</span>`;
    }
}

// Insert Text into MS Word using Office JS API
function insertTextIntoWord(text) {
    Word.run(async (context) => {
        // Access the current selection/cursor position in Word
        const selection = context.document.getSelection();
        
        // Insert the text at the cursor position
        selection.insertText(text, Word.InsertLocation.replace);
        
        // Sync document changes
        await context.sync();
        console.log("Successfully inserted text into Word document.");
    }).catch((err) => {
        console.error("MS Word insertion error:", err);
    });
}
