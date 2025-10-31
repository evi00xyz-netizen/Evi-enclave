/**
 * Trust Center Popup Component
 * Displays Phala Network TEE attestation widget in a modal popup
 */

class TrustCenterPopup {
    constructor(iframeUrl) {
        this.iframeUrl = iframeUrl;
        this.modal = null;
        this.isOpen = false;
    }

    init() {
        // Create modal HTML
        const modalHTML = `
            <div id="trustCenterModal" class="hidden fixed inset-0 bg-black bg-opacity-75 z-50 flex items-center justify-center p-4">
                <div class="bg-gray-800 rounded-lg overflow-hidden flex flex-col shadow-2xl relative" style="width: 382px;">
                    <!-- Modal Header -->
                    <div class="p-4 border-b border-gray-700 text-center">
                        <h2 class="text-lg font-bold flex items-center justify-center gap-2">
                            🔒 TEE Trust Center
                        </h2>
                        <p class="text-xs text-gray-400 mt-1">Powered by Phala Cloud</p>
                        <button onclick="trustCenter.close()" class="text-gray-400 hover:text-white text-2xl leading-none transition-colors absolute top-2 right-2" aria-label="Close">
                            ×
                        </button>
                    </div>

                    <!-- Iframe Container -->
                    <div class="overflow-hidden bg-white" style="height: 800px;">
                        <iframe
                            src="${this.iframeUrl}"
                            width="100%"
                            height="800"
                            frameborder="0"
                            class="w-full h-full"
                            title="Phala Cloud Trust Center"
                        ></iframe>
                    </div>
                </div>
            </div>
        `;

        // Create floating badge HTML
        const badgeHTML = `
            <button
                onclick="trustCenter.open()"
                class="fixed bottom-6 right-6 bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-700 hover:to-blue-700 text-white px-6 py-3 rounded-full shadow-lg flex items-center gap-2 transition-all hover:scale-105 z-40 group"
                aria-label="View TEE Attestation"
            >
                <span class="text-xl">🔒</span>
                <span class="font-bold">TEE Verified</span>
                <div class="absolute -top-1 -right-1 w-3 h-3 bg-green-500 rounded-full animate-pulse"></div>
            </button>
        `;

        // Inject HTML into body
        document.body.insertAdjacentHTML('beforeend', modalHTML);
        document.body.insertAdjacentHTML('beforeend', badgeHTML);

        this.modal = document.getElementById('trustCenterModal');

        // Setup event listeners
        this.setupEventListeners();
    }

    setupEventListeners() {
        // Close on ESC key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.isOpen) {
                this.close();
            }
        });

        // Close on backdrop click
        this.modal.addEventListener('click', (e) => {
            if (e.target === this.modal) {
                this.close();
            }
        });
    }

    open() {
        this.modal.classList.remove('hidden');
        this.isOpen = true;
        // Prevent body scroll when modal is open
        document.body.style.overflow = 'hidden';
    }

    close() {
        this.modal.classList.add('hidden');
        this.isOpen = false;
        // Restore body scroll
        document.body.style.overflow = '';
    }

    toggle() {
        if (this.isOpen) {
            this.close();
        } else {
            this.open();
        }
    }
}

// Initialize trust center with URL fetched from backend
let trustCenter = null;

async function initializeTrustCenter() {
    try {
        // Fetch trust center URL from backend API
        const response = await fetch('/api/trust-center-url');

        if (!response.ok) {
            console.error('Failed to fetch trust center URL:', response.statusText);
            return;
        }

        const data = await response.json();
        const trustCenterUrl = data.trust_center_url;

        if (!trustCenterUrl) {
            console.error('Trust center URL not configured');
            return;
        }

        // Initialize trust center with fetched URL
        trustCenter = new TrustCenterPopup(trustCenterUrl);
        trustCenter.init();
    } catch (error) {
        console.error('Error initializing trust center:', error);
    }
}

// Initialize on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeTrustCenter);
} else {
    initializeTrustCenter();
}
