/**
 * Lexicography UI Error & Alert Handling Module
 * File: error_handling_js.js
 */

const LexiconAlerts = {
    /**
     * Renders a top-level alert card for spelling corrections, non-standard variants, 
     * or official Chuon Nath guidance.
     * 
     * @param {Object} data - Search API response object
     * @param {HTMLElement} parentContainer - DOM container element to prepend the alert
     */
    renderOrthographicGuidance(data, parentContainer) {
        if (!data || data.status !== 'variant_redirect' || !data.orthographic_directive) {
            return;
        }

        const isMisspelling = data.orthographic_directive.includes('ខុសអក្ខរាវិរុទ្ធ') || 
                              data.orthographic_directive.includes('Misspelling');

        const alertContainer = document.createElement('div');
        alertContainer.id = 'orthographicBanner';
        alertContainer.className = `mb-6 p-4 rounded-xl border shadow-sm transition-all animate-fade-in ${
            isMisspelling 
                ? 'bg-amber-50 border-amber-300 text-amber-950' 
                : 'bg-blue-50 border-blue-300 text-blue-950'
        }`;

        alertContainer.innerHTML = `
            <div class="flex items-start gap-3">
                <span class="text-2xl flex-shrink-0">${isMisspelling ? '⚠️' : 'ℹ️'}</span>
                <div class="flex-grow">
                    <div class="flex items-center justify-between mb-1">
                        <h4 class="font-bold text-base flex items-center gap-2">
                            <span>${isMisspelling ? 'ការណែនាំអក្ខរាវិរុទ្ធ (Spelling Guidance)' : 'ព័ត៌មានអក្ខរាវិរុទ្ធ (Orthographic Notice)'}</span>
                            <span class="text-xs px-2 py-0.5 rounded-full font-semibold ${
                                isMisspelling 
                                    ? 'bg-amber-200 text-amber-900 border border-amber-300' 
                                    : 'bg-blue-200 text-blue-900 border border-blue-300'
                            }">
                                ${isMisspelling ? 'សំណេរខុស (Misspelling)' : 'ទម្រង់អថេរ (Variant)'}
                            </span>
                        </h4>
                    </div>
                    <p class="text-sm leading-relaxed mb-2">${data.orthographic_directive}</p>
                    ${data.canonical_word ? `
                        <div class="inline-flex items-center gap-2 bg-white/80 px-3 py-1.5 rounded-lg border border-slate-200 text-xs font-medium text-slate-700">
                            <span>ទម្រង់បទដ្ឋានផ្លូវការ៖</span>
                            <strong class="text-indigo-900 text-sm font-bold underline cursor-pointer hover:text-indigo-600" onclick="handleSearch('${data.canonical_word}')">
                                ${data.canonical_word}
                            </strong>
                        </div>
                    ` : ''}
                </div>
            </div>
        `;

        parentContainer.prepend(alertContainer);
    },

    /**
     * Renders connection, system, or timeout error alerts.
     */
    renderApiError(message, parentContainer) {
        parentContainer.innerHTML = `
            <div class="bg-red-50 border border-red-200 text-red-800 p-5 rounded-2xl shadow-sm text-center">
                <span class="text-3xl block mb-2">🚨</span>
                <h3 class="font-bold text-base mb-1">បរាជ័យក្នុងការភ្ជាប់សេវា (Connection Error)</h3>
                <p class="text-sm text-red-600">${message}</p>
            </div>
        `;
    },

    /**
     * Clear all active alerts from the container.
     */
    clearAlerts() {
        const banner = document.getElementById('orthographicBanner');
        if (banner) banner.remove();
    }
};
