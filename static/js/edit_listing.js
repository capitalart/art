/* ==============================
   ArtNarrator Edit Listing JS
   ============================== */

/* --------- [ EL1. Carousel Modal ] --------- */
document.addEventListener('DOMContentLoaded', () => {
  const carousel = document.getElementById('mockup-carousel');
  const imgEl = document.getElementById('carousel-img');
  const closeBtn = document.getElementById('carousel-close');
  const prevBtn = document.getElementById('carousel-prev');
  const nextBtn = document.getElementById('carousel-next');

  const links = Array.from(document.querySelectorAll('.mockup-img-link'));
  const thumb = document.querySelector('.main-thumb-link');
  if (thumb) links.unshift(thumb);
  const images = links.map(l => l.dataset.img);
  let idx = 0;

  function show(i) {
    idx = (i + images.length) % images.length;
    imgEl.src = images[idx];
    carousel.classList.add('active');
  }
  function close() {
    carousel.classList.remove('active');
    imgEl.src = '';
  }
  links.forEach((link, i) => {
    link.addEventListener('click', e => {
      e.preventDefault();
      show(i);
    });
  });
  if (closeBtn) closeBtn.onclick = close;
  if (prevBtn) prevBtn.onclick = () => show(idx - 1);
  if (nextBtn) nextBtn.onclick = () => show(idx + 1);
  if (carousel) carousel.addEventListener('click', e => { if (e.target === carousel) close(); });
  document.addEventListener('keydown', e => {
    if (!carousel.classList.contains('active')) return;
    if (e.key === 'Escape') close();
    else if (e.key === 'ArrowLeft') show(idx - 1);
    else if (e.key === 'ArrowRight') show(idx + 1);
  });


  /* --------- [ EL2. Swap Mockup Forms ] --------- */
  const swapButtons = document.querySelectorAll('.swap-btn');

  async function swapMockup(slot) {
    const form = document.getElementById(`swap-form-${slot}`);
    if (!form) return;
    const select = form.querySelector('select');
    const btn = form.querySelector('button');
    btn.disabled = true;

    const payload = {
      seo_filename: window.EDIT_INFO.seoFolder,
      aspect_ratio: window.EDIT_INFO.aspect,
      slot_index: slot,
      category: select.value
    };

    try {
      const res = await fetch('/swap-mockup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.success) {
        const img = document.getElementById(`mockup-img-${slot}`);
        const link = document.getElementById(`mockup-link-${slot}`);
        const ts = Date.now();
        if (img) img.src = data.new_thumb + '?t=' + ts;
        if (link) {
          link.dataset.img = data.new_full + '?t=' + ts;
          link.href = data.new_full + '?t=' + ts;
        }
      } else {
        alert(data.error || 'Failed to swap mockup');
      }
    } catch (err) {
      console.error('Swap error', err);
      alert('Error swapping mockup');
    }

    btn.disabled = false;
  }

  swapButtons.forEach((btn, idx) => {
    btn.addEventListener('click', e => {
      e.preventDefault();
      swapMockup(idx);
    });
  });

  /* --------- [ EL3. Enable Action Buttons ] --------- */
  function toggleActionBtns() {
    const txt = document.querySelector('textarea[name="images"]');
    const disabled = !(txt && txt.value.trim());
    document.querySelectorAll('.require-images').forEach(btn => {
      btn.disabled = disabled;
    });
  }
  const imagesTextarea = document.querySelector('textarea[name="images"]');
  if (imagesTextarea) imagesTextarea.addEventListener('input', toggleActionBtns);
  toggleActionBtns();
});

