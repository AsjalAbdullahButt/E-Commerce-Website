// === API.JS (SHARED) ===
// Central fetch wrapper that handles auth, errors, and redirects

function redirectToLogin() {
  const path = window.location.pathname;
  if (path.includes('/admin/')) {
    window.location.href = '../auth/login.html';
  } else if (path.includes('/rider/')) {
    window.location.href = '../auth/login.html';
  } else if (path.includes('/customer/')) {
    window.location.href = '../auth/login.html';
  } else {
    window.location.href = './auth/login.html';
  }
}

// The access token is kept in memory only (never localStorage/disk) so it can't be lifted by an
// XSS payload reading persistent storage. It's lost on every full page load by design; apiRequest
// silently restores it from the httpOnly refresh_token cookie via refreshAccessToken() the first
// time an authenticated call is made after a page loads. ecom_user/ecom_role hold no secrets
// (display name, email, role) so they stay in localStorage for synchronous nav rendering.
let _accessToken = null;

function getAccessToken() {
  return _accessToken;
}

function setAccessToken(token) {
  _accessToken = token;
}

function clearAuthSession() {
  setAccessToken(null);
  localStorage.removeItem('ecom_user');
  localStorage.removeItem('ecom_role');
}

function getCookie(name) {
  const match = document.cookie.match(new RegExp('(?:^|; )' + name + '=([^;]*)'));
  return match ? decodeURIComponent(match[1]) : null;
}

// Dedupes concurrent refresh attempts (e.g. several API calls 401-ing at once) into one request.
let _refreshPromise = null;

async function refreshAccessToken() {
  if (!_refreshPromise) {
    _refreshPromise = (async () => {
      try {
        const csrfToken = getCookie('csrf_token');
        const res = await fetch(`${API_BASE}/auth/refresh`, {
          method: 'POST',
          credentials: 'include',
          cache: 'no-store',
          headers: csrfToken ? { 'X-CSRF-Token': csrfToken } : {},
        });
        if (!res.ok) return false;
        const data = await res.json();
        setAccessToken(data.access_token);
        return true;
      } catch (err) {
        console.error('[API] Token refresh failed:', err.message);
        return false;
      } finally {
        _refreshPromise = null;
      }
    })();
  }
  return _refreshPromise;
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

async function apiRequest(method, endpoint, body = null, requiresAuth = false, _isRetry = false) {
  const headers = { 'Content-Type': 'application/json' };

  if (requiresAuth) {
    let token = getAccessToken();
    if (!token) {
      // Nothing in memory yet (fresh page load) — try a silent restore from the httpOnly
      // refresh_token cookie before giving up.
      await refreshAccessToken();
      token = getAccessToken();
    }
    if (!token) {
      redirectToLogin();
      return null;
    }
    headers['Authorization'] = `Bearer ${token}`;
  }

  const options = { method, headers };
  // Prevent Chrome aggressive caching for API calls
  options.cache = 'no-store';
  // Required for the browser to send/store the httpOnly refresh_token cookie set by
  // /auth/login and /auth/refresh — frontend (:5500) and backend (:8000) are different origins,
  // and fetch's default credentials mode ("same-origin") silently drops cross-origin cookies.
  options.credentials = 'include';
  if (body) options.body = JSON.stringify(body);

  try {
    // Add a cache-busting timestamp only for authenticated GET requests
    let url = `${API_BASE}${endpoint}`;
    if (method === 'GET' && requiresAuth) {
      const sep = url.includes('?') ? '&' : '?';
      url = `${url}${sep}_=${Date.now()}`;
    }
    const res = await fetch(url, options);

    if (res.status === 401) {
      // Access tokens are short-lived (15 min); try one silent refresh (matches the admin
      // panel's retry pattern in admin/js/admin-api.js) before dropping the session.
      if (requiresAuth && !_isRetry) {
        const refreshed = await refreshAccessToken();
        if (refreshed) {
          return apiRequest(method, endpoint, body, requiresAuth, true);
        }
      }
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
