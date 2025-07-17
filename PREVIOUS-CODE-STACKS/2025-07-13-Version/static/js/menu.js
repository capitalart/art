document.addEventListener('DOMContentLoaded', () => {
  const btn = document.getElementById('mega-button');
  const menu = document.getElementById('mega-menu');
  const overlay = document.getElementById('mega-overlay');
  const arrow = document.getElementById('mega-arrow');
  if (!btn || !menu) return;

  const openArrow = '▲';
  const closeArrow = '▼';

  function openMenu() {
    menu.classList.add('open');
    if (overlay) overlay.classList.add('active');
    btn.setAttribute('aria-expanded', 'true');
    if (arrow) arrow.textContent = openArrow;
  }

  function closeMenu() {
    menu.classList.remove('open');
    if (overlay) overlay.classList.remove('active');
    btn.setAttribute('aria-expanded', 'false');
    if (arrow) arrow.textContent = closeArrow;
  }

  btn.addEventListener('click', () => {
    if (menu.classList.contains('open')) {
      closeMenu();
    } else {
      openMenu();
    }
  });

  if (overlay) {
    overlay.addEventListener('click', closeMenu);
  }

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeMenu();
  });
});
