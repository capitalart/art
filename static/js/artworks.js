// In static/js/artworks.js

document.addEventListener('DOMContentLoaded', () => {
  // --- Event Listener for all "Analyze" buttons ---
  document.querySelectorAll('.btn-analyze').forEach(btn => {
    btn.addEventListener('click', ev => {
      ev.preventDefault();
      const card = btn.closest('.gallery-card');
      if (!card) return;
      
      const provider = btn.dataset.provider;
      const filename = card.dataset.filename;
      
      if (!filename || !provider) {
        alert('Error: Missing filename or provider information.');
        return;
      }
      
      // Call the function to run the analysis
      runAnalyze(card, provider, filename);
    });
  });

  // --- Event Listener for all "Delete" buttons ---
  document.querySelectorAll('.btn-delete').forEach(btn => {
    btn.addEventListener('click', ev => {
      ev.preventDefault();
      const card = btn.closest('.gallery-card');
      if (!card) return;
      const filename = card.dataset.filename;
      if (!filename) return;
      if (!confirm(`Are you sure you want to delete "${filename}"?`)) return;

      showOverlay(card, 'Deleting…');
      fetch(`/delete/${encodeURIComponent(filename)}`, { method: 'POST' })
        .then(r => r.json())
        .then(d => {
          if (d.success) {
            card.remove();
          } else {
            hideOverlay(card);
            alert(d.error || 'Delete failed');
          }
        })
        .catch(() => { hideOverlay(card); alert('An error occurred during deletion.'); });
    });
  });
});

// --- Helper function to show a loading overlay on a card ---
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

// --- Helper function to hide a loading overlay ---
function hideOverlay(card) {
  const ov = card.querySelector('.card-overlay');
  if (ov) ov.classList.add('hidden');
}

// --- Main function to handle the analysis process ---
function runAnalyze(card, provider, filename) {
  // Check if the provider API is configured
  const isConfigured = document.body.dataset[`${provider}Ok`] === 'true';
  if (!isConfigured) {
    alert(`${provider.charAt(0).toUpperCase() + provider.slice(1)} API Key is not configured. Please contact the administrator.`);
    return;
  }

  // Show the analysis modal and the card overlay
  if (window.AnalysisModal) window.AnalysisModal.open();
  showOverlay(card, `Analyzing…`);

  const actionUrl = `/analyze-${provider}/${encodeURIComponent(filename)}`;

  fetch(actionUrl, {
    method: 'POST',
    headers: { 'X-Requested-With': 'XMLHttpRequest' }
  })
  .then(resp => {
    if (!resp.ok) {
      return resp.json().then(errData => Promise.reject(errData));
    }
    return resp.json();
  })
  .then(data => {
    if (data.success && data.edit_url) {
      if (window.AnalysisModal) window.AnalysisModal.setMessage('Complete! Redirecting...');
      // Wait a moment before redirecting so the user sees the "Complete" message
      setTimeout(() => {
        window.location.href = data.edit_url;
      }, 1200);
    } else {
      throw new Error(data.error || 'Analysis failed to return a valid redirect URL.');
    }
  })
  .catch(error => {
    console.error('Analysis fetch error:', error);
    // Display the error inside the modal for the user
    if (window.AnalysisModal) window.AnalysisModal.setMessage(`Error: ${error.error || 'A server error occurred.'}`);
    hideOverlay(card);
  });
}