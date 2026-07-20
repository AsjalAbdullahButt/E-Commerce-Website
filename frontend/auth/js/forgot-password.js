attachFieldValidation(document.getElementById('forgot-email'), Validators.email);

async function handleForgotPassword() {
  const email = document.getElementById('forgot-email').value;
  if (!email) {
    showToast('Please enter your email', 'warning');
    shakeField(document.getElementById('forgot-email'));
    return;
  }

  const btn = document.getElementById('forgot-submit-btn');
  btn.disabled = true;
  btn.textContent = 'Sending...';

  try {
    const result = await api.post('/auth/forgot-password', { email });
    showToast(result.message || 'If an account exists, a reset link has been sent.', 'success');
  } catch (err) {
    showToast(err.message || 'Failed to send reset link', 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Send Reset Link';
  }
}

document.getElementById('forgot-submit-btn').addEventListener('click', handleForgotPassword);

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('forgot-form').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleForgotPassword();
    }
  });
});
