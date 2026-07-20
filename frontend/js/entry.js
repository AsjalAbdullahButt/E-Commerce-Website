// Single entry point: same site, different home per role. Reuses the token/role helpers
// from shared/js/auth.js rather than re-deriving session state.
(async function routeToHome() {
  const HOME_BY_ROLE = {
    customer: './customer/index.html',
    admin: './admin/dashboard.html',
    rider: './rider/dashboard.html',
  };

  if (!isLoggedIn()) {
    window.location.replace('./auth/login.html');
    return;
  }

  try {
    // Validates the token against the server (not just localStorage presence) and returns
    // the authoritative current role. api.js's apiRequest already handles a 401 here by
    // clearing the session and redirecting to ./auth/login.html, so we only need the
    // success path.
    const profile = await api.get('/auth/me', true);
    if (!profile) return; // apiRequest already redirected on 401

    localStorage.setItem('ecom_role', profile.role);
    window.location.replace(HOME_BY_ROLE[profile.role] || './customer/index.html');
  } catch (err) {
    console.error('Session check failed:', err);
    clearAuth();
    window.location.replace('./auth/login.html');
  }
})();
