// === PRODUCT-TILT.JS ===
// Cursor-tracked 3D tilt for .product-card + magnetic pull/pop for .magnetic-btn.
// Event-delegated on document so it keeps working after shop.js/home.js re-render
// the grid — no rebinding needed. Pointer-fine + motion-safe only; touch/reduced-motion
// devices fall back to the plain CSS :hover lift already defined per-page.

(function () {
  const fine = window.matchMedia('(pointer: fine)').matches;
  const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const MAX_TILT = 10; // degrees
  const MAGNET_RANGE = 18; // px

  let activeCard = null;
  let activeBtn = null;

  function resetCard(card) {
    card.classList.remove('tilting');
    card.style.transform = '';
  }

  function resetBtn(btn) {
    btn.style.transform = '';
  }

  function handleMove(e) {
    const card = e.target.closest('.product-card');
    if (card !== activeCard) {
      if (activeCard) resetCard(activeCard);
      if (card) card.classList.add('tilting');
      activeCard = card;
    }
    if (card) {
      const rect = card.getBoundingClientRect();
      const px = (e.clientX - rect.left) / rect.width;
      const py = (e.clientY - rect.top) / rect.height;
      const rotateY = (px - 0.5) * MAX_TILT * 2;
      const rotateX = (0.5 - py) * MAX_TILT * 2;
      card.style.transform = `perspective(900px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) scale3d(1.02,1.02,1.02)`;
      card.style.setProperty('--mx', `${px * 100}%`);
      card.style.setProperty('--my', `${py * 100}%`);
    }

    const btn = e.target.closest('.magnetic-btn');
    if (btn !== activeBtn) {
      if (activeBtn) resetBtn(activeBtn);
      activeBtn = btn;
    }
    if (btn) {
      const rect = btn.getBoundingClientRect();
      const dx = e.clientX - (rect.left + rect.width / 2);
      const dy = e.clientY - (rect.top + rect.height / 2);
      const pull = Math.min(1, MAGNET_RANGE / Math.max(1, Math.hypot(dx, dy)));
      btn.style.transform = `translate(${dx * 0.15 * pull}px, ${dy * 0.35 * pull}px)`;
    }
  }

  function resetAll() {
    if (activeCard) resetCard(activeCard);
    if (activeBtn) resetBtn(activeBtn);
    activeCard = null;
    activeBtn = null;
  }

  if (fine && !reduced) {
    document.addEventListener('pointermove', handleMove);
    document.documentElement.addEventListener('pointerleave', resetAll);
    window.addEventListener('blur', resetAll);
  }

  // Click "pop" feedback works everywhere (CSS neutralizes it under reduced-motion).
  // .pop-btn gets the pop only (no magnetic pull) — used for small fixed-position
  // icon buttons like the wishlist heart, where pulling toward the cursor would
  // look detached from the card corner it's anchored to.
  document.addEventListener('click', (e) => {
    const btn = e.target.closest('.magnetic-btn, .pop-btn');
    if (!btn) return;
    btn.classList.remove('pop');
    // Force reflow so the animation restarts on rapid repeat clicks.
    void btn.offsetWidth;
    btn.classList.add('pop');
    btn.addEventListener('animationend', () => btn.classList.remove('pop'), { once: true });
  });
})();
