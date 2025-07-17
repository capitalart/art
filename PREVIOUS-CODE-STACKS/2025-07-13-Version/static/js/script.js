/* ==========================================================================
   File: script.js
   Purpose: Handles interactive logic for the menu and theme toggling.
   ========================================================================== */

document.addEventListener("DOMContentLoaded", function () {
    const bodyTag = document.body;
    const htmlTag = document.documentElement;

    // === [ THEME TOGGLE LOGIC ] ===
    const themeToggle = document.getElementById("themeToggle");
    const themeToggleOverlay = document.getElementById("themeToggleOverlay");
    const themeIcon = document.getElementById("themeIcon");
    const themeIconOverlay = document.getElementById("themeIconOverlay");
    
    const userIcon = document.getElementById("userIcon");
    const userIconOverlay = document.getElementById("userIconOverlay");
    const userAuthLink = document.getElementById("userAuthLink");
    const userAuthLinkOverlay = document.getElementById("userAuthLinkOverlay");

    const icons = {
        sun: 'static/icons/svg/light/sun-light.svg',
        moon: 'static/icons/svg/light/moon-light.svg',
        user: 'static/icons/svg/light/user-circle-light.svg',
        userChecked: 'static/icons/svg/light/user-circle-check-light.svg'
    };

    const setTheme = (isDark) => {
        htmlTag.classList.toggle('dark', isDark);
        if (themeIcon) themeIcon.src = isDark ? icons.sun : icons.moon;
        if (themeIconOverlay) themeIconOverlay.src = isDark ? icons.sun : icons.moon;
        localStorage.setItem('darkMode', isDark);
    };

    const savedThemeIsDark = localStorage.getItem('darkMode') === 'true';
    setTheme(savedThemeIsDark);

    const toggleTheme = () => {
        const isCurrentlyDark = htmlTag.classList.contains('dark');
        setTheme(!isCurrentlyDark);
    };

    if (themeToggle) themeToggle.addEventListener('click', toggleTheme);
    if (themeToggleOverlay) themeToggleOverlay.addEventListener('click', toggleTheme);
    
    let isLoggedIn = false;
    const toggleLogin = (e) => {
        e.preventDefault();
        isLoggedIn = !isLoggedIn;
        if (userIcon) userIcon.src = isLoggedIn ? icons.userChecked : icons.user;
        if (userIconOverlay) userIconOverlay.src = isLoggedIn ? icons.userChecked : icons.user;
    };

    if (userAuthLink) userAuthLink.addEventListener('click', toggleLogin);
    if (userAuthLinkOverlay) userAuthLinkOverlay.addEventListener('click', toggleLogin);


    // === [ OVERLAY MENU LOGIC ] ===
    const menuToggle = document.getElementById("menuToggle");
    const menuToggleOverlay = document.getElementById("menuToggleOverlay");
    const overlayMenu = document.getElementById("overlayMenu");

    const openMenu = () => {
        if (!overlayMenu) return;
        overlayMenu.classList.add("is-active");
        bodyTag.style.overflow = 'hidden';
    };

    const closeMenu = () => {
        if (!overlayMenu) return;
        overlayMenu.classList.remove("is-active");
        bodyTag.style.overflow = '';
    };

    if (menuToggle) menuToggle.addEventListener("click", openMenu);
    if (menuToggleOverlay) menuToggleOverlay.addEventListener("click", closeMenu);

    if (overlayMenu) {
      overlayMenu.querySelectorAll('a').forEach(link => {
        link.addEventListener('click', closeMenu);
      });
        overlayMenu.addEventListener('click', (event) => {
            if (event.target === overlayMenu) {
                closeMenu();
            }
        });
    }

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && overlayMenu.classList.contains('is-active')) {
            closeMenu();
        }
    });
});