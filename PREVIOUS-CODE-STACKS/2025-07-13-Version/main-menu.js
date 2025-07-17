// main-menu.js - Responsive toggle for main menu

document.addEventListener('DOMContentLoaded', function() {
  var toggle = document.querySelector('.menu-toggle');
  var links = document.querySelector('.menu-links');
  toggle.addEventListener('click', function() {
    links.classList.toggle('active');
  });
});