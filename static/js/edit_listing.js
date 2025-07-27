// static/js/edit_listing.js

document.addEventListener('DOMContentLoaded', () => {
  // === [ 0. FALLBACK IMAGE HANDLER FOR MOCKUP THUMBS ] ===
  document.querySelectorAll('.mockup-thumb-img').forEach(img => {
    img.addEventListener('error', function handleError() {
      if (this.dataset.fallback && this.src !== this.dataset.fallback) {
        this.src = this.dataset.fallback;
      } else {
        // Uncomment below if you want a default fallback as LAST resort
        // this.src = '/static/img/default-mockup.jpg';
      }
      this.onerror = null; // Prevent loop
    });
  });

  // === [ 1. MODAL CAROUSEL LOGIC ] ===
  const carousel = document.getElementById('mockup-carousel');
  const carouselImg = document.getElementById('carousel-img');
  const images = Array.from(document.querySelectorAll('.mockup-img-link, .main-thumb-link'));
  let currentIndex = 0;

  function showImage(index) {
    if (index >= 0 && index < images.length) {
      currentIndex = index;
      carouselImg.src = images[currentIndex].dataset.img;
      carousel.classList.add('active');
    }
  }

  images.forEach((link, index) => {
    link.addEventListener('click', (e) => {
      e.preventDefault();
      showImage(index);
    });
  });

  if (carousel) {
    carousel.querySelector('#carousel-close').addEventListener('click', () => carousel.classList.remove('active'));
    carousel.querySelector('#carousel-prev').addEventListener('click', () => showImage((currentIndex - 1 + images.length) % images.length));
    carousel.querySelector('#carousel-next').addEventListener('click', () => showImage((currentIndex + 1) % images.length));
    document.addEventListener('keydown', (e) => {
      if (carousel.classList.contains('active')) {
        if (e.key === 'ArrowLeft') showImage((currentIndex - 1 + images.length) % images.length);
        if (e.key === 'ArrowRight') showImage((currentIndex + 1) % images.length);
        if (e.key === 'Escape') carousel.classList.remove('active');
      }
    });
  }

  // === [ 2. ASYNC MOCKUP SWAP LOGIC ] ===
  document.querySelectorAll('.swap-btn').forEach(button => {
    button.addEventListener('click', async (event) => {
      event.preventDefault();

      const btnContainer = button.parentElement;
      if (btnContainer.classList.contains('swapping')) return; // Prevent double-clicks

      const slotIndex = parseInt(button.dataset.index, 10);
      const form = button.closest('.swap-form');
      const select = form.querySelector('select[name="new_category"]');
      const newCategory = select.value;

      // Start loading state
      btnContainer.classList.add('swapping');

      try {
        const response = await fetch('/edit/swap-mockup-api', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            seo_folder: window.EDIT_INFO.seoFolder,
            slot_index: slotIndex,
            new_category: newCategory,
            aspect: window.EDIT_INFO.aspect
          }),
        });

        const data = await response.json();

        if (!response.ok || !data.success) {
          throw new Error(data.error || 'Failed to swap mockup.');
        }

        // Update the image and link on success
        const timestamp = new Date().getTime();
        const mockupImg = document.getElementById(`mockup-img-${slotIndex}`);
        const mockupLink = document.getElementById(`mockup-link-${slotIndex}`);

        if (mockupImg) {
          mockupImg.src = `${data.new_thumb_url}?t=${timestamp}`;
          mockupImg.dataset.fallback = `${data.new_mockup_url}?t=${timestamp}`;
        }
        if (mockupLink) {
          mockupLink.href = `${data.new_mockup_url}?t=${timestamp}`;
          mockupLink.dataset.img = `${data.new_mockup_url}?t=${timestamp}`;
        }

      } catch (error) {
        console.error('Swap failed:', error);
        alert(`Error: ${error.message}`);
      } finally {
        // End loading state
        btnContainer.classList.remove('swapping');
      }
    });
  });
});
