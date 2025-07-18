// Overlay menu functionality with accessibility

document.addEventListener('DOMContentLoaded', () => {
  const menuBtn = document.getElementById('menu-toggle');
  const overlay = document.getElementById('overlay-menu');
  const closeBtn = document.getElementById('overlay-close');
  const body = document.body;
  const arrowSpan = menuBtn ? menuBtn.querySelector('.arrow') : null;
  let lastFocused;

  const focusableSelector = 'a, button';

  function openMenu() {
    overlay.classList.add('open');
    menuBtn.setAttribute('aria-expanded', 'true');
    arrowSpan.textContent = '▲';
    body.classList.add('no-scroll');
    lastFocused = document.activeElement;
    const focusables = overlay.querySelectorAll(focusableSelector);
    if (focusables.length) focusables[0].focus();
  }

  function closeMenu() {
    overlay.classList.remove('open');
    menuBtn.setAttribute('aria-expanded', 'false');
    arrowSpan.textContent = '▼';
    body.classList.remove('no-scroll');
    if (lastFocused) lastFocused.focus();
  }

  if (menuBtn) {
    menuBtn.addEventListener('click', () => {
      if (overlay.classList.contains('open')) {
        closeMenu();
      } else {
        openMenu();
      }
    });
  }

  if (closeBtn) closeBtn.addEventListener('click', closeMenu);

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape' && overlay.classList.contains('open')) {
      closeMenu();
    }
  });

  overlay.addEventListener('click', e => {
    if (e.target === overlay) closeMenu();
  });

  overlay.addEventListener('keydown', e => {
    if (e.key !== 'Tab') return;
    const focusables = Array.from(overlay.querySelectorAll(focusableSelector));
    if (!focusables.length) return;
    const first = focusables[0];
    const last = focusables[focusables.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  });
});
