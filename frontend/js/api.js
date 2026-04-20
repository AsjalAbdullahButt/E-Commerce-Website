// === API.JS ===
// All fetch calls go through here

// ════════════════════════════════════════════════════
// 1️⃣  REDIRECT TO LOGIN (called by apiRequest when 401)
// ════════════════════════════════════════════════════
function redirectToLogin() {
  const depth = window.location.pathname.split('/').filter(Boolean).length;
  const prefix = depth > 2 ? '../' : './';
  window.location.href = prefix + 'login.html';
}

// ════════════════════════════════════════════════════
// 2️⃣  CLEAR AUTH SESSION (safe session auth cleanup)
// ════════════════════════════════════════════════════
function clearAuthSession() {
  sessionStorage.removeItem('ecom_token');
  sessionStorage.removeItem('ecom_user');
}

// ════════════════════════════════════════════════════
// 3️⃣  SHOW TOAST GLOBAL (used by all pages)
// ════════════════════════════════════════════════════
function showToast(message, type = 'success', duration = 3000) {
  let toast = document.getElementById('global-toast');
  if (!toast) {
    toast = document.createElement('div');
    toast.id = 'global-toast';
    toast.className = 'toast';
    document.body.appendChild(toast);
  }
  toast.textContent = message;
  toast.className = `toast toast-${type} show`;
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => {
    toast.classList.remove('show');
  }, duration);
}

// ════════════════════════════════════════════════════
// 4️⃣  API REQUEST (main fetch handler)
// ════════════════════════════════════════════════════
async function apiRequest(method, endpoint, body = null, requiresAuth = false) {
  const headers = { 'Content-Type': 'application/json' };

  if (requiresAuth) {
    const token = sessionStorage.getItem('ecom_token');
    if (!token) {
      redirectToLogin();
      return null;
    }
    headers['Authorization'] = `Bearer ${token}`;
  }

  const options = { method, headers };
  if (body) options.body = JSON.stringify(body);

  try {
    const res = await fetch(`${API_BASE}${endpoint}`, options);

    if (res.status === 401) {
      clearAuthSession();
      redirectToLogin();
      return null;
    }

    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.detail || data.error || `Error ${res.status}`);
    }

    return data;
  } catch (err) {
    console.error(`[API] ${method} ${endpoint}:`, err.message);
    throw err;
  }
}

// ════════════════════════════════════════════════════
// 5️⃣  API OBJECT (exported methods)
// ════════════════════════════════════════════════════
const api = {
  get:    (url, auth = false)        => apiRequest('GET',    url, null, auth),
  post:   (url, body, auth = false)  => apiRequest('POST',   url, body, auth),
  put:    (url, body, auth = false)  => apiRequest('PUT',    url, body, auth),
  patch:  (url, body, auth = false)  => apiRequest('PATCH',  url, body, auth),
  delete: (url, auth = false)        => apiRequest('DELETE', url, null, auth),
};
