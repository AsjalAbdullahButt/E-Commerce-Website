// === CONTACT.JS ===
// Form submission handlers with accessibility and validation

document.addEventListener('DOMContentLoaded', () => {
  initTabAccessibility();
  setMaxDateForComplaint();
  initContactForm();
  initComplaintForm();
  initFileUpload();
});

// ════════════════════════════════════════════════════
// SET MAX DATE FOR COMPLAINT (TODAY)
// ════════════════════════════════════════════════════
function setMaxDateForComplaint() {
  const dateInput = document.querySelector('input[name="complaint-date"]');
  if (dateInput) {
    const today = new Date().toISOString().split('T')[0];
    dateInput.setAttribute('max', today);
  }
}

// ════════════════════════════════════════════════════
// TAB ACCESSIBILITY & SWITCHING
// ════════════════════════════════════════════════════
function initTabAccessibility() {
  const tabBtns = document.querySelectorAll('.tab-btn');
  const tabContents = document.querySelectorAll('.tab-content');

  // Set ARIA attributes for accessibility
  const tabList = document.querySelector('.contact-tabs');
  if (tabList) {
    tabList.setAttribute('role', 'tablist');
  }

  tabBtns.forEach((btn, index) => {
    const tabName = btn.getAttribute('data-tab');
    btn.setAttribute('role', 'tab');
    btn.setAttribute('aria-selected', btn.classList.contains('active'));
    btn.setAttribute('aria-controls', tabName + '-tab');
    btn.setAttribute('tabindex', btn.classList.contains('active') ? '0' : '-1');

    btn.addEventListener('click', () => switchTab(tabName));

    // Keyboard navigation (Arrow keys)
    btn.addEventListener('keydown', (e) => {
      let newIndex = index;
      if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
        e.preventDefault();
        newIndex = (index + 1) % tabBtns.length;
      } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
        e.preventDefault();
        newIndex = (index - 1 + tabBtns.length) % tabBtns.length;
      } else if (e.key === 'Home') {
        e.preventDefault();
        newIndex = 0;
      } else if (e.key === 'End') {
        e.preventDefault();
        newIndex = tabBtns.length - 1;
      }
      tabBtns[newIndex].focus();
      switchTab(tabBtns[newIndex].getAttribute('data-tab'));
    });
  });

  // Set ARIA attributes for tab contents
  tabContents.forEach(content => {
    const tabId = content.id;
    content.setAttribute('role', 'tabpanel');
    content.setAttribute('aria-labelledby', content.id.replace('-tab', ''));
    if (!content.classList.contains('active')) {
      content.style.display = 'none';
    }
  });
}

function switchTab(tabName) {
  const tabBtns = document.querySelectorAll('.tab-btn');
  const tabContents = document.querySelectorAll('.tab-content');

  // Remove active class and hide contents
  tabBtns.forEach(btn => {
    const isActive = btn.getAttribute('data-tab') === tabName;
    btn.classList.toggle('active', isActive);
    btn.setAttribute('aria-selected', isActive);
    btn.setAttribute('tabindex', isActive ? '0' : '-1');
  });

  tabContents.forEach(content => {
    const isActive = content.id === tabName + '-tab';
    content.classList.toggle('active', isActive);
    content.style.display = isActive ? '' : 'none';
  });
}

// ════════════════════════════════════════════════════
// CONTACT FORM SUBMISSION
// ════════════════════════════════════════════════════
function initContactForm() {
  const contactForm = document.querySelector('.contact-form');
  if (!contactForm) return;

  contactForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    // Get form data with null checks
    const nameInput = contactForm.querySelector('input[name="name"]');
    const emailInput = contactForm.querySelector('input[name="email"]');
    const subjectInput = contactForm.querySelector('input[name="subject"]');
    const messageInput = contactForm.querySelector('textarea[name="message"]');

    if (!nameInput || !emailInput || !subjectInput || !messageInput) {
      showToast('Form fields missing', 'error');
      return;
    }

    const contactData = {
      name: nameInput.value.trim(),
      email: emailInput.value.trim(),
      subject: subjectInput.value.trim(),
      message: messageInput.value.trim()
    };

    // Validation
    if (!contactData.name || !contactData.email || !contactData.subject || !contactData.message) {
      showToast('Please fill in all required fields', 'error');
      return;
    }

    // Email validation
    if (!isValidEmail(contactData.email)) {
      showToast('Please enter a valid email address', 'error');
      return;
    }

    try {
      // Submit to backend
      const response = await api.post('/contact', contactData, false);

      if (response) {
        showToast('Thank you for reaching out! We will respond shortly.', 'success');
        contactForm.reset();
      }
    } catch (err) {
      console.error('Contact form error:', err);
      // Sanitize error message - don't expose raw backend errors
      const errorMessage = err.message?.includes('detail') 
        ? 'Unable to submit your message. Please try again later.'
        : 'Error submitting form. Please try again.';
      showToast(errorMessage, 'error');
    }
  });
}

// ════════════════════════════════════════════════════
// COMPLAINT FORM SUBMISSION
// ════════════════════════════════════════════════════
function initComplaintForm() {
  const complaintForm = document.querySelector('.complaint-form');
  if (!complaintForm) return;

  complaintForm.addEventListener('submit', async (e) => {
    e.preventDefault();

    // Get all form inputs with null checks
    const nameInput = complaintForm.querySelector('input[name="complaint-name"]');
    const emailInput = complaintForm.querySelector('input[name="complaint-email"]');
    const phoneInput = complaintForm.querySelector('input[name="complaint-phone"]');
    const orderInput = complaintForm.querySelector('input[name="complaint-order"]');
    const categoryInput = complaintForm.querySelector('select[name="complaint-category"]');
    const dateInput = complaintForm.querySelector('input[name="complaint-date"]');
    const descriptionInput = complaintForm.querySelector('textarea[name="complaint-description"]');
    const fileInput = complaintForm.querySelector('input[name="complaint-file"]');
    const agreeCheckbox = complaintForm.querySelector('#complaint-agree');

    if (!nameInput || !emailInput || !phoneInput || !categoryInput || !dateInput || 
        !descriptionInput || !fileInput || !agreeCheckbox) {
      showToast('Form fields missing', 'error');
      return;
    }

    // Validation
    if (!nameInput.value.trim() || !emailInput.value.trim() || !phoneInput.value.trim() || 
        !categoryInput.value || !dateInput.value || !descriptionInput.value.trim()) {
      showToast('Please fill in all required fields', 'error');
      return;
    }

    if (!isValidEmail(emailInput.value.trim())) {
      showToast('Please enter a valid email address', 'error');
      return;
    }

    if (!fileInput.files || fileInput.files.length === 0) {
      showToast('Please upload evidence file', 'error');
      return;
    }

    if (!agreeCheckbox.checked) {
      showToast('Please agree to the terms', 'error');
      return;
    }

    // Validate date is not in future
    const complaintDate = new Date(dateInput.value);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    if (complaintDate > today) {
      showToast('Date of issue cannot be in the future', 'error');
      return;
    }

    try {
      // Create FormData for file upload
      const formData = new FormData();
      formData.append('name', nameInput.value.trim());
      formData.append('email', emailInput.value.trim());
      formData.append('phone', phoneInput.value.trim());
      formData.append('order_number', orderInput.value.trim());
      formData.append('category', categoryInput.value);
      formData.append('date_of_issue', dateInput.value);
      formData.append('description', descriptionInput.value.trim());
      formData.append('file', fileInput.files[0]);

      // Submit to backend using fetch (for FormData support)
      const token = sessionStorage.getItem('ecom_token');
      const headers = {};
      if (token) {
        headers['Authorization'] = `Bearer ${token}`;
      }

      const response = await fetch(`${API_BASE}/complaints`, {
        method: 'POST',
        headers: headers,
        body: formData
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || data.error || `Error ${response.status}`);
      }

      showToast('Complaint submitted successfully! Our team will review it and contact you within 24-48 hours.', 'success');
      complaintForm.reset();

      // Switch back to contact tab after 2 seconds
      setTimeout(() => {
        const contactBtn = document.querySelector('[data-tab="contact"]');
        if (contactBtn) {
          contactBtn.click();
        }
      }, 2000);
    } catch (err) {
      console.error('Complaint form error:', err);
      // Sanitize error message
      const errorMessage = 'Unable to submit your complaint. Please try again later.';
      showToast(errorMessage, 'error');
    }
  });
}

// ════════════════════════════════════════════════════
// FILE UPLOAD ACCESSIBILITY
// ════════════════════════════════════════════════════
function initFileUpload() {
  const fileUploadArea = document.querySelector('.file-upload-area');
  const fileInput = document.querySelector('input[name="complaint-file"]');

  if (!fileUploadArea || !fileInput) return;

  // Make file upload area keyboard accessible
  fileUploadArea.setAttribute('role', 'button');
  fileUploadArea.setAttribute('tabindex', '0');
  fileUploadArea.setAttribute('aria-label', 'Upload evidence file');

  // Click handler
  fileUploadArea.addEventListener('click', () => fileInput.click());

  // Keyboard handler for Enter and Space
  fileUploadArea.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      fileInput.click();
    }
  });

  // Focus styles
  fileUploadArea.addEventListener('focus', () => {
    fileUploadArea.style.outline = '2px solid var(--gold)';
    fileUploadArea.style.outlineOffset = '2px';
  });

  fileUploadArea.addEventListener('blur', () => {
    fileUploadArea.style.outline = 'none';
  });

  // Drag and drop
  fileUploadArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    fileUploadArea.style.background = 'rgba(255, 215, 0, 0.15)';
  });

  fileUploadArea.addEventListener('dragleave', () => {
    fileUploadArea.style.background = 'rgba(255, 215, 0, 0.05)';
  });

  fileUploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    fileUploadArea.style.background = 'rgba(255, 215, 0, 0.05)';
    if (e.dataTransfer.files.length) {
      fileInput.files = e.dataTransfer.files;
    }
  });
}

// ════════════════════════════════════════════════════
// UTILITY FUNCTIONS
// ════════════════════════════════════════════════════
function isValidEmail(email) {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
}
