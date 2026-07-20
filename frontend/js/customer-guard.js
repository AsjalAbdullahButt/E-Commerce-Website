// Pre-render guard only, to avoid a flash of protected content — the access token itself lives
// in memory only (see shared/js/api.js) and isn't available this early, so this checks the
// non-sensitive cached profile instead. Actual auth is enforced server-side on every API call
// regardless. Set data-allow-guest-email="true" on this script tag for pages a guest order's
// tracking link (?guest_email=...) may also reach without a session — see js/checkout.js and
// js/tracking.js.
(function () {
  const user = localStorage.getItem('ecom_user');
  const role = localStorage.getItem('ecom_role');
  const allowGuestEmail = document.currentScript.dataset.allowGuestEmail === 'true';
  const isGuestLink = allowGuestEmail && new URLSearchParams(window.location.search).has('guest_email');
  if ((!user || role !== 'customer') && !isGuestLink) {
    window.location.replace('../auth/login.html');
  }
})();
