// JavaScript snippet to handle API response cleanly
async function performSearch(overrideQuery) {
    const searchInput = document.getElementById('searchInput');
    const query = (overrideQuery || searchInput.value).trim();
    if (!query) return;

    const resultsContainer = document.getElementById('resultsContainer') || document.getElementById('results');
    if (resultsContainer) {
        resultsContainer.innerHTML = '<div class="loading">កំពុងស្វែងរកក្នុងទិន្នន័យ...</div>';
    }

    try {
        const response = await fetch(`/api/v1/search?q=${encodeURIComponent(query)}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        
        const data = await response.json();
        
        // Render results into page safely
        let html = `<h3>លទ្ធផលសម្រាប់: ${data.query}</h3>`;
        
        if (data.educational_card) {
            html += `<div style="background:#f0f4f8; padding:10px; border-radius:5px; margin-bottom:15px;">
                <strong>${data.educational_card.title_km}</strong> (${data.educational_card.register_label_km})<br/>
                <p>${data.educational_card.historical_context_km}</p>
            </div>`;
        }

        if (data.linguistic_analysis && data.linguistic_analysis.morphology) {
            const morph = data.linguistic_analysis.morphology;
            html += `<div style="background:#eef9f2; padding:10px; border-radius:5px; margin-bottom:15px;">
                <strong>Morphology:</strong> Root: <code>${morph.root_morpheme}</code> | Subscripts: <code>${JSON.stringify(morph.subscript_sequence)}</code>
            </div>`;
        }

        if (data.results && data.results.length > 0) {
            data.results.forEach(item => {
                html += `<div class="result-card" style="border-bottom:1px solid #ccc; padding:10px 0;">
                    <h4>${item.entry_km}</h4>
                    <p>${item.definition_km}</p>
                </div>`;
            });
        } else {
            html += `<p>មិនមានទិន្នន័យបង្ហាញទេ។</p>`;
        }

        if (resultsContainer) {
            resultsContainer.innerHTML = html;
        }
    } catch (err) {
        console.error("Render error:", err);
        if (resultsContainer) {
            resultsContainer.innerHTML = `<div class="error" style="color:red;">មានបញ្ហាក្នុងការទាញយកទិន្នន័យ: ${err.message}</div>`;
        }
    }
}
