document.addEventListener('DOMContentLoaded', () => {
  const toggle = document.getElementById('theme-toggle');
  const sunIcon = document.getElementById('icon-sun');
  const moonIcon = document.getElementById('icon-moon');
  const navToggle = document.getElementById('nav-toggle');
  const navLinks = document.getElementById('nav-links');
  const profileIcon = document.getElementById('profile-icon');
  const megaBtn = document.getElementById('mega-button');
  const megaMenu = document.getElementById('mega-menu');

  function applyTheme(theme) {
    document.documentElement.classList.remove('theme-light', 'theme-dark');
    document.documentElement.classList.add('theme-' + theme);
    document.body.classList.toggle('dark-theme', theme === 'dark');
    localStorage.setItem('theme', theme);
    sunIcon.style.display = theme === 'dark' ? 'none' : 'inline';
    moonIcon.style.display = theme === 'dark' ? 'inline' : 'none';
    if (profileIcon) {
      const base = '/static/icons/svg/';
      profileIcon.src = theme === 'dark'
        ? base + 'dark/user-circle-dark.svg'
        : base + 'light/user-circle-light.svg';
    }
  }

  const saved = localStorage.getItem('theme');
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const initial = saved || (prefersDark ? 'dark' : 'light');
  applyTheme(initial);

  if (toggle) {
    toggle.addEventListener('click', () => {
      const next = document.documentElement.classList.contains('theme-dark') ? 'light' : 'dark';
      applyTheme(next);
    });
  }

  if (navToggle && navLinks) {
    navToggle.addEventListener('click', () => {
      const open = navLinks.classList.toggle('active');
      navToggle.classList.toggle('open', open);
    });
    navLinks.querySelectorAll('a').forEach(a => {
      a.addEventListener('click', () => {
        navLinks.classList.remove('active');
        navToggle.classList.remove('open');
      });
    });
  }

  function setupDropdown(toggleId, menuId) {
    const t = document.getElementById(toggleId);
    const m = document.getElementById(menuId);
    if (!t || !m) return;
    const parent = t.parentElement;
    t.addEventListener('click', (ev) => {
      ev.preventDefault();
      const open = parent.classList.toggle('open');
      t.setAttribute('aria-expanded', open);
    });
    document.addEventListener('click', (ev) => {
      if (!parent.contains(ev.target)) {
        parent.classList.remove('open');
        t.setAttribute('aria-expanded', 'false');
      }
    });
    document.addEventListener('keydown', (ev) => {
      if (ev.key === 'Escape') {
        parent.classList.remove('open');
        t.setAttribute('aria-expanded', 'false');
      }
    });
  }

  setupDropdown('help-toggle', 'help-menu');
  setupDropdown('admin-toggle', 'admin-menu');
  setupDropdown('profile-toggle', 'profile-menu');

  function closeMega() {
    if (megaMenu) {
      megaMenu.classList.remove('open');
      if (megaBtn) megaBtn.setAttribute('aria-expanded', 'false');
    }
  }

  if (megaBtn && megaMenu) {
    megaBtn.addEventListener('click', (ev) => {
      ev.preventDefault();
      const open = megaMenu.classList.toggle('open');
      megaBtn.setAttribute('aria-expanded', open);
    });

    document.addEventListener('click', (ev) => {
      if (!megaMenu.contains(ev.target) && !megaBtn.contains(ev.target)) {
        closeMega();
      }
    });

    document.addEventListener('keydown', (ev) => {
      if (ev.key === 'Escape') {
        closeMega();
      }
    });

    document.querySelectorAll('.mega-col h3').forEach((h) => {
      h.addEventListener('click', () => {
        if (window.innerWidth < 700) {
          h.parentElement.classList.toggle('open');
        }
      });
    });
  }
});
