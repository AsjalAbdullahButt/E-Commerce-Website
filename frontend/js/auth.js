// === AUTH.JS ===
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

const TOKEN_KEY = 'ecom_token';
const USER_KEY  = 'ecom_user';

function getToken()  {
  return sessionStorage.getItem(TOKEN_KEY);
}

function getUser() {
  const u = sessionStorage.getItem(USER_KEY);
  return u ? JSON.parse(u) : null;
}

function isLoggedIn() {
  return !!getToken();
}

function clearAuth() {
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(USER_KEY);
}

function requireAuth(allowedRoles = []) {
  const user = getUser();
  if (!user) {
    redirectToLogin();
    return null;
  }
  if (allowedRoles.length && !allowedRoles.includes(user.role)) {
    window.location.href = '../index.html';
    return null;
  }
  return user;
}

async function login(email, password) {
  const data = await api.post('/auth/login', { email, password });
  sessionStorage.setItem(TOKEN_KEY, data.access_token);
  sessionStorage.setItem(USER_KEY, JSON.stringify(data.user));
  return data.user;
}

async function register(name, email, password, phone) {
  const data = await api.post('/auth/register', {
    name,
    email,
    password,
    phone
  });
  sessionStorage.setItem(TOKEN_KEY, data.access_token);
  sessionStorage.setItem(USER_KEY, JSON.stringify(data.user));
  return data.user;
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
  window.location.href = './index.html';
}

function redirectAfterLogin(role) {
  const routes = {
    admin:    './admin/dashboard.html',
    rider:    './rider/dashboard.html',
    customer: './profile.html'
  };
  window.location.href = routes[role] || './index.html';
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
        icon.className = isPassword ? 'fas fa-eye-slash' : 'fas fa-eye';
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
        icon.className = isPassword ? 'fas fa-eye-slash' : 'fas fa-eye';
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
        icon.className = isPassword ? 'fas fa-eye-slash' : 'fas fa-eye';
      }
    });
  }
});
