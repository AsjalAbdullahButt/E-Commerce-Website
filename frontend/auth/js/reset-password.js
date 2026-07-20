attachFieldValidation(document.getElementById('reset-password'), Validators.strongPassword);
attachFieldValidation(
  document.getElementById('reset-confirm'),
  Validators.matches(() => document.getElementById('reset-password').value, 'Passwords do not match')
);

function getResetToken() {
  return new URLSearchParams(window.location.search).get('token');
}

async function handleResetPassword() {
  const token = getResetToken();
  if (!token) {
    showToast('Missing or invalid reset link', 'error');
    return;
  }

  const password = document.getElementById('reset-password').value;
  const confirm = document.getElementById('reset-confirm').value;

  if (!password || !confirm) {
    showToast('Please fill both fields', 'warning');
    if (!password) shakeField(document.getElementById('reset-password'));
    if (!confirm) shakeField(document.getElementById('reset-confirm'));
    return;
  }
  if (password !== confirm) {
    showToast('Passwords do not match', 'warning');
    shakeField(document.getElementById('reset-password'));
    shakeField(document.getElementById('reset-confirm'));
    return;
  }

  const btn = document.getElementById('reset-submit-btn');
  btn.disabled = true;
  btn.textContent = 'Resetting...';

  try {
    const result = await api.post('/auth/reset-password', { token, new_password: password });
    showToast(result.message || 'Password reset successfully', 'success');
    setTimeout(() => { window.location.href = './login.html'; }, 1500);
  } catch (err) {
    showToast(err.message || 'Failed to reset password. The link may have expired.', 'error');
    shakeField(document.getElementById('reset-password'));
  } finally {
    btn.disabled = false;
    btn.textContent = 'Reset Password';
  }
}

document.getElementById('reset-submit-btn').addEventListener('click', handleResetPassword);

document.addEventListener('DOMContentLoaded', () => {
  if (!getResetToken()) {
    document.getElementById('reset-subtitle').textContent = 'This reset link is missing a token. Request a new one from the forgot password page.';
    document.getElementById('reset-submit-btn').disabled = true;
  }
  document.getElementById('reset-form').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      handleResetPassword();
    }
  });
});
