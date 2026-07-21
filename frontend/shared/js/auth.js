// === AUTH.JS (SHARED) ===
// Single source for all authentication logic

// ─── THEME SYSTEM (runs before DOM loads to prevent flash) ───
(function initTheme() {
  const saved = localStorage.getItem('ecom_theme') || 'dark'; // dark = default
  document.documentElement.setAttribute('data-theme', saved);
  // Sync icon once DOM is ready
  document.addEventListener('DOMContentLoaded', function() {
    const icon = document.getElementById('theme-icon');
    if (icon) icon.className = saved === 'dark' ? 'fas fa-moon' : 'fas fa-sun';
  });
})();

function toggleTheme() {
  const html = document.documentElement;
  const current = html.getAttribute('data-theme') || 'dark';
  const next = current === 'dark' ? 'light' : 'dark';
  html.setAttribute('data-theme', next);
  localStorage.setItem('ecom_theme', next);
  const icon = document.getElementById('theme-icon');
  if (icon) {
    icon.className = next === 'dark' ? 'fas fa-moon' : 'fas fa-sun';
    // Brief spin animation
    icon.style.transform = 'rotate(360deg)';
    icon.style.transition = 'transform 0.4s ease';
    setTimeout(() => { icon.style.transform = ''; icon.style.transition = ''; }, 400);
  }
}

const USER_KEY  = 'ecom_user';
const ROLE_KEY  = 'ecom_role';

// getToken() reflects the in-memory access token (see shared/js/api.js) — null right after a
// page load until an authenticated call silently restores it via /auth/refresh.
function getToken()  {
  return getAccessToken();
}

function getUser() {
  const u = localStorage.getItem(USER_KEY);
  return u ? JSON.parse(u) : null;
}

function getRole() {
  return localStorage.getItem(ROLE_KEY);
}

// Based on the (non-sensitive) cached profile rather than the in-memory token, since the token
// itself is intentionally empty right after a fresh page load.
function isLoggedIn() {
  return !!getUser();
}

function clearAuth() {
  setAccessToken(null);
  localStorage.removeItem(USER_KEY);
  localStorage.removeItem(ROLE_KEY);
}

// ─── ROLE-BASED PAGE PROTECTION ───
function requireRole(requiredRoles) {
  const user = getUser();
  const role = getRole();
  
  if (!user || !role) {
    redirectToLogin();
    return null;
  }
  
  if (!requiredRoles.includes(role)) {
    // Unauthorized - redirect based on actual role
    const redirects = {
      admin: '../admin/dashboard.html',
      rider: '../rider/dashboard.html',
      customer: '../customer/index.html'
    };
    window.location.href = redirects[role] || '../customer/index.html';
    return null;
  }
  
  return user;
}

async function login(email, password) {
  try {
    const data = await api.post('/auth/login', { email, password });
    setAccessToken(data.access_token);
    localStorage.setItem(USER_KEY, JSON.stringify(data.user));
    localStorage.setItem(ROLE_KEY, data.user.role);
    return data.user;
  } catch (err) {
    console.error('Login failed:', err);
    throw err;
  }
}

async function register(name, email, password, phone) {
  try {
    const data = await api.post('/auth/register', {
      name,
      email,
      password,
      phone
    });
    setAccessToken(data.access_token);
    localStorage.setItem(USER_KEY, JSON.stringify(data.user));
    localStorage.setItem(ROLE_KEY, data.user.role);
    return data.user;
  } catch (err) {
    console.error('Registration failed:', err);
    throw err;
  }
}

async function logout() {
  try {
    // Call logout endpoint to clear server-side refresh token
    await api.post('/auth/logout', {}, true);
  } catch (err) {
    console.error('Logout API call failed:', err);
  }
  // Clear local session regardless of API response
  clearAuth();
  redirectToLogin();
}

// redirectToLogin() consolidated into api.js

// ─── GOOGLE SIGN-IN ───
// Called from login.html/register.html after the page loads. Fetches GET /auth/providers first
// so the button (and its divider) stay hidden entirely when GOOGLE_OAUTH_ENABLED=false server
// side -- there's never a dead button on screen while the feature is off, and the frontend never
// hardcodes a client ID.
async function initGoogleSignIn(containerId, dividerId) {
  let providers;
  try {
    providers = await api.get('/auth/providers');
  } catch (err) {
    return; // fail closed: no confirmation it's enabled, so no button
  }
  if (!providers || !providers.google_oauth_enabled || !providers.google_client_id) return;

  const container = document.getElementById(containerId);
  const divider = document.getElementById(dividerId);
  if (!container) return;
  // .google-signin-wrap holds both the real (invisible) button and our themed stand-in
  // (see auth.css) — fall back to the container itself if the wrapper markup isn't present.
  const wrap = container.closest('.google-signin-wrap') || container;

  const renderNow = () => {
    if (!window.google || !window.google.accounts || !window.google.accounts.id) return;
    window.google.accounts.id.initialize({
      client_id: providers.google_client_id,
      callback: handleGoogleCredentialResponse,
    });
    window.google.accounts.id.renderButton(container, {
      // Theme choice is irrelevant to what's visible — this real button renders fully
      // transparent (see .google-signin-container in auth.css) and only exists to receive
      // the actual click; the gold-themed .google-signin-visual button underneath is what
      // the user sees, since Google's brand guidelines don't allow recoloring the real button.
      type: 'standard', theme: 'filled_black', size: 'large', shape: 'pill',
      text: 'continue_with', logo_alignment: 'center', width: 320,
    });
    wrap.style.display = 'flex';
    if (divider) divider.style.display = 'flex';
  };

  // The GIS <script> tag is loaded async/defer, so window.google may not exist yet when this
  // runs on DOMContentLoaded -- window.onGoogleLibraryLoad is GIS's own "script is ready" hook.
  if (window.google && window.google.accounts && window.google.accounts.id) {
    renderNow();
  } else {
    window.onGoogleLibraryLoad = renderNow;
  }
}

async function handleGoogleCredentialResponse(googleResponse) {
  try {
    const data = await api.post('/auth/google', { id_token: googleResponse.credential });
    setAccessToken(data.access_token);
    localStorage.setItem(USER_KEY, JSON.stringify(data.user));
    localStorage.setItem(ROLE_KEY, data.user.role);
    showToast('Signed in with Google! Redirecting...', 'success');
    setTimeout(() => redirectAfterLogin(data.user.role), 1000);
  } catch (err) {
    console.error('Google sign-in failed:', err);
    showToast(err.message || 'Google sign-in failed. Please try again.', 'error');
  }
}

// Shared shake-on-invalid feedback for auth/checkout style forms.
function shakeField(input) {
  const group = input?.closest('.form-group');
  if (!group) return;
  group.classList.remove('shake');
  void group.offsetWidth;
  group.classList.add('shake');
  group.addEventListener('animationend', () => group.classList.remove('shake'), { once: true });
}

function redirectAfterLogin(role) {
  const routes = {
    admin:    '../admin/dashboard.html',
    rider:    '../rider/dashboard.html',
    customer: '../customer/index.html'
  };
  window.location.href = routes[role] || '../customer/index.html';
}

// Update navbar on every page load
document.addEventListener('DOMContentLoaded', () => {
  const user = getUser();
  const profileBtn = document.getElementById('nav-profile-btn');
  const logoutBtn  = document.getElementById('nav-logout-btn');
  const loginBtn   = document.getElementById('nav-login-btn');

  if (user) {
    if (profileBtn) profileBtn.style.display = 'flex';
    if (logoutBtn) {
      logoutBtn.style.display = 'flex';
      logoutBtn.addEventListener('click', logout);
    }
    if (loginBtn) loginBtn.style.display = 'none';
  } else {
    if (profileBtn) profileBtn.style.display = 'none';
    if (logoutBtn) logoutBtn.style.display = 'none';
    if (loginBtn) loginBtn.style.display = 'flex';
  }

  // Theme toggle button
  const themeBtn = document.getElementById('theme-toggle');
  if (themeBtn) themeBtn.addEventListener('click', toggleTheme);

  // Password visibility toggles - Login
  const loginToggleBtn = document.getElementById('login-toggle-pwd');
  const loginPasswordInput = document.getElementById('login-password');
  if (loginToggleBtn && loginPasswordInput) {
    loginToggleBtn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      const isPassword = loginPasswordInput.type === 'password';
      loginPasswordInput.type = isPassword ? 'text' : 'password';
      const icon = loginToggleBtn.querySelector('i');
      if (icon) {
        icon.className = isPassword ? 'fas fa-eye' : 'fas fa-eye-slash';
      }
    });
  }

  // Password visibility toggles - Register (Password field)
  const registerToggleBtn = document.getElementById('register-toggle-pwd');
  const registerPasswordInput = document.getElementById('register-password');
  if (registerToggleBtn && registerPasswordInput) {
    registerToggleBtn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      const isPassword = registerPasswordInput.type === 'password';
      registerPasswordInput.type = isPassword ? 'text' : 'password';
      const icon = registerToggleBtn.querySelector('i');
      if (icon) {
        icon.className = isPassword ? 'fas fa-eye' : 'fas fa-eye-slash';
      }
    });
  }

  // Password visibility toggles - Register (Confirm Password field)
  const registerToggleConfirmBtn = document.getElementById('register-toggle-confirm');
  const registerConfirmInput = document.getElementById('register-confirm');
  if (registerToggleConfirmBtn && registerConfirmInput) {
    registerToggleConfirmBtn.addEventListener('click', (e) => {
      e.preventDefault();
      e.stopPropagation();
      const isPassword = registerConfirmInput.type === 'password';
      registerConfirmInput.type = isPassword ? 'text' : 'password';
      const icon = registerToggleConfirmBtn.querySelector('i');
      if (icon) {
        icon.className = isPassword ? 'fas fa-eye' : 'fas fa-eye-slash';
      }
    });
  }
});
