// In static/js/analysis-modal.js

document.addEventListener('DOMContentLoaded', function() {
  const modal = document.getElementById('analysis-modal');
  if (!modal) return; // Exit if the modal isn't on the page

  const bar = document.getElementById('analysis-bar');
  const statusEl = document.getElementById('analysis-status');
  const closeBtn = document.getElementById('analysis-close');
  const statusUrl = document.body.dataset.analysisStatusUrl;
  let pollStatus;

  function openModal(opts = {}) {
    modal.classList.add('active');
    if (opts.message) {
      statusEl.textContent = opts.message;
      if(bar) bar.style.width = '0%';
    } else {
      fetchStatus();
      pollStatus = setInterval(fetchStatus, 1000);
    }
    // Corrected to find the right element to focus on
    modal.querySelector('.modal-box').focus();
  }

  function closeModal() {
    modal.classList.remove('active');
    clearInterval(pollStatus);
  }

  function fetchStatus() {
    if (!statusUrl) return;
    fetch(statusUrl)
      .then(r => r.json())
      .then(d => {
        const pct = d.percent || 0;
        if (bar) {
            bar.style.width = pct + '%';
            bar.setAttribute('aria-valuenow', pct);
        }
        if (statusEl) {
            if (d.status === 'failed') {
              statusEl.textContent = 'FAILED: ' + (d.error || 'Unknown error');
              clearInterval(pollStatus);
            } else if (d.status === 'complete') {
              statusEl.textContent = 'Complete';
              clearInterval(pollStatus);
            } else {
              statusEl.textContent = d.step || 'Analyzing';
            }
        }
      });
  }

  if (closeBtn) closeBtn.addEventListener('click', closeModal);
  
  modal.addEventListener('click', (e) => {
    if (e.target === modal) {
      closeModal();
    }
  });

  modal.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') { e.preventDefault(); closeModal(); }
  });

  // This selector was incorrect. It now correctly finds all analysis forms.
  document.querySelectorAll('.btn-analyze').forEach(button => {
    button.addEventListener('click', function(ev) {
      ev.preventDefault();
      
      // Manually find the form data instead of relying on a wrapping form element
      const card = button.closest('.gallery-card');
      const filename = card.dataset.filename;
      const provider = button.dataset.provider;
      const actionUrl = `/analyze-${provider}/${encodeURIComponent(filename)}`;
      
      openModal();

      fetch(actionUrl, {
          method: 'POST',
          headers: {
              'X-Requested-With': 'XMLHttpRequest'
          }
      })
      .then(resp => {
        if (!resp.ok) {
            // Handle HTTP errors
            return resp.json().then(err => Promise.reject(err));
        }
        return resp.json();
      })
      .then(data => {
        if (data.success && data.edit_url) {
            statusEl.textContent = 'Complete! Redirecting...';
            setTimeout(() => {
                window.location.href = data.edit_url;
            }, 1000);
        } else {
            throw new Error(data.error || 'Analysis failed to return a valid URL.');
        }
      })
      .catch(error => {
        console.error('Analysis fetch error:', error);
        statusEl.textContent = `Error: ${error.error || 'A server error occurred.'}`;
        clearInterval(pollStatus);
      });
    });
  });

  // Make the modal functions globally accessible if needed by other scripts
  window.AnalysisModal = { open: openModal, close: closeModal };
});