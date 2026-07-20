attachFieldValidation(document.getElementById('login-email'), Validators.email);
initGoogleSignIn('google-signin-container', 'google-divider');

async function handleLogin() {
  const email = document.getElementById('login-email').value;
  const password = document.getElementById('login-password').value;

  if (!email || !password) {
    showToast('Please fill all fields', 'warning');
    if (!email) shakeField(document.getElementById('login-email'));
    if (!password) shakeField(document.getElementById('login-password'));
    return;
  }

  try {
    const user = await login(email, password);
    showToast('Login successful! Redirecting...', 'success');

    // Redirect based on user role (returned from backend)
    setTimeout(() => {
      redirectAfterLogin(user.role);
    }, 1000);
  } catch (err) {
    console.error('Login error:', err);
    const errorMsg = err.message || 'Login failed. Please check your credentials and try again.';
    showToast(errorMsg, 'error');
    shakeField(document.getElementById('login-password'));
  }
}

document.getElementById('login-submit-btn').addEventListener('click', handleLogin);

// Make form submission work with Enter key
document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('login-form');
  form.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleLogin();
    }
  });
});
