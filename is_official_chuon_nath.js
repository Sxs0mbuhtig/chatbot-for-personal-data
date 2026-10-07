function renderSearchResult(data) {
  const container = document.getElementById("dictionary-output");
  container.innerHTML = "";

  if (data.status === "not_found") {
    container.innerHTML = `<div class="not-found-splash">${data.message}</div>`;
    return;
  }

  // 1. Render Orthographic Directive Box for Variants / Typos
  if (data.status === "variant_redirect" || !data.is_official_chuon_nath) {
    const warningBox = document.createElement("div");
    warningBox.className = "orthographic-warning-box";
    warningBox.innerHTML = `
      <div class="warning-header">⚠️ ចំណាំអក្ខរាវិរុទ្ធ</div>
      <div class="warning-body">${data.orthographic_directive}</div>
    `;
    container.appendChild(warningBox);
  }

  // 2. Render Dictionary Entry Cards
  data.results.forEach((entry) => {
    const card = document.createElement("div");
    card.className = "lexicon-card";

    const badgeHTML = entry.is_official_chuon_nath
      ? `<span class="badge official-seal">ប្រភព៖ វចនានុក្រមជួនណាត (បទដ្ឋានផ្លូវការ)</span>`
      : `<span class="badge unofficial-tag">ប្រភព៖ ${entry.source_title}</span>`;

    card.innerHTML = `
      <div class="card-header">
        <h2 class="headword">${entry.canonical_headword || entry.headword}</h2>
        <span class="pos-tag">${entry.pos}</span>
      </div>
      <div class="source-container">${badgeHTML}</div>
      <p class="definition-body">${entry.definition}</p>
    `;

    container.appendChild(card);
  });
}
