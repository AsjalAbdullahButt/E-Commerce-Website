// === AUTH.JS ===
// Single source for all authentication logic

const TOKEN_KEY = 'tribe_token';
const USER_KEY  = 'tribe_user';

function getToken()  {
  return localStorage.getItem(TOKEN_KEY);
}

function getUser() {
  const u = localStorage.getItem(USER_KEY);
  return u ? JSON.parse(u) : null;
}

function isLoggedIn() {
  return !!getToken();
}

function clearAuth() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
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
  localStorage.setItem(TOKEN_KEY, data.access_token);
  localStorage.setItem(USER_KEY, JSON.stringify(data.user));
  return data.user;
}

async function register(name, email, password, phone) {
  const data = await api.post('/auth/register', {
    name,
    email,
    password,
    phone
  });
  localStorage.setItem(TOKEN_KEY, data.access_token);
  localStorage.setItem(USER_KEY, JSON.stringify(data.user));
  return data.user;
}

function logout() {
  clearAuth();
  window.location.href = './login.html';
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

  // Hamburger menu
  const hamburger = document.getElementById('hamburger');
  const navLinks = document.getElementById('nav-links');
  if (hamburger) {
    hamburger.addEventListener('click', () => {
      navLinks.classList.toggle('open');
    });
  }
});
