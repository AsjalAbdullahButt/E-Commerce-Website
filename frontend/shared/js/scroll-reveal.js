// === SCROLL-REVEAL.JS ===
// Adds .in-view to .reveal / .reveal-stagger elements as they enter the viewport.
// Pure IntersectionObserver, no dependencies. Respects prefers-reduced-motion via CSS
// (global.css forces opacity:1 there), so no JS branching is needed for that case.

(function () {
  function initScrollReveal() {
    const targets = document.querySelectorAll('.reveal, .reveal-stagger');
    if (!targets.length) return;

    if (!('IntersectionObserver' in window)) {
      targets.forEach(el => el.classList.add('in-view'));
      return;
    }

    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('in-view');
          observer.unobserve(entry.target);
        }
      });
    // threshold 0 (any overlap), not a ratio: a ratio can never be reached by containers that
    // are empty when observed (their content arrives async — e.g. the shop grid's skeletons),
    // and elements much taller than the viewport would never hit it either, staying invisible.
    // The -60px rootMargin is what keeps reveals from firing prematurely.
    }, { threshold: 0, rootMargin: '0px 0px -60px 0px' });

    targets.forEach(el => observer.observe(el));
  }

  document.addEventListener('DOMContentLoaded', initScrollReveal);
})();
