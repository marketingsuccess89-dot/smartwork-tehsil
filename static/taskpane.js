// State Variables
let ws = null;
let userEmail = '';
let pingInterval = null;
let autoReconnect = true;

// DOM Elements
const loginContainer = document.getElementById('login-container');
const syncContainer = document.getElementById('sync-container');
const userEmailInput = document.getElementById('user-email');
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
        // Office is ready and host is MS Word
        console.log("Office.js is ready!");
        
        // Auto-load previous login email if exists
        const savedEmail = localStorage.getItem('tehsil_sync_email');
        if (savedEmail) {
            userEmailInput.value = savedEmail;
            connectSync(savedEmail);
        }
    }
});

// Event Listeners
connectBtn.addEventListener('click', () => {
    const email = userEmailInput.value.trim().toLowerCase();
    if (!email) {
        alert("कृपया एक वैध ईमेल आईडी दर्ज करें।");
        return;
    }
    // Simple email validation
    if (!email.includes('@')) {
        alert("ईमेल आईडी अमान्य है।");
        return;
    }
    localStorage.setItem('tehsil_sync_email', email);
    autoReconnect = true;
    connectSync(email);
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
function connectSync(email) {
    userEmail = email;
    activeUserDisplay.innerText = email;
    
    updateBadgeStatus('connecting');
    loginContainer.classList.add('hidden');
    syncContainer.classList.remove('hidden');
    
    // Connect WebSocket
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws/desktop/${encodeURIComponent(email)}`;
    
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
                
                if (message.event === 'transcription_ready') {
                    const text = message.text;
                    incomingTextPreview.value = text;
                    insertManualBtn.removeAttribute('disabled');
                    
                    // Auto-insert if checked
                    if (autoInsertToggle.checked) {
                        insertTextIntoWord(text);
                    }
                } else if (message.event === 'open_in_word') {
                    const docId = message.doc_id;
                    incomingTextPreview.value = `📄 नया दस्तावेज़ (ID: ${docId}) प्राप्त हुआ!\n\nफ़ाइल डाउनलोड हो रही है...`;
                    insertManualBtn.removeAttribute('disabled');
                    // Automatically trigger download of pristine .docx
                    window.location.href = `/d/${docId}`;
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
                        connectSync(userEmail);
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
        syncBadge.className = "text-[10px] font-bold px-2 py-0.5 rounded-full flex items-center bg-emerald-100 text-emerald-850 border border-emerald-200 text-emerald-700";
        syncBadge.innerHTML = `<span class="h-1.5 w-1.5 bg-emerald-500 rounded-full mr-1"></span><span>Connected</span>`;
    } else if (status === 'connecting') {
        syncBadge.className = "text-[10px] font-bold px-2 py-0.5 rounded-full flex items-center bg-amber-100 text-amber-800 border border-amber-200";
        syncBadge.innerHTML = `<span class="h-1.5 w-1.5 bg-amber-500 rounded-full animate-ping mr-1"></span><span>Connecting</span>`;
    } else {
        syncBadge.className = "text-[10px] font-bold px-2 py-0.5 rounded-full flex items-center bg-red-105 text-red-800 border border-red-200 bg-red-100 text-red-750";
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
