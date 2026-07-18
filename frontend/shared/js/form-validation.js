// === FORM-VALIDATION.JS (SHARED) ===
// Real-time inline validation for auth-style forms. Only a handful of checks exist across the
// login/register/forgot/reset forms, so this is a couple of small validators rather than a
// generic rules engine.

const Validators = {
  email: (v) => (/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v) ? null : 'Enter a valid email address'),
  minLength: (n) => (v) => (v.length >= n ? null : `Must be at least ${n} characters`),
  strongPassword: (v) => {
    if (v.length < 8) return 'At least 8 characters';
    if (!/[A-Z]/.test(v)) return 'Add an uppercase letter';
    if (!/[0-9]/.test(v)) return 'Add a digit';
    return null;
  },
  matches: (getOtherValue, message) => (v) => (v === getOtherValue() ? null : message),
};

// Toggles .field-valid/.field-invalid on the input's .form-group and shows an inline message in
// its .field-hint span (created on first use). Runs on blur, and again on input once a field is
// already marked invalid (so the message clears the moment the user fixes it).
function attachFieldValidation(input, validate) {
  if (!input) return;
  const group = input.closest('.form-group');
  if (!group) return;

  let hint = group.querySelector('.field-hint');
  if (!hint) {
    hint = document.createElement('span');
    hint.className = 'field-hint';
    group.appendChild(hint);
  }

  const run = () => {
    if (!input.value) {
      group.classList.remove('field-valid', 'field-invalid');
      hint.textContent = '';
      return;
    }
    const error = validate(input.value);
    group.classList.toggle('field-invalid', !!error);
    group.classList.toggle('field-valid', !error);
    hint.textContent = error || '';
  };

  input.addEventListener('blur', run);
  input.addEventListener('input', () => {
    if (group.classList.contains('field-invalid')) run();
  });
}
