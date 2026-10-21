/**
 * script.js — SecretVault Interactions & UI Logic
 */

document.addEventListener('DOMContentLoaded', () => {
    // ─── Global UI Elements ──────────────────────────────────────────────────
    initNavbar();
    initFlashMessages();
    initCopyButtons();
    initLoaders();
    initPasswordToggles();   // ← eye-button password visibility

    // ─── Page Specific UI ────────────────────────────────────────────────────
    
    // Encode Page
    if (document.getElementById('encodeForm')) {
        initEncodePage();
    }
    
    // Decode Page
    if (document.getElementById('decodeForm')) {
        initDecodePage();
    }
    
    // Face Registration/Auth Pages
    if (document.getElementById('faceRegisterForm') || document.getElementById('faceAuthForm')) {
        initFaceForms();
    }
});

/* ─── Password Visibility Toggles ───────────────────────────────────────── */
function initPasswordToggles() {
    // SVG paths for eye-open and eye-off states
    const EYE_OPEN = `<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" stroke="currentColor" stroke-width="2"/><circle cx="12" cy="12" r="3" stroke="currentColor" stroke-width="2"/>`;
    const EYE_OFF  = `<path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><path d="M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19" stroke="currentColor" stroke-width="2" stroke-linecap="round"/><line x1="1" y1="1" x2="23" y2="23" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>`;

    document.querySelectorAll('.input-toggle').forEach(btn => {
        btn.addEventListener('click', () => {
            // Find target input: first try data-target id, then closest sibling input
            const targetId = btn.dataset.target;
            const input = targetId
                ? document.getElementById(targetId)
                : btn.closest('.input-wrapper')?.querySelector('input');

            if (!input) return;

            const isHidden = input.type === 'password';
            input.type = isHidden ? 'text' : 'password';

            // Swap icon
            const svg = btn.querySelector('svg');
            if (svg) {
                svg.innerHTML = isHidden ? EYE_OFF : EYE_OPEN;
            }

            // Update aria-label
            btn.setAttribute('aria-label', isHidden ? 'Hide password' : 'Show password');

            // Keep focus on input for accessibility
            input.focus();
        });
    });
}


/* ─── Navbar & Dropdowns ─────────────────────────────────────────────────── */
function initNavbar() {
    // Mobile Nav Toggle
    const navToggle = document.querySelector('.nav-toggle');
    const navLinks = document.querySelector('.nav-links');
    
    if (navToggle && navLinks) {
        navToggle.addEventListener('click', () => {
            navToggle.classList.toggle('active');
            navLinks.classList.toggle('active');
        });
    }

    // User Dropdown
    const userMenu = document.querySelector('.nav-user-menu');
    const userBtn = document.querySelector('.nav-user-btn');
    
    if (userMenu && userBtn) {
        userBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            userMenu.classList.toggle('open');
        });
        
        // Close when clicking outside
        document.addEventListener('click', (e) => {
            if (!userMenu.contains(e.target)) {
                userMenu.classList.remove('open');
            }
        });
    }
    
    // Add scroll effect to navbar
    const navbar = document.querySelector('.navbar');
    if (navbar) {
        window.addEventListener('scroll', () => {
            if (window.scrollY > 20) {
                navbar.style.backgroundColor = 'rgba(255, 255, 255, 0.95)';
                navbar.style.boxShadow = '0 2px 10px rgba(0, 0, 0, 0.05)';
            } else {
                navbar.style.backgroundColor = 'var(--bg-white)';
                navbar.style.boxShadow = '0 1px 3px rgba(0,0,0,0.08)';
            }
        });
    }
}

/* ─── Flash Messages ─────────────────────────────────────────────────────── */
function initFlashMessages() {
    const flashes = document.querySelectorAll('.flash');
    
    flashes.forEach(flash => {
        // Close button
        const closeBtn = flash.querySelector('.flash-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                dismissFlash(flash);
            });
        }
        
        // Auto-dismiss after 5 seconds (except errors)
        if (!flash.classList.contains('flash-danger')) {
            setTimeout(() => {
                if (document.body.contains(flash)) {
                    dismissFlash(flash);
                }
            }, 5000);
        }
    });
}

function dismissFlash(flashElement) {
    flashElement.classList.add('fade-out');
    setTimeout(() => {
        if (flashElement.parentNode) {
            flashElement.parentNode.removeChild(flashElement);
        }
    }, 300); // Wait for animation
}

/* ─── Copy to Clipboard ──────────────────────────────────────────────────── */
function initCopyButtons() {
    const copyBtns = document.querySelectorAll('#copyBtn');
    
    copyBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetId = btn.getAttribute('data-target');
            const targetEl = document.getElementById(targetId);
            
            if (targetEl) {
                // Get text (either from input/textarea or innerText of pre/div)
                const text = targetEl.value || targetEl.innerText;
                
                navigator.clipboard.writeText(text).then(() => {
                    const originalHtml = btn.innerHTML;
                    btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none"><path d="M5 13l4 4L19 7" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg> Copied!';
                    btn.classList.add('text-success', 'border-success');
                    
                    setTimeout(() => {
                        btn.innerHTML = originalHtml;
                        btn.classList.remove('text-success', 'border-success');
                    }, 2000);
                }).catch(err => {
                    console.error('Could not copy text: ', err);
                });
            }
        });
    });
}

/* ─── Button Loaders ─────────────────────────────────────────────────────── */
function initLoaders() {
    const forms = document.querySelectorAll('form');
    
    forms.forEach(form => {
        form.addEventListener('submit', (e) => {
            // Check HTML5 validation first
            if (!form.checkValidity()) return;
            
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn && !submitBtn.disabled) {
                const btnText = submitBtn.querySelector('.btn-text');
                const btnLoader = submitBtn.querySelector('.btn-loader');
                const icon = submitBtn.querySelector('svg:not(.spinner)');
                
                if (btnText && btnLoader) {
                    btnText.classList.add('hidden');
                    btnLoader.classList.remove('hidden');
                    if (icon) icon.classList.add('hidden');
                    
                    // Don't disable the button completely, as it might prevent form submission
                    // Instead, add a class to prevent multiple clicks visually
                    submitBtn.classList.add('pointer-events-none', 'opacity-80');
                }
            }
        });
    });
}

/* ─── File Drop Zone Helpers ─────────────────────────────────────────────── */
function setupDropZone(dropZoneId, inputId, onFilesChanged) {
    const dropZone = document.getElementById(dropZoneId);
    const input = document.getElementById(inputId);
    
    if (!dropZone || !input) return;
    
    // Prevent default drag behaviors
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, preventDefaults, false);
    });

    function preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    // Allow clicking on drop zone to open file dialog
    dropZone.addEventListener('click', () => {
        input.click();
    });

    // Highlight drop zone
    ['dragenter', 'dragover'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => {
            dropZone.classList.add('dragover');
        }, false);
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropZone.addEventListener(eventName, () => {
            dropZone.classList.remove('dragover');
        }, false);
    });

    // Handle dropped files
    dropZone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        
        if (files.length > 0) {
            // Update the input files
            input.files = files;
            // Trigger change event explicitly
            const event = new Event('change', { bubbles: true });
            input.dispatchEvent(event);
        }
    }, false);
    
    // Handle input change
    input.addEventListener('change', (e) => {
        if (onFilesChanged) {
            onFilesChanged(e.target.files, dropZone, input);
        }
    });
}

/* ─── Encode Page Logic ──────────────────────────────────────────────────── */
function initEncodePage() {
    const coverInput = document.getElementById('coverImages');
    const previewGrid = document.getElementById('imagePreviewGrid');
    const imageCountBadge = document.getElementById('imageCount');
    const encodeBtn = document.getElementById('encodeBtn');
    const secretTypeToggle = document.getElementById('secretType');
    
    const minImages = parseInt(coverInput.getAttribute('data-min') || '1');
    const maxImages = parseInt(coverInput.getAttribute('data-max') || '50');
    
    // 1. Cover Images Drop Zone
    setupDropZone('dropZone', 'coverImages', (files) => {
        previewGrid.innerHTML = '';
        
        // Validate count
        if (files.length > maxImages) {
            alert(`You can only select up to ${maxImages} images.`);
            coverInput.value = ''; // Reset
            updateEncodeState();
            return;
        }
        
        imageCountBadge.textContent = `${files.length} / ${maxImages}`;
        
        if (files.length > 0) {
            document.getElementById('dropZoneInner').classList.add('hidden');
        } else {
            document.getElementById('dropZoneInner').classList.remove('hidden');
        }
        
        // Generate previews
        Array.from(files).forEach((file, index) => {
            if (!file.type.startsWith('image/')) return;
            
            const reader = new FileReader();
            reader.onload = (e) => {
                const div = document.createElement('div');
                div.className = 'preview-item';
                div.innerHTML = `
                    <img src="${e.target.result}" class="preview-img" alt="Cover preview">
                    <span class="preview-index">${index + 1}</span>
                `;
                previewGrid.appendChild(div);
            };
            reader.readAsDataURL(file);
        });
        
        // Update progress step 1
        if (files.length >= minImages && files.length <= maxImages) {
            document.querySelector('.progress-step[data-step="1"]').classList.add('completed');
            document.querySelector('.progress-step[data-step="2"]').classList.add('active');
        } else {
            document.querySelector('.progress-step[data-step="1"]').classList.remove('completed');
        }
        
        updateEncodeState();
    });
    
    // 2. Secret Type Toggle
    const textToggle = document.getElementById('textToggle');
    const fileToggle = document.getElementById('fileToggle');
    const textPanel = document.getElementById('textPanel');
    const filePanel = document.getElementById('filePanel');
    const secretTextInput = document.getElementById('secret_text');
    
    textToggle.addEventListener('click', () => {
        textToggle.classList.add('active');
        fileToggle.classList.remove('active');
        textPanel.classList.remove('hidden');
        filePanel.classList.add('hidden');
        secretTypeToggle.value = 'text';
        updateEncodeState();
    });
    
    fileToggle.addEventListener('click', () => {
        fileToggle.classList.add('active');
        textToggle.classList.remove('active');
        filePanel.classList.remove('hidden');
        textPanel.classList.add('hidden');
        secretTypeToggle.value = 'file';
        updateEncodeState();
    });
    
    // 3. Text Char Counter
    const charCount = document.getElementById('charCount');
    const charCounterDiv = document.querySelector('.char-counter');
    
    secretTextInput.addEventListener('input', () => {
        const len = secretTextInput.value.length;
        charCount.textContent = len;
        
        if (len > 80000) {
            charCounterDiv.classList.add('near-limit');
        } else {
            charCounterDiv.classList.remove('near-limit');
        }
        
        updateEncodeState();
    });
    
    // 4. Secret File Drop Zone
    const selectedFileDiv = document.getElementById('selectedFile');
    const selectedFileName = document.getElementById('selectedFileName');
    const clearFileBtn = document.getElementById('clearFile');
    const secretFileInput = document.getElementById('secretFile');
    
    setupDropZone('fileDropZone', 'secretFile', (files) => {
        if (files.length > 0) {
            const file = files[0];
            
            // Check size (16MB max)
            if (file.size > 16 * 1024 * 1024) {
                alert('File is too large. Maximum size is 16 MB.');
                secretFileInput.value = '';
                return;
            }
            
            selectedFileName.textContent = file.name;
            document.getElementById('fileDropZone').classList.add('hidden');
            selectedFileDiv.classList.remove('hidden');
            updateEncodeState();
        }
    });
    
    clearFileBtn.addEventListener('click', () => {
        secretFileInput.value = '';
        selectedFileDiv.classList.add('hidden');
        document.getElementById('fileDropZone').classList.remove('hidden');
        updateEncodeState();
    });
    
    // State validator
    function updateEncodeState() {
        const hasCovers = coverInput.files.length >= minImages && coverInput.files.length <= maxImages;
        let hasPayload = false;
        
        if (secretTypeToggle.value === 'text') {
            hasPayload = secretTextInput.value.trim().length > 0;
        } else {
            hasPayload = secretFileInput.files.length > 0;
        }
        
        if (hasPayload) {
            document.querySelector('.progress-step[data-step="2"]').classList.add('completed');
            document.querySelector('.progress-step[data-step="3"]').classList.add('active');
        } else {
            document.querySelector('.progress-step[data-step="2"]').classList.remove('completed');
            document.querySelector('.progress-step[data-step="3"]').classList.remove('active');
        }
        
        if (hasCovers && hasPayload) {
            encodeBtn.removeAttribute('disabled');
        } else {
            encodeBtn.setAttribute('disabled', 'disabled');
        }
    }
}

/* ─── Decode Page Logic ──────────────────────────────────────────────────── */
function initDecodePage() {
    const stegoInput = document.getElementById('stegoImages');
    const previewGrid = document.getElementById('stegoPreviewGrid');
    const stegoCountBadge = document.getElementById('stegoCount');
    const decodeBtn = document.getElementById('decodeBtn');
    
    setupDropZone('stegoDropZone', 'stegoImages', (files) => {
        previewGrid.innerHTML = '';
        
        if (files.length === 0) {
            stegoCountBadge.textContent = '0 images selected';
            decodeBtn.setAttribute('disabled', 'disabled');
            return;
        }
        
        stegoCountBadge.textContent = `${files.length} images selected`;
        decodeBtn.removeAttribute('disabled');
        
        // Hide drop text but keep zone for clicking
        const dropInner = document.querySelector('#stegoDropZone .drop-zone-inner');
        if (dropInner) dropInner.classList.add('hidden');
        
        // Ensure drop zone shrinks a bit
        document.getElementById('stegoDropZone').classList.remove('drop-zone-lg');
        
        // Generate previews
        Array.from(files).forEach((file, index) => {
            if (!file.type.startsWith('image/')) return;
            
            const reader = new FileReader();
            reader.onload = (e) => {
                const div = document.createElement('div');
                div.className = 'preview-item';
                div.innerHTML = `
                    <img src="${e.target.result}" class="preview-img" alt="Stego preview">
                    <span class="preview-index">${index + 1}</span>
                `;
                previewGrid.appendChild(div);
            };
            reader.readAsDataURL(file);
        });
    });
    
    // Simulate decode steps on submit
    const form = document.getElementById('decodeForm');
    form.addEventListener('submit', (e) => {
        if (!stegoInput.files.length) {
            e.preventDefault();
            return;
        }
        
        // Let form submit normally but show steps animation
        let currentStep = 1;
        const interval = setInterval(() => {
            if (currentStep <= 4) {
                document.getElementById(`dStep${currentStep}`).classList.add('active');
                currentStep++;
            } else {
                clearInterval(interval);
            }
        }, 800); // Activate a step every 800ms while request is inflight
    });
}

/* ─── Face Forms Logic ───────────────────────────────────────────────────── */
function initFaceForms() {
    // Shared logic for Register and Auth forms
    const setupFaceZone = (zoneId, inputId, innerId, previewId, placeholderId, titleId) => {
        const input = document.getElementById(inputId);
        const preview = document.getElementById(previewId);
        const placeholder = document.getElementById(placeholderId);
        const title = document.getElementById(titleId);
        
        if (!input) return;
        
        setupDropZone(zoneId, inputId, (files) => {
            if (files.length > 0 && files[0].type.startsWith('image/')) {
                const reader = new FileReader();
                reader.onload = (e) => {
                    preview.src = e.target.result;
                    preview.classList.remove('hidden');
                    if (placeholder) placeholder.classList.add('hidden');
                    if (title) title.textContent = files[0].name;
                };
                reader.readAsDataURL(files[0]);
            }
        });
    };
    
    // Register page
    setupFaceZone(
        'faceDropZone', 
        'faceImage', 
        'faceDropInner', 
        'facePreview', 
        'facePlaceholder', 
        'faceDropTitle'
    );
    
    // Auth page
    setupFaceZone(
        'faceAuthDropZone', 
        'authFaceImage', 
        null, 
        'authFacePreview', 
        'authFacePlaceholder', 
        'authFaceDropTitle'
    );
}
