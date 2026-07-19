// Shared helpers + page chrome for every authed admin page. Plain global-scope script
// (no modules — see scripts/build-dist.js); load order: config.js, api.js, admin-config.js,
// admin-api.js, THIS FILE, then the page's own JS. Replaces per-page copies of these helpers
// and the identical inline theme/logout <script> blocks that were duplicated per page.

function getAdminData() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEYS.ADMIN_DATA) || 'null');
  } catch {
    return null;
  }
}

// The access token lives in memory only (see js/admin-api.js) and is restored lazily on the
// first API call, so it isn't checked here — only the cached (non-sensitive) profile.
// Pass `allowedRoles` to additionally gate the page to specific admin roles.
function requireAuth(allowedRoles) {
  const adminData = getAdminData();
  if (!adminData) {
    window.location.replace('./login.html');
    return false;
  }
  if (allowedRoles && !allowedRoles.includes(adminData.role)) {
    window.location.replace('../customer/index.html');
    return false;
  }
  return true;
}

function formatCurrency(value) {
  return `Rs ${Number(value || 0).toLocaleString('en-PK', { minimumFractionDigits: 0, maximumFractionDigits: 2 })}`;
}

function formatDate(value) {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '-';
  return date.toLocaleDateString('en-PK', { year: 'numeric', month: 'short', day: 'numeric' });
}

// showToast is defined once in shared/js/api.js and loaded before this file on every admin page.

// ─── PAGE CHROME: saved theme + header theme toggle + logout ───
(function () {
  const saved = localStorage.getItem('ecom_theme') || 'dark';
  document.documentElement.setAttribute('data-theme', saved);

  document.addEventListener('DOMContentLoaded', () => {
    const icon = document.getElementById('theme-icon');
    if (icon) icon.className = saved === 'dark' ? 'fas fa-moon' : 'fas fa-sun';

    document.getElementById('theme-toggle')?.addEventListener('click', () => {
      const html = document.documentElement;
      const next = (html.getAttribute('data-theme') || 'dark') === 'dark' ? 'light' : 'dark';
      html.setAttribute('data-theme', next);
      localStorage.setItem('ecom_theme', next);
      if (icon) icon.className = next === 'dark' ? 'fas fa-moon' : 'fas fa-sun';
    });

    document.getElementById('nav-logout-btn')?.addEventListener('click', async () => {
      try {
        await adminAPI.logout();
      } catch {
        // Server-side logout failed — still clear the local session below.
      }
      localStorage.removeItem(STORAGE_KEYS.AUTH_TOKEN);
      localStorage.removeItem(STORAGE_KEYS.REFRESH_TOKEN);
      localStorage.removeItem(STORAGE_KEYS.ADMIN_DATA);
      window.location.href = './login.html';
    });
  });
})();
