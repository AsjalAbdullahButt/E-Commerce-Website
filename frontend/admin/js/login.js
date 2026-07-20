document.getElementById('loginForm').addEventListener('submit', async (e) => {
    e.preventDefault();

    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    const errorDiv = document.getElementById('errorMessage');
    const loginBtn = document.getElementById('loginBtn');
    const spinner = document.getElementById('spinner');
    const btnText = document.getElementById('btnText');

    // Clear previous errors
    errorDiv.style.display = 'none';

    // Show loading
    loginBtn.disabled = true;
    loginBtn.classList.add('loading');
    loginBtn.setAttribute('aria-busy', 'true');
    spinner.style.display = 'inline-block';
    btnText.textContent = 'Signing in...';

    try {
        const response = await adminAPI.login(email, password);

        if (response.success) {
            // Store only the (non-sensitive) profile. The access token itself is kept in
            // memory only (see js/admin-api.js) — dashboard.html's fresh AdminAPI
            // instance restores it from the httpOnly admin_refresh_token cookie the
            // server just set (never readable from JS) on its first request.
            localStorage.setItem(STORAGE_KEYS.ADMIN_DATA, JSON.stringify(response.data.admin));

            // Redirect to dashboard
            window.location.href = 'dashboard.html';
        } else {
            throw new Error(response.message || 'Login failed');
        }
    } catch (error) {
        errorDiv.textContent = '❌ ' + (error.message || 'Login failed. Please check your credentials.');
        errorDiv.style.display = 'block';

        loginBtn.disabled = false;
        loginBtn.classList.remove('loading');
        loginBtn.removeAttribute('aria-busy');
        spinner.style.display = 'none';
        btnText.textContent = 'Sign In';
    }
});
