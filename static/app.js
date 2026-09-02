// State Variables
let activeTab = 'image'; // 'image' or 'audio'
let selectedImageFile = null;
let selectedAudioFile = null;
let mediaRecorder = null;
let audioChunks = [];
let recordStartTime = null;
let recordDurationTimer = null;
let isRecording = false;

// Editor Settings State (Default Zoomed Out for True A4 Print Preview)
let currentFontSize = (typeof window !== 'undefined' && window.innerWidth < 640) ? 9.5 : 10.5;

// Sync Variables
let mobileUserEmail = '';
let checkSyncStatusInterval = null;
let isDesktopConnected = false;

// DOM Elements
const tabImageBtn = document.getElementById('tab-image');
const tabAudioBtn = document.getElementById('tab-audio');
const panelImage = document.getElementById('panel-image');
const panelAudio = document.getElementById('panel-audio');

const dropZone = document.getElementById('drop-zone');
const cameraInput = document.getElementById('camera-input');
const fileInput = document.getElementById('file-input');
const imagePreviewContainer = document.getElementById('image-preview-container');
const imagePreview = document.getElementById('image-preview');
const removeImageBtn = document.getElementById('remove-image');

const recordBtn = document.getElementById('record-btn');
const recordIcon = document.getElementById('record-icon');
const recordRing = document.getElementById('record-ring');
const recordRing2 = document.getElementById('record-ring-2');
const recordTimer = document.getElementById('record-timer');
const recordStatus = document.getElementById('record-status');
const audioInput = document.getElementById('audio-input');
const audioPreviewContainer = document.getElementById('audio-preview-container');
const audioPreview = document.getElementById('audio-preview');
const removeAudioBtn = document.getElementById('remove-audio');

const mobileSyncBadge = document.getElementById('mobile-sync-badge');
const mobileLoginSection = document.getElementById('mobile-login-section');
const mobileActiveSection = document.getElementById('mobile-active-section');
const mobileUserEmailInput = document.getElementById('mobile-user-email');
const mobileLoginBtn = document.getElementById('mobile-login-btn');
const mobileLogoutBtn = document.getElementById('mobile-logout-btn');

const documentEditor = document.getElementById('document-editor');
const documentPreview = document.getElementById('document-preview');
const previewContent = document.getElementById('preview-content');
const previewPlaceholder = document.getElementById('preview-placeholder');
const wordCountBadge = document.getElementById('word-count-badge');
const fontIncreaseBtn = document.getElementById('font-increase-btn');
const fontDecreaseBtn = document.getElementById('font-decrease-btn');
const pageNavBar = document.getElementById('page-nav-bar');
const prevPageBtn = document.getElementById('prev-page-btn');
const nextPageBtn = document.getElementById('next-page-btn');
const pageIndicator = document.getElementById('page-indicator');
const stampPaperHeader = document.getElementById('stamp-paper-header');
const stampPaperToggle = document.getElementById('stamp-paper-toggle');
const downloadStampInput = document.getElementById('download-stamp-input');

const loadingOverlay = document.getElementById('loading-overlay');
const processBtn = document.getElementById('process-btn');
const processBtnText = document.getElementById('process-btn-text');
const downloadDocxBtn = document.getElementById('download-docx-btn');
const copyBtn = document.getElementById('copy-btn');
const clearBtn = document.getElementById('clear-btn');

const toggleHistoryBtn = document.getElementById('toggle-history');
const closeHistoryBtn = document.getElementById('close-history');
const historySidebar = document.getElementById('history-sidebar');
const sidebarBackdrop = document.getElementById('sidebar-backdrop');
const historyList = document.getElementById('history-list');
const historyEmpty = document.getElementById('history-empty');
const clearHistoryBtn = document.getElementById('clear-history');

const toast = document.getElementById('toast');
const toastIcon = document.getElementById('toast-icon');
const toastMessage = document.getElementById('toast-message');

// Initialize Application
document.addEventListener('DOMContentLoaded', () => {
    loadHistory();
    setupEventListeners();
    updateCounters();
    
    // Load previously linked sync email
    const savedMobileEmail = localStorage.getItem('tehsil_mobile_email');
    if (savedMobileEmail) {
        linkMobileEmail(savedMobileEmail);
    }
});

// Setup Event Listeners
function setupEventListeners() {
    // 1. Tabs Switcher (Turns Active Tab Rich Green)
    if (tabImageBtn) tabImageBtn.addEventListener('click', () => switchTab('image'));
    if (tabAudioBtn) tabAudioBtn.addEventListener('click', () => switchTab('audio'));

    // 2. Camera Direct Hardware Capture Listener
    if (cameraInput) {
        cameraInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                handleImageSelection(e.target.files[0]);
            }
        });
    }

    // 3. Drop Zone & Gallery/File Upload
    if (dropZone && fileInput) {
        dropZone.addEventListener('click', () => {
            fileInput.click();
        });
        fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                handleImageSelection(e.target.files[0]);
            }
        });
        dropZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            dropZone.classList.add('border-emerald-500', 'bg-emerald-50/40', 'scale-[1.01]');
        });
        dropZone.addEventListener('dragleave', () => {
            dropZone.classList.remove('border-emerald-500', 'bg-emerald-50/40', 'scale-[1.01]');
        });
        dropZone.addEventListener('drop', (e) => {
            e.preventDefault();
            dropZone.classList.remove('border-emerald-500', 'bg-emerald-50/40', 'scale-[1.01]');
            if (e.dataTransfer.files.length > 0) {
                handleImageSelection(e.dataTransfer.files[0]);
            }
        });
    }

    if (removeImageBtn) {
        removeImageBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            clearImageSelection();
        });
    }

    // 4. Voice Recording Controls
    if (recordBtn) {
        recordBtn.addEventListener('click', toggleRecording);
    }
    if (removeAudioBtn) {
        removeAudioBtn.addEventListener('click', clearAudioSelection);
    }
    if (audioInput) {
        audioInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                handleAudioSelection(e.target.files[0]);
            }
        });
    }

    // 5. Desktop Sync Handlers
    if (mobileLoginBtn) {
        mobileLoginBtn.addEventListener('click', () => {
            const email = mobileUserEmailInput.value.trim().toLowerCase();
            if (!email || !email.includes('@')) {
                showToast('error', 'कृपया एक वैध ईमेल आईडी दर्ज करें।');
                return;
            }
            localStorage.setItem('tehsil_mobile_email', email);
            linkMobileEmail(email);
        });
    }
    if (mobileLogoutBtn) {
        mobileLogoutBtn.addEventListener('click', unlinkMobileEmail);
    }

    // 6. Editor Actions & Live Counters
    if (documentEditor) {
        documentEditor.addEventListener('input', updateCounters);
    }

    if (prevPageBtn) {
        prevPageBtn.addEventListener('click', () => {
            if (currentPageIndex > 0) {
                currentPageIndex--;
                renderCurrentPage();
            }
        });
    }

    if (nextPageBtn) {
        nextPageBtn.addEventListener('click', () => {
            if (currentPageIndex < documentPages.length - 1) {
                currentPageIndex++;
                renderCurrentPage();
            }
        });
    }

    if (stampPaperToggle) {
        stampPaperToggle.addEventListener('change', () => {
            if (downloadStampInput) {
                downloadStampInput.value = stampPaperToggle.checked ? 'true' : 'false';
            }
            if (documentEditor && documentEditor.value) {
                paginateDocument(documentEditor.value);
                renderCurrentPage();
            }
        });
    }

    if (fontIncreaseBtn) {
        fontIncreaseBtn.addEventListener('click', () => {
            if (currentFontSize < 18) {
                currentFontSize += 1;
                if (documentEditor && documentEditor.value) {
                    paginateDocument(documentEditor.value);
                    renderCurrentPage();
                }
            }
        });
    }

    if (fontDecreaseBtn) {
        fontDecreaseBtn.addEventListener('click', () => {
            if (currentFontSize > 9) {
                currentFontSize -= 1;
                if (documentEditor && documentEditor.value) {
                    paginateDocument(documentEditor.value);
                    renderCurrentPage();
                }
            }
        });
    }

    if (processBtn) {
        processBtn.addEventListener('click', () => {
            if (activeTab === 'image' && !selectedImageFile) {
                showToast('error', 'कृपया पहले फ़ोटो खींचें या फाइल अपलोड करें।');
                return;
            }
            if (activeTab === 'audio' && !selectedAudioFile) {
                showToast('error', 'कृपया पहले बोलकर रिकॉर्ड करें या ऑडियो चुनें।');
                return;
            }
            processWithAI(activeTab);
        });
    }

    if (copyBtn) copyBtn.addEventListener('click', copyToClipboard);
    if (clearBtn) clearBtn.addEventListener('click', clearEditor);

    // 7. Native Download Form Handler (100% Mobile & PC Native Stream)
    const downloadForm = document.getElementById('download-form');
    const downloadTextInput = document.getElementById('download-text-input');
    if (downloadForm) {
        downloadForm.addEventListener('submit', (e) => {
            const text = documentEditor ? documentEditor.value.trim() : '';
            if (!text) {
                e.preventDefault();
                showToast('error', 'डाउनलोड करने के लिए पहले दस्तावेज़ तैयार करें।');
                return;
            }
            if (downloadTextInput) {
                downloadTextInput.value = text;
            }
            showToast('success', 'Word फ़ाइल डाउनलोड शुरू हो गई!');
            // Open WhatsApp Share Modal
            setTimeout(() => {
                openModal('modal-share');
            }, 600);
        });
    }

    // 8. History Sidebar Controls
    if (toggleHistoryBtn) toggleHistoryBtn.addEventListener('click', openHistorySidebar);
    if (closeHistoryBtn) closeHistoryBtn.addEventListener('click', closeHistorySidebar);
    if (sidebarBackdrop) sidebarBackdrop.addEventListener('click', closeHistorySidebar);
    if (clearHistoryBtn) clearHistoryBtn.addEventListener('click', clearAllHistory);

    // 9. WhatsApp Share Modal Controls
    const whatsappShareBtn = document.getElementById('whatsapp-share-btn');
    if (whatsappShareBtn) {
        whatsappShareBtn.addEventListener('click', shareOnWhatsApp);
    }
    const whatsappCopyBtn = document.getElementById('whatsapp-copy-btn');
    if (whatsappCopyBtn) {
        whatsappCopyBtn.addEventListener('click', () => {
            copyToClipboard();
            showToast('success', 'टेक्स्ट कॉपी हो गया! अब WhatsApp में पेस्ट करें।');
        });
    }
    const redownloadBtn = document.getElementById('redownload-btn');
    if (redownloadBtn) {
        redownloadBtn.addEventListener('click', () => {
            if (downloadForm) downloadForm.requestSubmit ? downloadForm.requestSubmit() : downloadForm.submit();
        });
    }
}

// Live Word & Character Counter
function updateCounters() {
    if (!wordCountBadge || !documentEditor) return;
    const text = documentEditor.value.trim();
    const words = text ? text.split(/\s+/).filter(Boolean).length : 0;
    const chars = text.length;
    wordCountBadge.innerText = `${words} Words • ${chars} Chars`;

    if (downloadDocxBtn) {
        if (text.length > 0) {
            downloadDocxBtn.removeAttribute('disabled');
        } else {
            downloadDocxBtn.setAttribute('disabled', 'true');
        }
    }
}

// Client-side image compression for ultra-fast mobile and desktop uploads
async function compressImageClientSide(file, maxDimension = 1280, quality = 0.75) {
    if (!file || !file.type.startsWith('image/') || file.type === 'image/gif' || file.type === 'image/svg+xml') {
        return file;
    }

    return new Promise((resolve) => {
        const img = new Image();
        const reader = new FileReader();

        reader.onload = (e) => {
            img.onload = () => {
                let width = img.width;
                let height = img.height;

                if (width > maxDimension || height > maxDimension) {
                    if (width > height) {
                        height = Math.round((height * maxDimension) / width);
                        width = maxDimension;
                    } else {
                        width = Math.round((width * maxDimension) / height);
                        height = maxDimension;
                    }
                }

                const canvas = document.createElement('canvas');
                canvas.width = width;
                canvas.height = height;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(img, 0, 0, width, height);

                canvas.toBlob((blob) => {
                    if (blob && blob.size < file.size) {
                        const compressedFile = new File([blob], file.name.replace(/\.[^/.]+$/, ".jpg"), {
                            type: 'image/jpeg',
                            lastModified: Date.now()
                        });
                        console.log(`Compressed from ${(file.size/1024).toFixed(1)}KB to ${(blob.size/1024).toFixed(1)}KB`);
                        resolve(compressedFile);
                    } else {
                        resolve(file);
                    }
                }, 'image/jpeg', quality);
            };
            img.onerror = () => resolve(file);
            img.src = e.target.result;
        };
        reader.onerror = () => resolve(file);
        reader.readAsDataURL(file);
    });
}

// Switch Tabs (Image / Voice) - Selected tab turns Rich Green
function switchTab(tab) {
    activeTab = tab;
    if (tab === 'image') {
        tabImageBtn.className = "w-full flex justify-center items-center py-2.5 px-4 rounded-xl text-xs font-bold transition-all duration-200 bg-emerald-700 text-white shadow-md shadow-emerald-700/20";
        tabAudioBtn.className = "w-full flex justify-center items-center py-2.5 px-4 rounded-xl text-xs font-semibold transition-all duration-200 text-slate-600 hover:text-emerald-900 hover:bg-emerald-50/50";
        panelImage.classList.remove('hidden');
        panelAudio.classList.add('hidden');
    } else {
        tabAudioBtn.className = "w-full flex justify-center items-center py-2.5 px-4 rounded-xl text-xs font-bold transition-all duration-200 bg-emerald-700 text-white shadow-md shadow-emerald-700/20";
        tabImageBtn.className = "w-full flex justify-center items-center py-2.5 px-4 rounded-xl text-xs font-semibold transition-all duration-200 text-slate-600 hover:text-emerald-900 hover:bg-emerald-50/50";
        panelAudio.classList.remove('hidden');
        panelImage.classList.add('hidden');
    }
}

// Handle Image Selection & Auto-start Smart Typing
async function handleImageSelection(file) {
    if (!file.type.startsWith('image/')) {
        showToast('error', 'कृपया केवल इमेज फाइल ही अपलोड करें।');
        return;
    }

    // Fast client-side compression to avoid 50s network delay
    const optimizedFile = await compressImageClientSide(file);
    selectedImageFile = optimizedFile;
    selectedAudioFile = null;

    const reader = new FileReader();
    reader.onload = (e) => {
        imagePreview.src = e.target.result;
        imagePreviewContainer.classList.remove('hidden');
        dropZone.classList.add('hidden');
    };
    reader.readAsDataURL(optimizedFile);

    // Instant Smart Typing
    processWithAI('image');
}

function clearImageSelection() {
    selectedImageFile = null;
    if (cameraInput) cameraInput.value = '';
    if (fileInput) fileInput.value = '';
    imagePreview.src = '#';
    imagePreviewContainer.classList.add('hidden');
    dropZone.classList.remove('hidden');
}

// Handle Audio Selection & Auto-start Smart Typing
function handleAudioSelection(file) {
    selectedAudioFile = file;
    selectedImageFile = null;
    audioPreview.src = URL.createObjectURL(file);
    audioPreviewContainer.classList.remove('hidden');

    // Instant Smart Typing
    processWithAI('audio');
}

function clearAudioSelection() {
    selectedAudioFile = null;
    audioInput.value = '';
    audioPreview.src = '';
    audioPreviewContainer.classList.add('hidden');
}

// Voice Recording Logic with Zoom In-Out Animation
async function toggleRecording() {
    if (!isRecording) {
        await startRecording();
    } else {
        stopRecording();
    }
}

async function startRecording() {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        audioChunks = [];
        
        let options = {};
        let recordedMime = 'audio/webm';
        let ext = 'webm';
        
        if (MediaRecorder.isTypeSupported('audio/webm')) {
            options = { mimeType: 'audio/webm' };
            recordedMime = 'audio/webm';
            ext = 'webm';
        } else if (MediaRecorder.isTypeSupported('audio/mp4')) {
            options = { mimeType: 'audio/mp4' };
            recordedMime = 'audio/mp4';
            ext = 'm4a';
        } else if (MediaRecorder.isTypeSupported('audio/ogg')) {
            options = { mimeType: 'audio/ogg' };
            recordedMime = 'audio/ogg';
            ext = 'ogg';
        } else {
            recordedMime = 'audio/wav';
            ext = 'wav';
        }
        
        mediaRecorder = new MediaRecorder(stream, options);
        
        mediaRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                audioChunks.push(event.data);
            }
        };

        mediaRecorder.onstop = () => {
            const audioBlob = new Blob(audioChunks, { type: recordedMime });
            const file = new File([audioBlob], `dictation_audio.${ext}`, { type: recordedMime });
            handleAudioSelection(file);
        };

        mediaRecorder.start();
        isRecording = true;
        recordStartTime = Date.now();
        if (recordRing) recordRing.classList.remove('hidden');
        if (recordRing2) recordRing2.classList.remove('hidden');
        if (recordIcon) recordIcon.className = 'fa-solid fa-stop text-2xl animate-pulse';
        if (recordStatus) recordStatus.innerText = 'रिकॉर्डिंग चालू है... बोलना जारी रखें';
        
        recordDurationTimer = setInterval(() => {
            const elapsed = Math.floor((Date.now() - recordStartTime) / 1000);
            const minutes = String(Math.floor(elapsed / 60)).padStart(2, '0');
            const seconds = String(elapsed % 60).padStart(2, '0');
            if (recordTimer) recordTimer.innerText = `${minutes}:${seconds}`;
        }, 1000);

    } catch (err) {
        console.error('Recording error:', err);
        showToast('error', 'माइक्रोफोन एक्सेस करने में समस्या हुई। कृपया अनुमति दें।');
    }
}

function stopRecording() {
    if (!mediaRecorder || !isRecording) return;
    
    mediaRecorder.stop();
    mediaRecorder.stream.getTracks().forEach(track => track.stop());
    
    isRecording = false;
    clearInterval(recordDurationTimer);
    if (recordTimer) recordTimer.innerText = '00:00';
    if (recordRing) recordRing.classList.add('hidden');
    if (recordRing2) recordRing2.classList.add('hidden');
    if (recordIcon) recordIcon.className = 'fa-solid fa-microphone text-2xl';
    if (recordStatus) recordStatus.innerText = 'रिकॉर्डिंग समाप्त। Smart Typing शुरू हो रही है...';
}

// Process Document through FastAPI
async function processWithAI(mode) {
    const formData = new FormData();
    let url = '';

    if (mode === 'image' || selectedImageFile) {
        if (!selectedImageFile) return;
        formData.append('file', selectedImageFile);
        url = '/api/process-image';
    } else {
        if (!selectedAudioFile) return;
        formData.append('file', selectedAudioFile);
        url = '/api/process-audio';
    }

    if (mobileUserEmail) {
        formData.append('user_id', mobileUserEmail);
    }

    // Show Loading Overlay and Button State
    if (loadingOverlay) loadingOverlay.classList.remove('hidden');
    if (processBtn && processBtnText) {
        processBtn.setAttribute('disabled', 'true');
        processBtnText.innerHTML = `<span class="flex items-center justify-center"><div class="h-4 w-4 border-2 border-white border-t-transparent rounded-full animate-spin mr-2"></div>दस्तावेज़ तैयार हो रहा है...</span>`;
    }

    try {
        const response = await fetch(url, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.detail || 'सर्वर प्रोसेसिंग में त्रुटि हुई।');
        }

        const data = await response.json();
        
        // Populate document editor & A4 Preview
        if (documentEditor) {
            documentEditor.value = data.transcribed_text;
            updateCounters();
        }
        if (documentPreview) {
            paginateDocument(data.transcribed_text);
            renderCurrentPage();
        }
        if (downloadDocxBtn) {
            downloadDocxBtn.removeAttribute('disabled');
        }
        
        // Save to History
        saveToHistory(data);
        showToast('success', 'Smart Typing द्वारा दस्तावेज़ तैयार कर लिया गया!');

    } catch (err) {
        console.error(err);
        showToast('error', err.message || 'दस्तावेज़ प्रोसेस करने में असमर्थ।');
    } finally {
        if (loadingOverlay) loadingOverlay.classList.add('hidden');
        if (processBtn && processBtnText) {
            processBtn.removeAttribute('disabled');
            processBtnText.innerHTML = `दस्तावेज़ तैयार करें (Start Smart Typing)`;
        }
    }
}

// Download MS Word Document (.docx)
function downloadWordDocument() {
    const text = documentEditor ? documentEditor.value : '';

    if (!text.trim()) {
        showToast('error', 'डाउनलोड करने के लिए कोई टेक्स्ट नहीं है।');
        return;
    }

    const fileName = `Smart_Typing_Document_${Date.now()}.docx`;

    // 1. Direct Form Download: Native browser stream download (100% reliable across mobile & PC)
    triggerDirectFormDownload(text, fileName);

    // 2. Immediately open the WhatsApp Share Modal
    setTimeout(() => {
        openModal('modal-share');
    }, 500);
}

// Direct form download for seamless native downloading across all platforms
function triggerDirectFormDownload(text, fileName) {
    try {
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = '/api/download-docx';
        form.style.display = 'none';

        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = 'text';
        input.value = text;
        form.appendChild(input);

        document.body.appendChild(form);
        form.submit();
        
        setTimeout(() => {
            if (document.body.contains(form)) {
                document.body.removeChild(form);
            }
        }, 3000);
        showToast('success', 'Word फ़ाइल डाउनलोड शुरू हो गई!');
    } catch (e) {
        console.error('Download form error:', e);
        showToast('error', 'फ़ाइल डाउनलोड करने में असमर्थ।');
    }
}

// Modal Dialog Helpers
function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) modal.classList.remove('hidden');
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) modal.classList.add('hidden');
}
window.openModal = openModal;
window.closeModal = closeModal;

// WhatsApp File Share Handler (Directly launches WhatsApp / WhatsApp Business app)
async function shareOnWhatsApp() {
    const text = documentEditor ? documentEditor.value.trim() : '';
    if (!text) {
        showToast('error', 'शेयर करने के लिए कोई टेक्स्ट नहीं है।');
        return;
    }

    const isMobile = /Android|iPhone|iPad|iPod/i.test(navigator.userAgent);
    const whatsappShareBtn = document.getElementById('whatsapp-share-btn');
    const whatsappShareBtnText = document.getElementById('whatsapp-share-btn-text');
    const originalText = whatsappShareBtnText ? whatsappShareBtnText.innerText : 'Word (.DOCX) फ़ाइल WhatsApp पर भेजें';

    if (whatsappShareBtn) {
        whatsappShareBtn.setAttribute('disabled', 'true');
        if (whatsappShareBtnText) {
            whatsappShareBtnText.innerText = 'WhatsApp खुल रहा है...';
        }
    }

    try {
        const isStamp = Boolean(stampPaperToggle && stampPaperToggle.checked);
        
        // 1. Try Native File Share if browser supports it (HTTPS / Secure Context)
        if (navigator.canShare) {
            try {
                const response = await fetch('/api/generate-docx', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text, stamp_paper: isStamp })
                });

                if (response.ok) {
                    const blob = await response.blob();
                    const fileName = `Smart_Typing_Document_${Date.now()}.docx`;
                    const docxFile = new File(
                        [blob], 
                        fileName, 
                        { type: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document' }
                    );

                    if (navigator.canShare({ files: [docxFile] })) {
                        await navigator.share({
                            files: [docxFile],
                            title: fileName
                        });
                        showToast('success', 'Word फ़ाइल WhatsApp पर भेजी गई!');
                        return;
                    }
                }
            } catch (shareErr) {
                if (shareErr.name === 'AbortError') return;
                console.log('Native file share failed, falling back to app intent:', shareErr);
            }
        }

        // 2. WAY 4 (Integrated Fallback): Generate Instant 1-Click .DOCX Download Link for WhatsApp
        let shareLink = window.location.href;
        try {
            const linkRes = await fetch('/api/create-share-link', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text, stamp_paper: isStamp })
            });
            if (linkRes.ok) {
                const linkData = await linkRes.json();
                shareLink = `${window.location.origin}/d/${linkData.doc_id}`;
            }
        } catch (e) {
            console.error('Share link generation error:', e);
        }

        const whatsappMessage = `📄 *तहसील विलेख / दस्तावेज़ (MS Word .docx फ़ाइल)*\n\nनमस्ते, आपके लिए तैयार किया गया MS Word (.docx) दस्तावेज़ सीधे यहाँ क्लिक करके डाउनलोड करें:\n👉 ${shareLink}`;

        if (isMobile) {
            showToast('success', 'WhatsApp Business खोला जा रहा है...');
            // Directly triggers native WhatsApp / WhatsApp Business app on Android & iOS
            window.location.href = `whatsapp://send?text=${encodeURIComponent(whatsappMessage)}`;
        } else {
            // Desktop fallback: Open WhatsApp Web
            showToast('info', 'Word फ़ाइल Downloads में है। WhatsApp Web खोला जा रहा है...');
            window.open(`https://web.whatsapp.com/send?text=${encodeURIComponent(whatsappMessage)}`, '_blank');
        }
    } catch (err) {
        console.error('File share error:', err);
        showToast('error', 'WhatsApp खोलने में असमर्थ।');
    } finally {
        if (whatsappShareBtn) {
            whatsappShareBtn.removeAttribute('disabled');
            if (whatsappShareBtnText) {
                whatsappShareBtnText.innerText = originalText;
            }
        }
    }
}

// Copy to Clipboard with Full Formatting (Rich Text HTML for MS Word + Plain Text fallback)
async function copyToClipboard() {
    const text = documentEditor ? documentEditor.value : '';
    if (!text || !text.trim()) {
        showToast('error', 'कॉपी करने के लिए कोई टेक्स्ट नहीं है।');
        return;
    }

    try {
        const formattedHtml = convertTextToWordHtml(text);
        const blobHtml = new Blob([formattedHtml], { type: 'text/html' });
        const blobText = new Blob([text], { type: 'text/plain' });

        if (navigator.clipboard && navigator.clipboard.write && window.ClipboardItem) {
            const clipboardItem = new ClipboardItem({
                'text/html': blobHtml,
                'text/plain': blobText
            });
            await navigator.clipboard.write([clipboardItem]);
            showToast('success', 'फॉर्मेटेड टेक्स्ट कॉपी हुआ! MS Word में Paste (Ctrl+V) करें।');
        } else {
            await navigator.clipboard.writeText(text);
            showToast('success', 'टेक्स्ट क्लिपबोर्ड पर कॉपी किया गया!');
        }
    } catch (err) {
        console.error('Clipboard copy error:', err);
        try {
            await navigator.clipboard.writeText(text);
            showToast('success', 'टेक्स्ट कॉपी किया गया!');
        } catch (e) {
            showToast('error', 'कॉपी करने में त्रुटि हुई।');
        }
    }
}

// Clear Workspace / Preview
function clearEditor() {
    if (confirm('क्या आप प्रीव्यू साफ़ करना चाहते हैं?')) {
        if (documentEditor) {
            documentEditor.value = '';
            updateCounters();
        }
        documentPages = [];
        currentPageIndex = 0;
        renderCurrentPage();
        if (downloadDocxBtn) downloadDocxBtn.setAttribute('disabled', 'true');
        showToast('success', 'वर्कस्पेस साफ़ किया गया।');
    }
}

// Toast Notifications in Rich Emerald Theme
function showToast(type, message) {
    if (!toast || !toastMessage) return;
    toastMessage.innerText = message;
    
    if (type === 'success') {
        toast.className = 'fixed bottom-6 right-6 bg-[#06281e] text-emerald-300 text-xs font-semibold py-3 px-5 rounded-xl shadow-2xl flex items-center space-x-2.5 transition duration-300 z-50 transform translate-y-0 opacity-100 border border-emerald-600/50';
        toastIcon.innerHTML = '<i class="fa-solid fa-circle-check text-emerald-400"></i>';
    } else {
        toast.className = 'fixed bottom-6 right-6 bg-[#06281e] text-rose-300 text-xs font-semibold py-3 px-5 rounded-xl shadow-2xl flex items-center space-x-2.5 transition duration-300 z-50 transform translate-y-0 opacity-100 border border-rose-600/50';
        toastIcon.innerHTML = '<i class="fa-solid fa-circle-exclamation text-rose-400"></i>';
    }

    setTimeout(() => {
        toast.className = 'fixed bottom-6 right-6 bg-[#06281e] text-white text-xs font-semibold py-3 px-5 rounded-xl shadow-xl transform translate-y-20 opacity-0 transition duration-300 z-50 flex items-center space-x-2.5 border border-emerald-900';
    }, 4000);
}

// History Management
function saveToHistory(data) {
    let history = JSON.parse(localStorage.getItem('smart_typing_history') || '[]');
    const newItem = {
        id: Date.now(),
        date: new Date().toLocaleString('hi-IN'),
        transcribed_text: data.transcribed_text
    };
    history.unshift(newItem);
    if (history.length > 20) history.pop();
    localStorage.setItem('smart_typing_history', JSON.stringify(history));
    loadHistory();
}

function loadHistory() {
    if (!historyList || !historyEmpty) return;
    let history = JSON.parse(localStorage.getItem('smart_typing_history') || '[]');
    historyList.innerHTML = '';
    
    if (history.length === 0) {
        historyEmpty.classList.remove('hidden');
        return;
    }
    
    historyEmpty.classList.add('hidden');
    
    history.forEach(item => {
        const div = document.createElement('div');
        div.className = 'p-3 border border-emerald-100/80 rounded-xl hover:bg-emerald-50/50 cursor-pointer transition flex flex-col justify-between bg-white text-left shadow-sm';
        const textSnippet = item.transcribed_text.substring(0, 50) + (item.transcribed_text.length > 50 ? '...' : '');
        
        div.innerHTML = `
            <div class="flex justify-between items-center mb-1">
                <span class="text-[10px] text-slate-400 font-semibold font-mono">${item.date}</span>
            </div>
            <p class="text-xs font-semibold text-emerald-950 leading-snug">${textSnippet}</p>
        `;
        
        div.addEventListener('click', () => {
            if (documentEditor) {
                documentEditor.value = item.transcribed_text;
                updateCounters();
            }
            if (documentPreview) {
                paginateDocument(item.transcribed_text);
                renderCurrentPage();
            }
            if (downloadDocxBtn) downloadDocxBtn.removeAttribute('disabled');
            closeHistorySidebar();
            showToast('success', 'इतिहास से दस्तावेज़ रीलोड किया गया!');
        });
        
        historyList.appendChild(div);
    });
}

function clearAllHistory() {
    if (confirm('क्या आप सच में संपूर्ण इतिहास हटाना चाहते हैं?')) {
        localStorage.removeItem('smart_typing_history');
        loadHistory();
        showToast('success', 'इतिहास सफलतापूर्वक साफ़ किया गया।');
    }
}

function openHistorySidebar() {
    if (historySidebar) historySidebar.classList.remove('translate-x-full');
    if (sidebarBackdrop) sidebarBackdrop.classList.remove('hidden');
}

function closeHistorySidebar() {
    if (historySidebar) historySidebar.classList.add('translate-x-full');
    if (sidebarBackdrop) sidebarBackdrop.classList.add('hidden');
}

// Desktop Sync Handlers
function linkMobileEmail(email) {
    mobileUserEmail = email;
    const display = document.getElementById('mobile-email-display');
    if (display) display.innerText = email;
    
    if (mobileLoginSection) mobileLoginSection.classList.add('hidden');
    if (mobileActiveSection) mobileActiveSection.classList.remove('hidden');
    
    checkDesktopSyncStatus();
    
    if (checkSyncStatusInterval) clearInterval(checkSyncStatusInterval);
    checkSyncStatusInterval = setInterval(checkDesktopSyncStatus, 5000);
}

function unlinkMobileEmail() {
    mobileUserEmail = '';
    localStorage.removeItem('tehsil_mobile_email');
    
    if (mobileLoginSection) mobileLoginSection.classList.remove('hidden');
    if (mobileActiveSection) mobileActiveSection.classList.add('hidden');
    if (mobileUserEmailInput) mobileUserEmailInput.value = '';
    
    if (checkSyncStatusInterval) {
        clearInterval(checkSyncStatusInterval);
        checkSyncStatusInterval = null;
    }
    
    isDesktopConnected = false;
    updateMobileSyncBadge(false);
}

async function checkDesktopSyncStatus() {
    if (!mobileUserEmail) return;
    try {
        const response = await fetch(`/api/connection-status/${encodeURIComponent(mobileUserEmail)}`);
        if (response.ok) {
            const data = await response.json();
            isDesktopConnected = data.connected;
            updateMobileSyncBadge(data.connected);
        }
    } catch (err) {
        console.error("Failed to fetch sync status:", err);
    }
}

function updateMobileSyncBadge(connected) {
    if (!mobileSyncBadge) return;
    if (connected) {
        mobileSyncBadge.className = "text-[10px] font-bold px-2.5 py-0.5 rounded-full bg-emerald-50 text-emerald-700 border border-emerald-200";
        mobileSyncBadge.innerHTML = `<span class="inline-block h-1.5 w-1.5 bg-emerald-500 rounded-full mr-1 animate-pulse"></span>Connected`;
    } else {
        mobileSyncBadge.className = "text-[10px] font-bold px-2.5 py-0.5 rounded-full bg-slate-100 text-slate-500 border border-slate-200";
        mobileSyncBadge.innerHTML = `🔴 Offline`;
    }
}

// State for Universal A4 Pages
let documentPages = [];
let currentPageIndex = 0;

// Universal mid-sentence line unwrap for all document types (Zero hardcoded names)
function unwrapParagraphs(text) {
    if (!text) return '';
    const lines = text.split('\n');
    const unwrapped = [];
    let currentP = [];

    for (let line of lines) {
        let stripped = line.trim();
        if (!stripped) {
            if (currentP.length > 0) {
                unwrapped.push(currentP.join(' '));
                currentP = [];
            }
            unwrapped.push('');
            continue;
        }

        const isHeading = stripped.startsWith('#');
        const isBullet = stripped.startsWith('* ') || stripped.startsWith('- ');
        const isTable = stripped.startsWith('|');
        const isNewClause = /^(\d+|[०-९]+)[\.\)]\s+/.test(stripped);
        const isLabelLine = /^[^:\n]{2,30}\s*:\s*.+$/.test(stripped);
        const isFormalBreak = /^(सेवा में|महोदय|महोदया|श्रीमान|मान्यवर|विषय|भवदीय|प्रार्थी|निवेदक|शपथी|हस्ताक्षर|स्थान|दिनांक)/.test(stripped);

        if (isHeading || isBullet || isTable || isNewClause || isLabelLine || isFormalBreak) {
            if (currentP.length > 0) {
                unwrapped.push(currentP.join(' '));
                currentP = [];
            }
            currentP.push(stripped);
        } else {
            if (currentP.length > 0 && 
                !currentP[currentP.length - 1].startsWith('#') && 
                !currentP[currentP.length - 1].startsWith('|') && 
                !/^[^:\n]{2,30}\s*:\s*.+$/.test(currentP[currentP.length - 1]) &&
                !/^(सेवा में|महोदय|महोदया|श्रीमान|मान्यवर|विषय|भवदीय|प्रार्थी|निवेदक|शपथी|हस्ताक्षर)/.test(currentP[currentP.length - 1])) {
                currentP.push(stripped);
            } else {
                if (currentP.length > 0) {
                    unwrapped.push(currentP.join(' '));
                    currentP = [];
                }
                currentP.push(stripped);
            }
        }
    }

    if (currentP.length > 0) {
        unwrapped.push(currentP.join(' '));
    }

    return unwrapped.join('\n');
}

// Convert a single block into formatted HTML
function renderBlockHtml(block) {
    if (block.type === 'title') {
        return `<h1 class="font-bold text-center text-slate-950 mb-2 pb-1 border-b border-slate-300 tracking-wide text-xs sm:text-sm leading-tight">${formatInline(block.raw)}</h1>`;
    }
    if (block.type === 'heading') {
        return `<h2 class="font-bold text-slate-900 mt-2 mb-1 text-xs sm:text-sm">${formatInline(block.raw)}</h2>`;
    }
    if (block.type === 'clause') {
        return `<div class="flex items-start my-1.5 space-x-1.5 text-justify leading-tight">
            <span class="font-bold text-slate-900 shrink-0 select-none">${block.num}.</span>
            <div class="flex-grow text-slate-900 leading-tight text-justify">${formatInline(block.raw)}</div>
        </div>`;
    }
    if (block.type === 'table') {
        const tableRows = [];
        for (let line of block.raw) {
            if (!line.match(/^[\|\s\-:]+$/)) {
                let cells = line.split('|').slice(1, -1).map(c => c.trim());
                tableRows.push(cells);
            }
        }
        if (tableRows.length === 0) return '';
        const cols = Math.max(...tableRows.map(r => r.length));
        let html = '<div class="my-2.5 w-full"><table class="w-full border-collapse">';
        for (let r = 0; r < tableRows.length; r++) {
            html += '<tr>';
            for (let c = 0; c < cols; c++) {
                let cellVal = tableRows[r][c] || '';
                let alignClass = (cols === 2 && c === 1) ? 'text-right' : 'text-left';
                html += `<td class="p-1.5 align-top ${alignClass} text-slate-900">${formatInline(cellVal)}</td>`;
            }
            html += '</tr>';
        }
        html += '</table></div>';
        return html;
    }
    return `<p class="my-1 leading-tight text-justify text-slate-900">${formatInline(block.raw)}</p>`;
}

// Universal A4 Pagination: divides any document across Page 1, Page 2 with ZERO scrolling
function paginateDocument(rawText) {
    if (!rawText || !rawText.trim()) {
        documentPages = [];
        currentPageIndex = 0;
        return;
    }

    const unwrappedText = unwrapParagraphs(rawText);
    const lines = unwrappedText.split('\n');

    // Parse into distinct semantic blocks
    const blocks = [];
    let i = 0;
    while (i < lines.length) {
        let line = lines[i].trim();
        if (!line) {
            i++;
            continue;
        }

        // Markdown Table
        if (line.startsWith('|') && line.endsWith('|')) {
            let tableLines = [];
            while (i < lines.length && lines[i].trim().startsWith('|') && lines[i].trim().endsWith('|')) {
                tableLines.push(lines[i].trim());
                i++;
            }
            blocks.push({ type: 'table', raw: tableLines });
            continue;
        }

        // Title
        if (line.startsWith('# ')) {
            blocks.push({ type: 'title', raw: line.substring(2).trim() });
            i++;
            continue;
        }

        // Section Heading
        if (line.startsWith('## ')) {
            blocks.push({ type: 'heading', raw: line.substring(3).trim() });
            i++;
            continue;
        }

        // Numbered Clause
        let numMatch = line.match(/^(\d+|[०-९]+)[\.\)]\s+(.*)$/);
        if (numMatch) {
            blocks.push({ type: 'clause', num: numMatch[1], raw: numMatch[2] });
            i++;
            continue;
        }

        // Standard Paragraph / line
        blocks.push({ type: 'paragraph', raw: line });
        i++;
    }

    // Temporary measuring container to determine DOM heights accurately
    const measureBox = document.createElement('div');
    measureBox.className = 'a4-print-sheet';
    measureBox.style.visibility = 'hidden';
    measureBox.style.position = 'absolute';
    measureBox.style.top = '-9999px';
    measureBox.style.left = '-9999px';
    measureBox.style.height = 'auto';
    measureBox.style.maxHeight = 'none';
    measureBox.style.fontSize = `${currentFontSize}px`;
    document.body.appendChild(measureBox);

    const sheet = document.getElementById('document-preview');
    const isMobile = window.innerWidth < 640;
    const baseMaxH = (sheet && sheet.clientHeight > 100) ? sheet.clientHeight - (isMobile ? 32 : 44) : (isMobile ? 388 : 476);
    const isStampPaper = Boolean(stampPaperToggle && stampPaperToggle.checked);

    const pages = [[]];
    let currentH = 0;

    for (let b = 0; b < blocks.length; b++) {
        const block = blocks[b];
        const blockHtml = renderBlockHtml(block);

        measureBox.innerHTML = blockHtml;
        const blockH = measureBox.firstElementChild ? measureBox.firstElementChild.offsetHeight + (isMobile ? 6 : 8) : (isMobile ? 24 : 30);

        const pageLimit = (pages.length === 1 && isStampPaper) ? (baseMaxH - 45) : baseMaxH;

        if (currentH + blockH > pageLimit && pages[pages.length - 1].length > 0) {
            pages.push([blockHtml]);
            currentH = blockH;
        } else {
            pages[pages.length - 1].push(blockHtml);
            currentH += blockH;
        }
    }

    document.body.removeChild(measureBox);

    documentPages = pages.map(pageBlocks => pageBlocks.join(''));
    currentPageIndex = 0;
}

// Render the currently active page inside the A4 sheet with ZERO scrolling
function renderCurrentPage() {
    const isStamp = Boolean(stampPaperToggle && stampPaperToggle.checked);

    if (!documentPages || documentPages.length === 0) {
        if (previewContent) previewContent.classList.add('hidden');
        if (previewPlaceholder) previewPlaceholder.classList.remove('hidden');
        if (pageNavBar) pageNavBar.classList.add('hidden');
        if (stampPaperHeader) stampPaperHeader.classList.add('hidden');
        return;
    }

    if (previewPlaceholder) previewPlaceholder.classList.add('hidden');
    if (previewContent) {
        previewContent.innerHTML = documentPages[currentPageIndex] || '';
        previewContent.style.fontSize = `${currentFontSize}px`;
        previewContent.classList.remove('hidden');
    }

    // Stamp Paper Header indicator (only on Page 1)
    if (stampPaperHeader) {
        if (isStamp && currentPageIndex === 0) {
            stampPaperHeader.classList.remove('hidden');
        } else {
            stampPaperHeader.classList.add('hidden');
        }
    }

    // Page Navigation Bar
    if (documentPages.length > 1) {
        if (pageNavBar) pageNavBar.classList.remove('hidden');
        if (pageIndicator) pageIndicator.innerText = `पेज ${currentPageIndex + 1} / ${documentPages.length}`;
        if (prevPageBtn) prevPageBtn.disabled = (currentPageIndex === 0);
        if (nextPageBtn) nextPageBtn.disabled = (currentPageIndex === documentPages.length - 1);
    } else {
        if (pageNavBar) pageNavBar.classList.add('hidden');
    }
}

// Re-paginate on window resize
window.addEventListener('resize', () => {
    if (documentEditor && documentEditor.value) {
        paginateDocument(documentEditor.value);
        renderCurrentPage();
    }
});

function formatInline(str) {
    if (!str) return '';
    return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/&lt;br\s*\/?&gt;/gi, '<br>')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
}

// Convert entire document text into formatted HTML for MS Word clipboard paste
function convertTextToWordHtml(rawText) {
    if (!rawText) return '';
    const unwrapped = unwrapParagraphs(rawText);
    const lines = unwrapped.split('\n');
    let fullHtml = '';

    for (let line of lines) {
        let stripped = line.trim();
        if (!stripped) continue;
        if (stripped.startsWith('# ')) {
            fullHtml += `<h1>${formatInline(stripped.substring(2))}</h1>`;
        } else if (stripped.startsWith('## ')) {
            fullHtml += `<h2>${formatInline(stripped.substring(3))}</h2>`;
        } else if (stripped.startsWith('|') && stripped.endsWith('|')) {
            let cells = stripped.split('|').slice(1, -1).map(c => c.trim());
            if (!stripped.match(/^[\|\s\-:]+$/)) {
                fullHtml += `<tr>${cells.map(c => `<td>${formatInline(c)}</td>`).join('')}</tr>`;
            }
        } else {
            let numMatch = stripped.match(/^(\d+|[०-९]+)[\.\)]\s+(.*)$/);
            if (numMatch) {
                fullHtml += `<p><strong>${numMatch[1]}.</strong> ${formatInline(numMatch[2])}</p>`;
            } else {
                fullHtml += `<p>${formatInline(stripped)}</p>`;
            }
        }
    }

    return `<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
body {
    font-family: 'Nirmala UI', Calibri, Arial, sans-serif;
    font-size: 12pt;
    line-height: 1.5;
    color: #000000;
}
h1 {
    font-size: 16pt;
    font-weight: bold;
    text-align: center;
    margin-bottom: 12pt;
}
h2 {
    font-size: 13pt;
    font-weight: bold;
    margin-top: 12pt;
    margin-bottom: 4pt;
}
p {
    font-size: 12pt;
    text-align: justify;
    margin-bottom: 6pt;
    line-height: 1.5;
}
table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 16pt;
    margin-bottom: 16pt;
}
td {
    padding: 6pt;
    vertical-align: top;
}
</style>
</head>
<body>
${fullHtml}
</body>
</html>`;
}
