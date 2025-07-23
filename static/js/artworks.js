document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.btn-analyze').forEach(btn => {
    btn.addEventListener('click', ev => {
      ev.preventDefault();
      const card = btn.closest('.gallery-card');
      if (!card) return;
      const provider = btn.dataset.provider;
      const filename = card.dataset.filename;
      if (!filename) return;
      runAnalyze(card, provider, filename);
    });
  });

  document.querySelectorAll('.btn-delete').forEach(btn => {
    btn.addEventListener('click', ev => {
      ev.preventDefault();
      const card = btn.closest('.gallery-card');
      if (!card) return;
      const filename = card.dataset.filename;
      if (!filename) return;
      if (!confirm('Are you sure?')) return;
      showOverlay(card, 'Deleting…');
      fetch(`/delete/${encodeURIComponent(filename)}`, {method: 'POST'})
        .then(r => r.json())
        .then(d => {
          hideOverlay(card);
          if (d.success) {
            card.remove();
          } else {
            alert(d.error || 'Delete failed');
          }
        })
        .catch(() => { hideOverlay(card); alert('Delete failed'); });
    });
  });
});

function showOverlay(card, text) {
  let ov = card.querySelector('.card-overlay');
  if (!ov) {
    ov = document.createElement('div');
    ov.className = 'card-overlay';
    card.appendChild(ov);
  }
  ov.innerHTML = `<span class="spinner"></span> ${text}`;
  ov.classList.remove('hidden');
}

function hideOverlay(card) {
  const ov = card.querySelector('.card-overlay');
  if (ov) ov.classList.add('hidden');
}

// Request backend analysis for an artwork. If the server responds with
// an edit_url we immediately redirect the browser there. This keeps
// both XHR and non-XHR flows consistent with the Flask route.
// Trigger analysis for ``filename`` via the chosen provider. The backend may
// respond with JSON (listing data) or an image blob. Blob responses are
// displayed directly while JSON results update the card and/or redirect.
const FRIENDLY_AI_ERROR =
  'Sorry, we could not analyze this artwork due to an AI error. Please try again or switch provider.';

function runAnalyze(card, provider, filename) {
  const openaiOk = document.body.dataset.openaiOk === 'true';
  const googleOk = document.body.dataset.googleOk === 'true';
  if ((provider === 'openai' && !openaiOk) || (provider === 'google' && !googleOk)) {
    const msg = provider === 'openai' ? 'OpenAI API Key is not configured. Please contact admin.' : 'Google API Key is not configured. Please contact admin.';
    if (window.AnalysisModal) window.AnalysisModal.open({message: msg});
    return;
  }
  if (window.AnalysisModal) window.AnalysisModal.open();
  showOverlay(card, `Analyzing with ${provider}…`);
  fetch(`/analyze-${provider}/${encodeURIComponent(filename)}`, {
    method: 'POST',
    headers: {'X-Requested-With': 'XMLHttpRequest'}
  })
    .then(async r => {
      const type = r.headers.get('Content-Type') || '';
      if (!r.ok) {
        let msg = 'HTTP ' + r.status;
        if (type.includes('application/json')) {
          try { const j = await r.json(); msg = j.error || msg; } catch {}
        }
        throw new Error(msg);
      }
      if (type.startsWith('image/')) {
        const blob = await r.blob();
        const url = URL.createObjectURL(blob);
        const img = card.querySelector('.card-img-top');
        if (img) img.src = url;
        return {success: true};
      }
      return r.json();
    })
    .then(d => {
      hideOverlay(card);
      if (window.AnalysisModal) window.AnalysisModal.close();
      if (d.success) {
        if (d.edit_url) {
          window.location.href = d.edit_url;
          return;
        }
        updateCard(card, d);
        setStatus(card, true);
      } else {
        setStatus(card, false);
        if (window.AnalysisModal) window.AnalysisModal.open({message: FRIENDLY_AI_ERROR});
      }
    })
    .catch(err => {
      hideOverlay(card);
      setStatus(card, false);
      if (window.AnalysisModal) {
        window.AnalysisModal.open({message: FRIENDLY_AI_ERROR});
      }
    });
}

function setStatus(card, ok) {
  const icon = card.querySelector('.status-icon');
  if (!icon) return;
  icon.textContent = ok ? '✅' : '❌';
}

function updateCard(card, data) {
  const listing = data.listing || {};
  const titleEl = card.querySelector('.card-title');
  if (listing.title && titleEl) titleEl.textContent = listing.title;
  const descEl = card.querySelector('.desc-snippet');
  if (listing.description && descEl) descEl.textContent = listing.description.slice(0, 160);
  if (data.seo_folder) {
    const img = card.querySelector('.card-img-top');
    // Update thumbnail to the processed location
    if (img) img.src = `/static/art-processing/processed-artwork/${data.seo_folder}/${data.seo_folder}-THUMB.jpg?t=` + Date.now();
  }
}
