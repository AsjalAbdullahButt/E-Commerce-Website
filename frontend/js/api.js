// === API.JS ===
// All fetch calls go through here

async function apiRequest(method, endpoint, body = null, requiresAuth = false) {
  const headers = { 'Content-Type': 'application/json' };

  if (requiresAuth) {
    const token = localStorage.getItem('tribe_token');
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
      clearAuth();
      redirectToLogin();
      return null;
    }

    const data = await res.json();

    if (!res.ok) {
      throw new Error(data.detail || `Error ${res.status}`);
    }

    return data;
  } catch (err) {
    console.error(`[API] ${method} ${endpoint}:`, err.message);
    throw err;
  }
}

function redirectToLogin() {
  const depth = window.location.pathname.split('/').filter(Boolean).length;
  const prefix = depth > 2 ? '../' : './';
  window.location.href = prefix + 'login.html';
}

const api = {
  get:    (url, auth = false)        => apiRequest('GET',    url, null, auth),
  post:   (url, body, auth = false)  => apiRequest('POST',   url, body, auth),
  put:    (url, body, auth = false)  => apiRequest('PUT',    url, body, auth),
  patch:  (url, body, auth = false)  => apiRequest('PATCH',  url, body, auth),
  delete: (url, auth = false)        => apiRequest('DELETE', url, null, auth),
};
