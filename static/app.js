// State Variables
let activeTab = 'image'; // 'image' or 'audio'
let selectedImageFiles = []; // Array of File objects (supports multi-page deeds)
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
let mobileUserPin = '';
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
const pageCountBadge = document.getElementById('page-count-badge');
const imagesGrid = document.getElementById('images-grid');
const clearAllImagesBtn = document.getElementById('clear-all-images');
const cameraInputAdd = document.getElementById('camera-input-add');
const fileInputAdd = document.getElementById('file-input-add');
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
const mobileUserPinInput = document.getElementById('mobile-user-pin');
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
    
    // Load previously linked sync email and PIN
    const savedMobileEmail = localStorage.getItem('tehsil_mobile_email');
    const savedMobilePin = localStorage.getItem('tehsil_mobile_pin') || '';
    if (savedMobileEmail) {
        linkMobileEmail(savedMobileEmail, savedMobilePin);
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
            if (e.target.files && e.target.files.length > 0) {
                handleImageSelection(Array.from(e.target.files));
            }
        });
    }

    // 3. Drop Zone & Gallery/File Upload
    if (dropZone && fileInput) {
        dropZone.addEventListener('click', () => {
            fileInput.click();
        });
        fileInput.addEventListener('change', (e) => {
            if (e.target.files && e.target.files.length > 0) {
                handleImageSelection(Array.from(e.target.files));
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
            if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                handleImageSelection(Array.from(e.dataTransfer.files));
            }
        });
    }

    // Additional Multi-page Camera & Gallery Listeners
    if (cameraInputAdd) {
        cameraInputAdd.addEventListener('change', (e) => {
            if (e.target.files && e.target.files.length > 0) {
                handleImageSelection(Array.from(e.target.files));
            }
        });
    }
    if (fileInputAdd) {
        fileInputAdd.addEventListener('change', (e) => {
            if (e.target.files && e.target.files.length > 0) {
                handleImageSelection(Array.from(e.target.files));
            }
        });
    }
    if (clearAllImagesBtn) {
        clearAllImagesBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            clearImageSelection();
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
            const email = mobileUserEmailInput ? mobileUserEmailInput.value.trim().toLowerCase() : '';
            const pin = mobileUserPinInput ? mobileUserPinInput.value.trim() : '';
            if (!email || !email.includes('@')) {
                showToast('error', 'कृपया एक वैध ईमेल आईडी दर्ज करें।');
                return;
            }
            if (!pin) {
                showToast('error', 'कृपया 4-अंकों का सुरक्षा पिन दर्ज करें।');
                return;
            }
            localStorage.setItem('tehsil_mobile_email', email);
            localStorage.setItem('tehsil_mobile_pin', pin);
            linkMobileEmail(email, pin);
            showToast('success', 'कंप्यूटर सिंक सफलतापूर्वक लिंक हुआ!');
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
            if (activeTab === 'image') {
                if (selectedImageFiles.length === 0) {
                    showToast('error', 'कृपया पहले फ़ोटो खींचें या गैलरी से 1 या अधिक पेज जोड़ें।');
                    return;
                }
                processWithAI('image');
            } else if (activeTab === 'audio') {
                if (!selectedAudioFile) {
                    showToast('error', 'कृपया पहले बोलकर रिकॉर्ड करें या ऑडियो फ़ाइल चुनें।');
                    return;
                }
                processWithAI('audio');
            }
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

    // 9. WhatsApp & PDF Action Controls
    const shareWhatsappDirectBtn = document.getElementById('share-whatsapp-direct-btn');
    if (shareWhatsappDirectBtn) {
        shareWhatsappDirectBtn.addEventListener('click', () => {
            const text = documentEditor ? documentEditor.value.trim() : '';
            if (!text) {
                showToast('error', 'कृपया पहले दस्तावेज़ तैयार करें।');
                return;
            }
            openModal('modal-share');
        });
    }


    const whatsappLinkModalBtn = document.getElementById('whatsapp-link-modal-btn');
    if (whatsappLinkModalBtn) {
        whatsappLinkModalBtn.addEventListener('click', shareOnWhatsApp);
    }

    const downloadDocxModalBtn = document.getElementById('download-docx-modal-btn');
    if (downloadDocxModalBtn) {
        downloadDocxModalBtn.addEventListener('click', () => {
            if (downloadForm) downloadForm.requestSubmit ? downloadForm.requestSubmit() : downloadForm.submit();
        });
    }

    const whatsappCopyBtn = document.getElementById('whatsapp-copy-btn');
    if (whatsappCopyBtn) {
        whatsappCopyBtn.addEventListener('click', () => {
            copyToClipboard();
            showToast('success', 'टेक्स्ट कॉपी हो गया! अब WhatsApp में पेस्ट करें।');
        });
    }

    // 10. Direct Send to MS Word Button Handler
    const sendToWordBtn = document.getElementById('send-to-word-btn');
    if (sendToWordBtn) {
        sendToWordBtn.addEventListener('click', handleSendToWord);
    }

    // 11. Modal Station Setup & Send Button Handler
    const modalSaveAndSendBtn = document.getElementById('modal-save-and-send-btn');
    if (modalSaveAndSendBtn) {
        modalSaveAndSendBtn.addEventListener('click', () => {
            const modalEmail = document.getElementById('modal-input-email');
            const modalPin = document.getElementById('modal-input-pin');
            const email = modalEmail ? modalEmail.value.trim().toLowerCase() : '';
            const pin = modalPin ? modalPin.value.trim() : '';

            if (!email || !email.includes('@')) {
                showToast('error', 'कृपया एक वैध Gmail दर्ज करें।');
                return;
            }
            if (!pin) {
                showToast('error', 'कृपया सुरक्षा पिन दर्ज करें।');
                return;
            }

            localStorage.setItem('tehsil_mobile_email', email);
            localStorage.setItem('tehsil_mobile_pin', pin);
            linkMobileEmail(email, pin);
            closeModal('modal-station-setup');
            handleSendToWord();
        });
    }

    // 12. Smart PC Agent Download Trigger (Prevents useless .exe downloads on mobile)
    document.querySelectorAll('.pc-agent-download-trigger').forEach(el => {
        el.addEventListener('click', (e) => {
            const isMobile = /Android|iPhone|iPad|iPod|webOS|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent) || window.innerWidth < 768;
            if (isMobile) {
                e.preventDefault();
                openModal('modal-pc-agent-info');
            }
        });
    });
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

// Render thumbnails for multi-page deeds
function renderImageThumbnails() {
    if (!imagesGrid) return;
    imagesGrid.innerHTML = '';
    
    selectedImageFiles.forEach((file, index) => {
        const thumbCard = document.createElement('div');
        thumbCard.className = 'relative group rounded-xl overflow-hidden border border-emerald-200 bg-white shadow-xs';
        
        const previewUrl = URL.createObjectURL(file);
        
        thumbCard.innerHTML = `
            <div class="relative h-28 bg-slate-100 flex items-center justify-center overflow-hidden">
                <img src="${previewUrl}" alt="पेज ${index + 1}" class="w-full h-full object-cover">
                <div class="absolute top-1.5 left-1.5 bg-emerald-900/80 backdrop-blur-xs text-white text-[10px] font-bold px-2 py-0.5 rounded-full border border-white/20 shadow-xs">
                    पेज ${index + 1}
                </div>
                <button type="button" class="remove-page-btn absolute top-1.5 right-1.5 bg-rose-600 hover:bg-rose-700 text-white rounded-full h-6 w-6 flex items-center justify-center transition shadow-sm cursor-pointer" title="इस पेज को हटाएं" data-index="${index}">
                    <i class="fa-solid fa-xmark text-xs pointer-events-none"></i>
                </button>
            </div>
            <div class="p-1.5 bg-emerald-50/50 flex justify-between items-center text-[10px] text-emerald-900 truncate">
                <span class="font-medium truncate max-w-[120px]">${file.name || `Page_${index + 1}.jpg`}</span>
                <span class="text-slate-400 text-[9px] font-mono">${(file.size / 1024).toFixed(0)} KB</span>
            </div>
        `;
        
        const removeBtn = thumbCard.querySelector('.remove-page-btn');
        if (removeBtn) {
            removeBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                removeImagePage(index);
            });
        }
        
        imagesGrid.appendChild(thumbCard);
    });

    if (pageCountBadge) {
        pageCountBadge.innerText = `${selectedImageFiles.length} पेज चुने गए`;
    }
}

function removeImagePage(index) {
    if (index >= 0 && index < selectedImageFiles.length) {
        selectedImageFiles.splice(index, 1);
        if (selectedImageFiles.length === 0) {
            clearImageSelection();
        } else {
            renderImageThumbnails();
            showToast('info', `पेज हटाया गया। कुल ${selectedImageFiles.length} पेज शेष हैं।`);
        }
    }
}

// Handle Image Selection & Preview (User must click 'दस्तावेज़ तैयार करें' to run AI)
async function handleImageSelection(filesInput) {
    const files = Array.isArray(filesInput) ? filesInput : [filesInput];
    const validImages = files.filter(f => f && ((f.type && f.type.startsWith('image/')) || (f.name && /\.(jpg|jpeg|png|webp|bmp|heic|tiff)$/i.test(f.name))));

    if (validImages.length === 0) {
        showToast('error', 'कृपया केवल इमेज फाइल (JPG, PNG, WebP) ही अपलोड करें।');
        return;
    }

    showToast('info', `${validImages.length} पेज जोड़े जा रहे हैं...`);

    for (const f of validImages) {
        const optimizedFile = await compressImageClientSide(f);
        selectedImageFiles.push(optimizedFile);
    }
    
    // Clear audio if image selected
    selectedAudioFile = null;
    if (audioPreviewContainer) audioPreviewContainer.classList.add('hidden');

    // Display multi-page preview container and hide drop-zone
    if (selectedImageFiles.length > 0) {
        if (dropZone) dropZone.classList.add('hidden');
        if (imagePreviewContainer) imagePreviewContainer.classList.remove('hidden');
        renderImageThumbnails();
        showToast('success', `${selectedImageFiles.length} पेज तैयार! अब "दस्तावेज़ तैयार करें" बटन दबाएँ।`);
    }

    // Reset file inputs so the same photo/file can be re-selected if necessary
    if (cameraInput) cameraInput.value = '';
    if (fileInput) fileInput.value = '';
    if (cameraInputAdd) cameraInputAdd.value = '';
    if (fileInputAdd) fileInputAdd.value = '';

    // NOTICE: processWithAI is NOT auto-called here.
    // The user will click `[दस्तावेज़ तैयार करें (Smart Typing)]` when satisfied with their images.
}

function clearImageSelection() {
    selectedImageFiles = [];
    if (cameraInput) cameraInput.value = '';
    if (fileInput) fileInput.value = '';
    if (cameraInputAdd) cameraInputAdd.value = '';
    if (fileInputAdd) fileInputAdd.value = '';
    if (imagesGrid) imagesGrid.innerHTML = '';
    if (pageCountBadge) pageCountBadge.innerText = '0 पेज चुने गए';
    if (imagePreviewContainer) imagePreviewContainer.classList.add('hidden');
    if (dropZone) dropZone.classList.remove('hidden');
    if (imagePreview) imagePreview.src = '#';
}

// Handle Audio Selection & Preview (User must click 'दस्तावेज़ तैयार करें' to run AI)
function handleAudioSelection(file) {
    selectedAudioFile = file;
    // Clear image selection if audio selected
    selectedImageFiles = [];
    clearImageSelection();

    if (audioPreview) audioPreview.src = URL.createObjectURL(file);
    if (audioPreviewContainer) audioPreviewContainer.classList.remove('hidden');
    if (recordStatus) recordStatus.innerText = 'ऑडियो तैयार है! नीचे "दस्तावेज़ तैयार करें" बटन दबाएँ।';

    showToast('success', 'ऑडियो रिकॉर्डिंग तैयार है! अब "दस्तावेज़ तैयार करें" बटन दबाएँ।');
    // NOTICE: processWithAI is NOT auto-called here.
    // The user will click `[दस्तावेज़ तैयार करें (Smart Typing)]` when satisfied.
}

function clearAudioSelection() {
    selectedAudioFile = null;
    if (audioInput) audioInput.value = '';
    if (audioPreview) audioPreview.src = '';
    if (audioPreviewContainer) audioPreviewContainer.classList.add('hidden');
    if (recordStatus) recordStatus.innerText = 'माइक चालू करने के लिए बटन दबाएं';
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
    if (recordStatus) recordStatus.innerText = 'रिकॉर्डिंग पूरी हो गई! अब नीचे "दस्तावेज़ तैयार करें" बटन दबाएं।';
}

// Process Document through FastAPI
async function processWithAI(mode) {
    const formData = new FormData();
    let url = '';

    if (mode === 'image' || (selectedImageFiles && selectedImageFiles.length > 0)) {
        if (!selectedImageFiles || selectedImageFiles.length === 0) {
            showToast('error', 'कृपया पहले फ़ोटो खींचें या 1 या अधिक पेज जोड़ें।');
            return;
        }
        selectedImageFiles.forEach((file) => {
            formData.append('files', file);
        });
        // Also append 'file' for backwards compatibility
        formData.append('file', selectedImageFiles[0]);
        url = '/api/process-image';
    } else {
        if (!selectedAudioFile) {
            showToast('error', 'कृपया पहले बोलकर रिकॉर्ड करें या ऑडियो फ़ाइल चुनें।');
            return;
        }
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
        
        // Auto-enable 3.0 inch stamp paper margin if Stamp Paper was detected in photo
        if (data.stamp_paper_detected && stampPaperToggle) {
            stampPaperToggle.checked = true;
            if (downloadStampInput) downloadStampInput.value = 'true';
            showToast('info', '📜 स्टाम्प पेपर पहचाना गया: 3-इंच मार्जिन स्वतः लागू हो गया!');
        } else if (stampPaperToggle && !data.stamp_paper_detected) {
            stampPaperToggle.checked = false;
            if (downloadStampInput) downloadStampInput.value = 'false';
        }

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
            processBtnText.innerHTML = `दस्तावेज़ तैयार करें (Smart Typing)`;
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
        const isStamp = Boolean(stampPaperToggle && stampPaperToggle.checked);
        const form = document.createElement('form');
        form.method = 'POST';
        form.action = '/api/download-docx';
        form.style.display = 'none';

        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = 'text';
        input.value = text;
        form.appendChild(input);

        const stampInput = document.createElement('input');
        stampInput.type = 'hidden';
        stampInput.name = 'stamp_paper';
        stampInput.value = isStamp ? 'true' : 'false';
        form.appendChild(stampInput);

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

// WhatsApp Share Handler (Directly launches WhatsApp with 1-Click DOCX Download + A4 View/PDF links)
async function shareOnWhatsApp() {
    const text = documentEditor ? documentEditor.value.trim() : '';
    if (!text) {
        showToast('error', 'शेयर करने के लिए कोई टेक्स्ट नहीं है।');
        return;
    }

    const isMobile = /Android|iPhone|iPad|iPod/i.test(navigator.userAgent);
    const whatsappShareBtn = document.getElementById('share-whatsapp-direct-btn');

    try {
        const isStamp = Boolean(stampPaperToggle && stampPaperToggle.checked);
        showToast('info', 'WhatsApp लिंक तैयार हो रहा है...');

        // 1. Generate Instant 1-Click Share Link from backend
        let docId = '';
        try {
            const linkRes = await fetch('/api/create-share-link', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text, stamp_paper: isStamp })
            });
            if (linkRes.ok) {
                const linkData = await linkRes.json();
                docId = linkData.doc_id;
            }
        } catch (e) {
            console.error('Share link generation error:', e);
        }

        const docxDownloadLink = docId ? `${window.location.origin}/d/${docId}` : window.location.href;
        const viewPrintLink = docId ? `${window.location.origin}/v/${docId}` : window.location.href;

        const whatsappMessage = `📄 *तहसील विलेख / कानूनी दस्तावेज़ (Smart Typing)*\n\nनमस्ते, आपके लिए तैयार किया गया दस्तावेज़ निम्नलिखित लिंक से प्राप्त करें:\n\n📥 *MS Word (.DOCX) फ़ाइल डाउनलोड लिंक:*\n👉 ${docxDownloadLink}\n\n👁️ *मोबाइल पर A4 देखें व PDF सेव करें:*\n👉 ${viewPrintLink}\n\n_(यह लिंक 48 घंटे के लिए सक्रिय है)_`;

        // Close modal if open
        closeModal('modal-share');

        const whatsappUrl = `https://api.whatsapp.com/send?text=${encodeURIComponent(whatsappMessage)}`;
        if (isMobile) {
            showToast('success', 'WhatsApp खोला जा रहा है...');
            // Universal HTTPS link directly opens WhatsApp app on mobile without popup block
            window.location.href = whatsappUrl;
        } else {
            showToast('info', 'WhatsApp Web खोला जा रहा है...');
            window.open(whatsappUrl, '_blank');
        }
    } catch (err) {
        console.error('WhatsApp share error:', err);
        showToast('error', 'WhatsApp खोलने में असमर्थ।');
    }
}

// Native A4 Print & "Save as PDF" Handler (100% Crisp Vector Text, Zero Dependency, Never Cuts)
function triggerNativePrint() {
    const text = documentEditor ? documentEditor.value.trim() : '';
    if (!text) {
        showToast('error', 'प्रिंट करने के लिए कोई दस्तावेज़ नहीं है।');
        return;
    }

    const isStamp = Boolean(stampPaperToggle && stampPaperToggle.checked);
    const unwrappedText = unwrapParagraphs(text);

    let printMount = document.getElementById('print-mount-point');
    if (!printMount) {
        printMount = document.createElement('div');
        printMount.id = 'print-mount-point';
        document.body.appendChild(printMount);
    }
    printMount.innerHTML = '';

    const h1Matches = unwrappedText.match(/^#\s+[^\n]+/gm) || [];
    const sevaMatches = unwrappedText.match(/^सेवा में/gm) || [];
    const rawSections = unwrappedText.split(/\n\s*-{3,}\s*\n/).filter(p => p.trim());
    const isMultiDoc = rawSections.length > 1 && (h1Matches.length > 1 || sevaMatches.length > 1);

    const rawPages = isMultiDoc ? rawSections : [unwrappedText.trim()];
    if (rawPages.length === 0) rawPages.push(unwrappedText);

    rawPages.forEach((pageText, pageIdx) => {
        const pageSheet = document.createElement('div');
        pageSheet.className = 'print-page-sheet';

        // 1. If Stamp Paper mode: add 2.7-inch blank space on Page 1 (No dashed borders, no emoji)
        if (isStamp && pageIdx === 0) {
            const spacer = document.createElement('div');
            spacer.className = 'stamp-print-spacer';
            pageSheet.appendChild(spacer);
        }

        const lines = pageText.split('\n');
        let i = 0;
        while (i < lines.length) {
            const line = lines[i].trim();
            if (!line || /^-{3,}$/.test(line)) {
                i++;
                continue;
            }

            // Markdown Table
            if (line.startsWith('|') && line.endsWith('|')) {
                const tableLines = [];
                while (i < lines.length && lines[i].trim().startsWith('|') && lines[i].trim().endsWith('|')) {
                    tableLines.push(lines[i].trim());
                    i++;
                }
                
                const tableRows = [];
                for (let tLine of tableLines) {
                    if (!tLine.match(/^[\|\s\-:]+$/)) {
                        let cells = tLine.split('|').slice(1, -1).map(c => c.trim());
                        tableRows.push(cells);
                    }
                }

                if (tableRows.length > 0) {
                    const cols = Math.max(...tableRows.map(r => r.length));

                    // If dummy 2-column table with empty left column (| | भवदीय |), render as clean right-aligned text without table
                    if (cols === 2 && tableRows.every(r => !r[0] || r[0].trim() === '')) {
                        const blockDiv = document.createElement('div');
                        blockDiv.style.textAlign = 'right';
                        blockDiv.style.margin = '8pt 0';
                        for (let r = 0; r < tableRows.length; r++) {
                            const cellVal = tableRows[r][1] || '';
                            if (cellVal) {
                                const p = document.createElement('p');
                                p.style.margin = '2pt 0';
                                p.style.textAlign = 'right';
                                p.style.lineHeight = '1.3';
                                p.innerHTML = formatInline(cellVal);
                                blockDiv.appendChild(p);
                            }
                        }
                        pageSheet.appendChild(blockDiv);
                        continue;
                    }

                    let isSigTable = tableRows.some(row => 
                        row.some(cell => {
                            const cl = cell.toLowerCase();
                            return ['हस्ताक्षर', 'हसताक्षर', 'हस्तक्षर', 'हस्ताक्षरी', 'साक्षी', 'साक्क्षी', 'गवाह', 'प्रथम पक्ष', 'परथम पक्ष', 'द्वितीय पक्ष', 'दवतीय पक्ष', 'क्रेता', 'विक्रेता', 'शपथकर्ता', 'आवेदक', 'प्रार्थी', 'निवेदक', 'भवदीय', 'signature', 'witness', 'party', 'landlord', 'tenant', 'deponent', 'applicant'].some(kw => cl.includes(kw));
                        })
                    );
                    if (cols === 2 && !isSigTable && tableRows.length <= 4) {
                        isSigTable = true;
                    }

                    const tbl = document.createElement('table');
                    tbl.className = 'print-table';

                    if (!isSigTable) {
                        tbl.style.border = '1.5pt solid #06281e';
                    }

                    for (let r = 0; r < tableRows.length; r++) {
                        const tr = document.createElement('tr');
                        const isHeader = (r === 0 && !isSigTable);
                        if (isHeader) {
                            tr.style.backgroundColor = '#f0fdf4';
                            tr.style.fontWeight = 'bold';
                        }

                        for (let c = 0; c < cols; c++) {
                            const cellVal = tableRows[r][c] || '';
                            const td = document.createElement(isHeader ? 'th' : 'td');
                            
                            if (!isSigTable) {
                                td.style.border = '1pt solid #cbd5e1';
                            }

                            if (isSigTable && cols === 2) {
                                td.style.textAlign = (c === 0) ? 'left' : 'right';
                                td.style.width = '50%';
                            } else if (isSigTable) {
                                td.style.textAlign = 'center';
                            } else {
                                td.style.textAlign = isHeader ? 'center' : 'left';
                            }

                            td.innerHTML = formatInline(cellVal);
                            tr.appendChild(td);
                        }
                        tbl.appendChild(tr);
                    }
                    pageSheet.appendChild(tbl);
                }
                continue;
            }

            // Title (# Title)
            if (line.startsWith('# ')) {
                const h1 = document.createElement('h1');
                h1.className = 'print-title';
                h1.innerHTML = formatInline(line.substring(2).trim());
                pageSheet.appendChild(h1);
                i++;
                continue;
            }

            // Section Heading (## Heading)
            if (line.startsWith('## ')) {
                const h2 = document.createElement('h2');
                h2.className = 'print-heading';
                h2.innerHTML = formatInline(line.substring(3).trim());
                pageSheet.appendChild(h2);
                i++;
                continue;
            }

            // Sub-Heading (### Sub-Heading)
            if (line.startsWith('### ')) {
                const h3 = document.createElement('h3');
                h3.style.fontSize = '12pt';
                h3.style.fontWeight = 'bold';
                h3.style.color = '#06281e';
                h3.style.margin = '8pt 0 3pt 0';
                h3.innerHTML = formatInline(line.substring(4).trim());
                pageSheet.appendChild(h3);
                i++;
                continue;
            }

            // Numbered Clause (e.g. 1. or (1) or (क))
            const numMatch = line.match(/^(?:(?:\(?(\d+|[०-९]+|[क-ह])\))|(\d+|[०-९]+)[\.\)])\s+(.*)$/);
            if (numMatch) {
                const num = numMatch[1] || numMatch[2];
                const content = numMatch[3];
                const clauseDiv = document.createElement('div');
                clauseDiv.className = 'print-clause';
                clauseDiv.innerHTML = `<strong>${num}.</strong> ${formatInline(content)}`;
                pageSheet.appendChild(clauseDiv);
                i++;
                continue;
            }

            // Standard Paragraph
            const p = document.createElement('p');
            p.className = 'print-p';
            p.innerHTML = formatInline(line);
            pageSheet.appendChild(p);
            i++;
        }

        printMount.appendChild(pageSheet);
    });

    // Close modal if open so it doesn't block the screen
    closeModal('modal-share');

    // Trigger Browser Native Print Dialog
    setTimeout(() => {
        const origTitle = document.title;
        document.title = '';
        window.print();
        setTimeout(() => {
            document.title = origTitle;
        }, 1000);
    }, 150);
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
function linkMobileEmail(email, pin) {
    mobileUserEmail = email;
    mobileUserPin = pin || localStorage.getItem('tehsil_mobile_pin') || '';
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
    mobileUserPin = '';
    localStorage.removeItem('tehsil_mobile_email');
    localStorage.removeItem('tehsil_mobile_pin');
    
    if (mobileLoginSection) mobileLoginSection.classList.remove('hidden');
    if (mobileActiveSection) mobileActiveSection.classList.add('hidden');
    if (mobileUserEmailInput) mobileUserEmailInput.value = '';
    if (mobileUserPinInput) mobileUserPinInput.value = '';
    
    if (checkSyncStatusInterval) {
        clearInterval(checkSyncStatusInterval);
        checkSyncStatusInterval = null;
    }
    
    isDesktopConnected = false;
    updateMobileSyncBadge(false);
}

// Explicit On-Demand Send to Desktop MS Word
async function handleSendToWord() {
    const text = documentEditor ? documentEditor.value.trim() : '';
    if (!text) {
        showToast('error', 'भेजने के लिए पहले दस्तावेज़ तैयार करें।');
        return;
    }

    if (!mobileUserEmail || !mobileUserPin) {
        const modalEmail = document.getElementById('modal-input-email');
        const modalPin = document.getElementById('modal-input-pin');
        if (modalEmail && mobileUserEmail) modalEmail.value = mobileUserEmail;
        if (modalPin && mobileUserPin) modalPin.value = mobileUserPin;
        openModal('modal-station-setup');
        return;
    }

    const sendToWordBtn = document.getElementById('send-to-word-btn');
    if (sendToWordBtn) sendToWordBtn.setAttribute('disabled', 'true');
    showToast('info', 'MS Word में भेजा जा रहा है...');

    try {
        const isStamp = Boolean(stampPaperToggle && stampPaperToggle.checked);
        const res = await fetch('/api/send-to-word', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                text: text,
                stamp_paper: isStamp,
                station_id: mobileUserEmail,
                pin: mobileUserPin
            })
        });

        const data = await res.json();
        if (res.ok && data.success) {
            showToast('success', data.message || 'दस्तावेज़ भेजा गया! कंप्यूटर के MS Word में खुल रहा है...');
        } else {
            showToast('error', data.message || 'भेजने में विफल।');
            if (res.status === 401 || res.status === 404) {
                const modalEmail = document.getElementById('modal-input-email');
                const modalPin = document.getElementById('modal-input-pin');
                if (modalEmail) modalEmail.value = mobileUserEmail;
                if (modalPin) modalPin.value = mobileUserPin;
                openModal('modal-station-setup');
            }
        }
    } catch (err) {
        console.error('Send to Word error:', err);
        showToast('error', 'कनेक्शन त्रुटि: कंप्यूटर तक नहीं पहुँच सका।');
    } finally {
        if (sendToWordBtn) sendToWordBtn.removeAttribute('disabled');
    }
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
    let inClosing = false;

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
        const isPageBreak = /^\s*-{3,}\s*$/.test(stripped);
        if (isPageBreak) inClosing = false;

        const isNewClause = /^(?:(?:\(?(\d+|[०-९]+|[क-ह])\))|(\d+|[०-९]+)[\.\)])\s+/.test(stripped);
        const isLabelLine = /^[^:\n]{2,35}\s*:\s*.*$/.test(stripped);

        // Precision closing detection: sentences ending in verbs/punctuation are NOT closing blocks
        const isSentence = /(?:कि:|है[।\.]|हूँ[।\.]|था[।\.]|करें[।\.]|गया[।\.]|जाएगा[।\.])$/.test(stripped);
        let isClosingStart = false;
        if (!isSentence && stripped.length < 45) {
            if (/^(?:द्वारा अधिवक्ता|अधिवक्ता|हस्ताक्षर|भवदीय|निवेदक|शपथी|शपथकर्ता|विनीत|आपका आज्ञाकारी|आज्ञाकारी|स्वीकृत व प्रस्तुतकर्ता|Sincerely|Regards|Yours obediently|Yours faithfully)\b/i.test(stripped)) {
                isClosingStart = true;
            } else if (/^(?:आवेदक|प्रार्थी)\s*(?:[/:,।\-]|बनाम|$)/i.test(stripped) && !/(?:सादर|निवेदन|प्रार्थना|करता|करती)/.test(stripped)) {
                isClosingStart = true;
            }
        }

        if (isClosingStart) {
            inClosing = true;
        } else if (inClosing && (isSentence || stripped.length > 60 || isNewClause || isHeading)) {
            inClosing = false;
        }

        const isFormalBreak = /^(सेवा में|महोदय|महोदया|श्रीमान|मान्यवर|विषय|स्थान|दिनांक|न्यायालय|मुकदमा|बनाम|थाना|धारा|प्रार्थना|अनुतोष|स्वीकृत|संलग्नक|नाम|पिता|पता|कक्षा|अनुक्रमांक|मो०|मोबाइल|To:|From:|Subject:|Dear|Respected|Date:)/i.test(stripped) || isClosingStart;

        if (inClosing || isHeading || isBullet || isTable || isPageBreak || isNewClause || isLabelLine || isFormalBreak) {
            if (currentP.length > 0) {
                unwrapped.push(currentP.join(' '));
                currentP = [];
            }
            unwrapped.push(stripped);
        } else {
            if (currentP.length > 0 && 
                !currentP[currentP.length - 1].startsWith('#') && 
                !currentP[currentP.length - 1].startsWith('|') && 
                !/^\s*-{3,}\s*$/.test(currentP[currentP.length - 1]) &&
                !/^[^:\n]{2,35}\s*:\s*.*$/.test(currentP[currentP.length - 1]) &&
                !/^(सेवा में|महोदय|महोदया|श्रीमान|मान्यवर|विषय|भवदीय|प्रार्थी|आवेदक|निवेदक|शपथी|हस्ताक्षर|न्यायालय|मुकदमा|बनाम|To:|From:|Subject:|Dear|Respected|Sincerely)/i.test(currentP[currentP.length - 1])) {
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
        return `<h1 class="font-bold text-center text-slate-950 mb-3 pb-1 border-b border-slate-300 tracking-wide text-sm sm:text-base leading-snug">${formatInline(block.raw)}</h1>`;
    }
    if (block.type === 'heading') {
        return `<h2 class="font-bold text-slate-900 mt-2 mb-1 text-xs sm:text-sm">${formatInline(block.raw)}</h2>`;
    }
    if (block.type === 'subheading') {
        return `<h3 class="font-bold text-slate-900 mt-1.5 mb-0.5 text-xs sm:text-sm" style="color: #06281e;">${formatInline(block.raw)}</h3>`;
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

        // If dummy 2-column table with empty left column (| | भवदीय |), render as clean right-aligned text without table
        if (cols === 2 && tableRows.every(r => !r[0] || r[0].trim() === '')) {
            let html = '<div class="my-2.5 text-right w-full space-y-0.5">';
            for (let r = 0; r < tableRows.length; r++) {
                let cellVal = tableRows[r][1] || '';
                if (cellVal) {
                    html += `<p class="leading-normal text-right text-slate-900 font-medium">${formatInline(cellVal)}</p>`;
                }
            }
            html += '</div>';
            return html;
        }

        // True 2-party side-by-side or data table: keep Left on left (w-1/2) and Right on right (w-1/2), never mix!
        let html = '<div class="my-2.5 w-full"><table class="w-full border-collapse">';
        for (let r = 0; r < tableRows.length; r++) {
            html += '<tr>';
            for (let c = 0; c < cols; c++) {
                let cellVal = tableRows[r][c] || '';
                let widthClass = (cols === 2) ? 'w-1/2' : '';
                let alignClass = (cols === 2 && c === 1) ? 'text-right' : 'text-left';
                html += `<td class="p-1.5 align-top ${widthClass} ${alignClass} text-slate-900 font-medium">${formatInline(cellVal)}</td>`;
            }
            html += '</tr>';
        }
        html += '</table></div>';
        return html;
    }
    if (block.type === 'closing') {
        return `<p class="my-0.5 leading-normal text-right text-slate-900 font-medium">${formatInline(block.raw)}</p>`;
    }
    if (block.type === 'left_info') {
        return `<p class="my-0.5 leading-normal text-left text-slate-900 font-medium">${formatInline(block.raw)}</p>`;
    }
    if (block.type === 'break') {
        return '<div class="my-4 border-t-2 border-dashed border-emerald-300 relative flex items-center justify-center print:hidden"><span class="bg-white px-3 text-[10px] text-emerald-800 font-bold uppercase tracking-wider">नया पेज (Next Page / New Document)</span></div>';
    }
    return `<p class="my-1 leading-tight text-justify text-slate-900">${formatInline(block.raw)}</p>`;
}

// Universal A4 Pagination: divides any document across Page 1, Page 2 with ZERO scrolling
// Render Authentic A4 Print Preview directly in the on-screen preview box
function paginateDocument(rawText) {
    if (!rawText || !rawText.trim()) {
        documentPages = [];
        currentPageIndex = 0;
        return;
    }

    const unwrappedText = unwrapParagraphs(rawText);
    const lines = unwrappedText.split('\n');
    const isStampPaper = Boolean(stampPaperToggle && stampPaperToggle.checked);

    // Parse into distinct semantic blocks
    const blocks = [];
    let i = 0;
    let inClosingBlock = false;
    while (i < lines.length) {
        let line = lines[i].trim();
        if (!line) {
            i++;
            continue;
        }

        // Section Break
        if (/^-{3,}$/.test(line)) {
            blocks.push({ type: 'break' });
            inClosingBlock = false;
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
            inClosingBlock = false;
            i++;
            continue;
        }

        // Section Heading
        if (line.startsWith('## ')) {
            blocks.push({ type: 'heading', raw: line.substring(3).trim() });
            inClosingBlock = false;
            i++;
            continue;
        }

        // Sub-Heading
        if (line.startsWith('### ')) {
            blocks.push({ type: 'subheading', raw: line.substring(4).trim() });
            inClosingBlock = false;
            i++;
            continue;
        }

        // Numbered Clause
        let numMatch = line.match(/^(?:(?:\(?(\d+|[०-९]+|[क-ह])\))|(\d+|[०-९]+)[\.\)])\s+(.*)$/);
        if (numMatch) {
            const num = numMatch[1] || numMatch[2];
            blocks.push({ type: 'clause', num: num, raw: numMatch[3] });
            inClosingBlock = false;
            i++;
            continue;
        }

        // Date and place line stays on left
        if (/^(दिनांक|स्थान|Date:|Place:)/i.test(line)) {
            inClosingBlock = false;
            blocks.push({ type: 'left_info', raw: line });
            i++;
            continue;
        }

        // Check single closing / signature / applicant block lines
        const isSentence = /(?:कि:|है[।\.]|हूँ[।\.]|था[।\.]|करें[।\.]|गया[।\.]|जाएगा[।\.])$/.test(line);
        let isClosingStart = false;
        if (!isSentence && line.length < 45) {
            if (/^(?:द्वारा अधिवक्ता|अधिवक्ता|हस्ताक्षर|भवदीय|निवेदक|शपथी|शपथकर्ता|विनीत|आपका आज्ञाकारी|आज्ञाकारी|स्वीकृत व प्रस्तुतकर्ता|Sincerely|Regards|Yours obediently|Yours faithfully)\b/i.test(line)) {
                isClosingStart = true;
            } else if (/^(?:आवेदक|प्रार्थी)\s*(?:[/:,।\-]|बनाम|$)/i.test(line) && !/(?:सादर|निवेदन|प्रार्थना|करता|करती)/.test(line)) {
                isClosingStart = true;
            }
        }

        if (isClosingStart) {
            inClosingBlock = true;
        } else if (inClosingBlock && (isSentence || line.length > 60 || numMatch || line.startsWith('#'))) {
            inClosingBlock = false;
        }

        if (inClosingBlock) {
            blocks.push({ type: 'closing', raw: line });
            i++;
            continue;
        }

        // Standard Paragraph / line
        blocks.push({ type: 'paragraph', raw: line });
        i++;
    }

    // Group blocks into individual pages separated by 'break' (---)
    const pages = [];
    let currentPageBlocks = [];

    for (let b = 0; b < blocks.length; b++) {
        if (blocks[b].type === 'break') {
            if (currentPageBlocks.length > 0) {
                pages.push(currentPageBlocks);
                currentPageBlocks = [];
            }
        } else {
            currentPageBlocks.push(blocks[b]);
        }
    }
    if (currentPageBlocks.length > 0 || pages.length === 0) {
        pages.push(currentPageBlocks);
    }

    documentPages = pages.map((pageBlks, pageIdx) => {
        let pageHtml = [];
        if (pageIdx === 0 && isStampPaper) {
            pageHtml.push('<div class="stamp-space-box w-full mb-5 py-6 border-2 border-dashed border-emerald-300 rounded-xl bg-emerald-50/50 text-center text-emerald-800 font-bold text-xs select-none flex items-center justify-center space-x-2"><i class="fa-solid fa-stamp text-emerald-600 text-sm"></i><span>📜 स्टाम्प पेपर प्रिंट एरिया (3.0" Space Reserved)</span></div>');
        }
        for (let blk of pageBlks) {
            pageHtml.push(renderBlockHtml(blk));
        }
        return pageHtml.join('');
    });

    if (currentPageIndex >= documentPages.length) {
        currentPageIndex = 0;
    }
}

// Render the A4 Print Preview with natural reading flow
function renderCurrentPage() {
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

    // Page navigation bar for multi-page / multi-document drafts
    if (pageNavBar) {
        if (documentPages.length > 1) {
            pageNavBar.classList.remove('hidden');
            if (pageIndicator) {
                pageIndicator.innerText = `पेज ${currentPageIndex + 1} / ${documentPages.length}`;
            }
            if (prevPageBtn) {
                prevPageBtn.disabled = (currentPageIndex === 0);
                prevPageBtn.style.opacity = (currentPageIndex === 0) ? '0.4' : '1';
                prevPageBtn.style.cursor = (currentPageIndex === 0) ? 'not-allowed' : 'pointer';
            }
            if (nextPageBtn) {
                nextPageBtn.disabled = (currentPageIndex === documentPages.length - 1);
                nextPageBtn.style.opacity = (currentPageIndex === documentPages.length - 1) ? '0.4' : '1';
                nextPageBtn.style.cursor = (currentPageIndex === documentPages.length - 1) ? 'not-allowed' : 'pointer';
            }
        } else {
            pageNavBar.classList.add('hidden');
        }
    }

    if (stampPaperHeader) {
        const isStampPaper = Boolean(stampPaperToggle && stampPaperToggle.checked);
        if (isStampPaper && currentPageIndex === 0) {
            stampPaperHeader.classList.remove('hidden');
        } else {
            stampPaperHeader.classList.add('hidden');
        }
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
    let inTable = false;
    let inClosing = false;

    function closeTable() {
        if (inTable) {
            fullHtml += '</tbody></table>';
            inTable = false;
        }
    }

    for (let line of lines) {
        let stripped = line.trim();
        if (!stripped) continue;
        if (stripped.match(/^-{3,}$/)) {
            closeTable();
            inClosing = false;
            fullHtml += '<br clear="all" style="page-break-before:always; mso-break-type:section-break">';
            continue;
        }

        if (stripped.startsWith('|') && stripped.endsWith('|')) {
            if (!inTable) {
                fullHtml += '<table border="0" cellspacing="0" cellpadding="4" style="width:100%; border-collapse:collapse; margin-top:12pt; margin-bottom:12pt;"><tbody>';
                inTable = true;
            }
            if (!stripped.match(/^[\|\s\-:]+$/)) {
                let cells = stripped.split('|').slice(1, -1).map(c => c.trim());
                fullHtml += '<tr>';
                for (let c = 0; c < cells.length; c++) {
                    let align = (cells.length === 2 && c === 1) ? 'right' : 'left';
                    fullHtml += `<td style="vertical-align:top; text-align:${align}; padding:4pt 6pt;">${formatInline(cells[c])}</td>`;
                }
                fullHtml += '</tr>';
            }
            continue;
        }

        closeTable();

        if (stripped.startsWith('# ')) {
            inClosing = false;
            fullHtml += `<h1>${formatInline(stripped.substring(2))}</h1>`;
        } else if (stripped.startsWith('## ')) {
            inClosing = false;
            fullHtml += `<h2>${formatInline(stripped.substring(3))}</h2>`;
        } else if (stripped.startsWith('### ')) {
            inClosing = false;
            fullHtml += `<h3>${formatInline(stripped.substring(4))}</h3>`;
        } else {
            let numMatch = stripped.match(/^(?:(?:\(?(\d+|[०-९]+|[क-ह])\))|(\d+|[०-९]+)[\.\)])\s+(.*)$/);
            if (numMatch) {
                inClosing = false;
                let num = numMatch[1] || numMatch[2];
                fullHtml += `<p><strong>${num}.</strong> ${formatInline(numMatch[3])}</p>`;
            } else {
                const isSentence = /(?:कि:|है[।\.]|हूँ[।\.]|था[।\.]|करें[।\.]|गया[।\.]|जाएगा[।\.])$/.test(stripped);
                let isClosingStart = false;
                if (!isSentence && stripped.length < 45) {
                    if (/^(?:द्वारा अधिवक्ता|अधिवक्ता|हस्ताक्षर|भवदीय|निवेदक|शपथी|शपथकर्ता|विनीत|आपका आज्ञाकारी|आज्ञाकारी|स्वीकृत व प्रस्तुतकर्ता|Sincerely|Regards|Yours obediently|Yours faithfully)\b/i.test(stripped)) {
                        isClosingStart = true;
                    } else if (/^(?:आवेदक|प्रार्थी)\s*(?:[/:,।\-]|बनाम|$)/i.test(stripped) && !/(?:सादर|निवेदन|प्रार्थना|करता|करती)/.test(stripped)) {
                        isClosingStart = true;
                    }
                }

                if (isClosingStart) {
                    inClosing = true;
                } else if (inClosing && (isSentence || stripped.length > 60)) {
                    inClosing = false;
                }

                let pAlign = inClosing ? 'right' : 'justify';
                fullHtml += `<p style="text-align:${pAlign};">${formatInline(stripped)}</p>`;
            }
        }
    }

    closeTable();

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
