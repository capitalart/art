document.addEventListener('DOMContentLoaded', function() {
  const modal = document.getElementById('analysis-modal');
  const bar = document.getElementById('analysis-bar');
  const statusEl = document.getElementById('analysis-status');
  const closeBtn = document.getElementById('analysis-close');
  const statusUrl = document.body.dataset.analysisStatusUrl;
  let pollStatus;

  function openModal() {
    modal.classList.add('active');
    fetchStatus();
    pollStatus = setInterval(fetchStatus, 1000);
    modal.querySelector('.analysis-box').focus();
  }

  function closeModal() {
    modal.classList.remove('active');
    clearInterval(pollStatus);
  }

  function fetchStatus() {
    fetch(statusUrl)
      .then(r => r.json())
      .then(d => {
        const pct = d.percent || 0;
        bar.style.width = pct + '%';
        bar.setAttribute('aria-valuenow', pct);
        statusEl.textContent = d.step || '';
      });
  }

  if (closeBtn) closeBtn.addEventListener('click', closeModal);
  modal.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') { e.preventDefault(); closeModal(); }
  });

  document.querySelectorAll('form.analyze-form').forEach(f => {
    f.addEventListener('submit', function(ev) {
      ev.preventDefault();
      openModal();
      const data = new FormData(f);
      fetch(f.action, {method: 'POST', body: data})
        .then(resp => resp.text().then(() => resp.url))
        .then(url => { setTimeout(() => { closeModal(); window.location.href = url; }, 1000); });
    });
  });
});
