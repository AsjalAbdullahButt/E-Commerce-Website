attachFieldValidation(document.getElementById('register-email'), Validators.email);
attachFieldValidation(document.getElementById('register-password'), Validators.minLength(6));
attachFieldValidation(
  document.getElementById('register-confirm'),
  Validators.matches(() => document.getElementById('register-password').value, 'Passwords do not match')
);
initGoogleSignIn('google-signin-container', 'google-divider');

async function handleRegister() {
  const name = document.getElementById('register-name').value;
  const email = document.getElementById('register-email').value;
  const phone = document.getElementById('register-phone').value;
  const password = document.getElementById('register-password').value;
  const confirm = document.getElementById('register-confirm').value;

  if (!name || !email || !password || !confirm) {
    showToast('Please fill all fields', 'warning');
    if (!name) shakeField(document.getElementById('register-name'));
    if (!email) shakeField(document.getElementById('register-email'));
    if (!password) shakeField(document.getElementById('register-password'));
    if (!confirm) shakeField(document.getElementById('register-confirm'));
    return;
  }

  if (password !== confirm) {
    showToast('Passwords do not match', 'warning');
    shakeField(document.getElementById('register-password'));
    shakeField(document.getElementById('register-confirm'));
    return;
  }

  if (password.length < 6) {
    showToast('Password must be at least 6 characters', 'warning');
    shakeField(document.getElementById('register-password'));
    return;
  }

  try {
    const user = await register(name, email, password, phone);
    showToast('Account created! Redirecting...', 'success');

    // Redirect to customer pages
    setTimeout(() => {
      window.location.href = '../customer/profile.html';
    }, 1500);
  } catch (err) {
    console.error('Registration error:', err);
    const errorMsg = err.message || 'Registration failed. Please try again.';
    showToast(errorMsg, 'error');
  }
}

document.getElementById('register-submit-btn').addEventListener('click', handleRegister);

// Make form submission work with Enter key
document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('register-form');
  form.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleRegister();
    }
  });

  // Prefills from the post-guest-checkout "Create Account" link (js/tracking.js) so a guest
  // doesn't have to retype the email their order confirmation was already sent to.
  const prefillEmail = new URLSearchParams(window.location.search).get('email');
  if (prefillEmail) {
    const emailInput = document.getElementById('register-email');
    if (emailInput) emailInput.value = prefillEmail;
  }
});
