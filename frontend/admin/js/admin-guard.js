// Page-load role guard for admin pages — extracted from what used to be an identical inline
// <script> block copy-pasted onto every admin page (CSP hardening: script-src can't allow
// 'unsafe-inline' once every inline script is external). Reads the allowed-roles list from this
// script tag's own data-allowed-roles attribute so one file serves every admin page instead of
// a new inline copy per page's role requirements.
(function () {
  const user = JSON.parse(localStorage.getItem('admin_data') || 'null');
  if (!user) {
    window.location.replace('./login.html');
    return;
  }
  const allowedRoles = (document.currentScript.dataset.allowedRoles || 'admin,super_admin,manager,support').split(',');
  if (!allowedRoles.includes(user.role)) {
    window.location.replace('../customer/index.html');
  }
})();
