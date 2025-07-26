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
  // Legacy AJAX swap disabled; form now submits normally to backend

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

