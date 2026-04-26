'use strict';

/* ---- Hamburger menu ---- */
(function () {
  var hamburger = document.getElementById('hamburger');
  var navLinks  = document.getElementById('navLinks');
  if (!hamburger || !navLinks) { return; }
  hamburger.addEventListener('click', function () {
    var isOpen = navLinks.classList.toggle('open');
    hamburger.setAttribute('aria-expanded', String(isOpen));
  });
  // Close on nav link click (mobile)
  navLinks.querySelectorAll('a').forEach(function(a) {
    a.addEventListener('click', function() {
      navLinks.classList.remove('open');
      hamburger.setAttribute('aria-expanded', 'false');
    });
  });
}());

/* ---- Navbar shadow on scroll ---- */
(function () {
  var navbar = document.querySelector('.navbar');
  if (!navbar) { return; }
  window.addEventListener('scroll', function () {
    navbar.style.boxShadow = window.scrollY > 50
      ? '0 4px 30px rgba(201, 96, 122, 0.1)'
      : 'none';
  }, { passive: true });
}());

/* ---- Scroll reveal ---- */
(function () {
  function initReveal() {
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('visible');
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.1 });
    document.querySelectorAll('.reveal').forEach(function (el) {
      observer.observe(el);
    });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initReveal);
  } else {
    initReveal();
  }
}());
