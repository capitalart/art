document.addEventListener('DOMContentLoaded', () => {
  const toggles = document.querySelectorAll('.theme-toggle');
  const sunIcons = document.querySelectorAll('.icon-sun');
  const moonIcons = document.querySelectorAll('.icon-moon');

  function applyTheme(theme) {
    document.documentElement.classList.remove('theme-light', 'theme-dark');
    document.documentElement.classList.add('theme-' + theme);
    localStorage.setItem('theme', theme);
    sunIcons.forEach(i => i.style.display = theme === 'dark' ? 'none' : 'inline');
    moonIcons.forEach(i => i.style.display = theme === 'dark' ? 'inline' : 'none');
  }

  const saved = localStorage.getItem('theme');
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const initial = saved || (prefersDark ? 'dark' : 'light');
  applyTheme(initial);

  toggles.forEach(btn => {
    btn.addEventListener('click', () => {
      const next = document.documentElement.classList.contains('theme-dark')
        ? 'light' : 'dark';
      applyTheme(next);
    });
  });
});
