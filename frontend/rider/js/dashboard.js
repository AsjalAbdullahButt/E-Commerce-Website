document.addEventListener('DOMContentLoaded', () => {
  const user = requireRole(['rider']);
  if (user) {
    document.getElementById('rider-name').textContent = user.name || 'Rider';
    loadStats();
  }
  document.getElementById('nav-logout-btn').addEventListener('click', logout);
});

function animateStatNumber(id, endValue) {
  const node = document.getElementById(id);
  if (!node) return;
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
    node.textContent = String(endValue);
    return;
  }
  const duration = 800;
  const startTime = performance.now();
  const step = (now) => {
    const progress = Math.min(1, (now - startTime) / duration);
    const eased = 1 - Math.pow(1 - progress, 3);
    node.textContent = String(Math.round(endValue * eased));
    if (progress < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

async function loadStats() {
  try {
    // /rider/orders only returns orders still in progress (shipped/confirmed/packed) —
    // it never includes delivered orders, so "delivered" must come from /rider/stats instead,
    // which counts across the rider's full order history server-side.
    const [activeOrders, stats] = await Promise.all([
      api.get('/rider/orders', true),
      api.get('/rider/stats', true),
    ]);

    const pending = Array.isArray(activeOrders) ? activeOrders.length : 0;
    const delivered = stats?.delivered || 0;

    animateStatNumber('stat-total', pending + delivered);
    animateStatNumber('stat-pending', pending);
    animateStatNumber('stat-delivered', delivered);
  } catch (err) {
    console.error('Failed to load stats:', err);
  }
}
