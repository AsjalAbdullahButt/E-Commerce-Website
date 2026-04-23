// === API.JS (SHARED) ===
// Central fetch wrapper that handles auth, errors, and redirects

function redirectToLogin() {
  window.location.href = window.location.pathname.includes('/admin/') 
    ? '../../auth/login.html' 
    : window.location.pathname.includes('/rider/')
    ? '../../auth/login.html'
    : '../auth/login.html';
}

function clearAuthSession() {
  localStorage.removeItem('ecom_token');
  localStorage.removeItem('ecom_user');
  localStorage.removeItem('ecom_role');
}

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

async function apiRequest(method, endpoint, body = null, requiresAuth = false) {
  const headers = { 'Content-Type': 'application/json' };

  if (requiresAuth) {
    const token = localStorage.getItem('ecom_token');
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

    if (res.status === 403) {
      showToast('Access Denied', 'error');
      return null;
    }

    let data;
    try {
      data = await res.json();
    } catch (e) {
      if (!res.ok) {
        throw new Error(`Request failed with status ${res.status}`);
      }
      return null;
    }

    if (!res.ok) {
      throw new Error(data.detail || data.error || `Error ${res.status}`);
    }

    return data;
  } catch (err) {
    console.error(`[API] ${method} ${endpoint}:`, err.message);
    throw err;
  }
}

const api = {
  get:    (url, auth = false)        => apiRequest('GET',    url, null, auth),
  post:   (url, body, auth = false)  => apiRequest('POST',   url, body, auth),
  put:    (url, body, auth = false)  => apiRequest('PUT',    url, body, auth),
  patch:  (url, body, auth = false)  => apiRequest('PATCH',  url, body, auth),
  delete: (url, auth = false)        => apiRequest('DELETE', url, null, auth),
};
