// === HOME.JS ===
let activeCategory = '';

// swatchColor + renderProductCardSkeletons come from shared/js/ui-states.js, loaded before this file.

const defaultCategories = ['All', 'T-Shirts', 'Hoodies', 'Pants', 'Accessories'];

function renderCategoryItems(container, categories) {
  if (!container) return;

  container.textContent = '';
  categories.forEach((cat, idx) => {
    const div = document.createElement('div');
    div.className = `category-item ${idx === 0 ? 'active' : ''}`;
    div.dataset.category = encodeURIComponent(cat);

    const icon = document.createElement('i');
    icon.className = 'fas fa-tag';

    const span = document.createElement('span');
    span.textContent = cat;

    div.appendChild(icon);
    div.appendChild(span);
    container.appendChild(div);
  });
}

async function loadFeaturedProducts(category = '') {
  try {
    const params = new URLSearchParams({ limit: 4, sort: 'newest' });
    if (category && category !== 'All') {
      params.set('category', category);
    }

    const container = document.querySelector('.product-grid');
    if (!container) return;

    renderProductCardSkeletons(container, 4);

    const data = await api.get(`/products?${params}`);

    container.textContent = '';
    if (!data.products || data.products.length === 0) {
      renderEmptyStateInto(container, {
        icon: 'fa-box-open',
        title: 'No products found',
        message: category ? `No products found for ${category}.` : 'No featured products available.',
      });
      return;
    }

    const frag = document.createDocumentFragment();
    data.products.forEach((p) => {
      const card = buildProductCard(p);
      card.style.opacity = '0';
      card.style.transform = 'translateY(16px)';
      frag.appendChild(card);
    });
    container.appendChild(frag);

    requestAnimationFrame(() => {
      Array.from(container.children).forEach((card, idx) => {
        card.style.transition = `opacity var(--duration-slow) var(--ease) ${idx * 60}ms, transform var(--duration-slow) var(--ease) ${idx * 60}ms`;
        card.style.opacity = '1';
        card.style.transform = 'none';
      });
    });
  } catch (err) {
    console.error('Failed to load featured products', err);
  }
}

// Load categories from API
async function loadCategories() {
  const container = document.querySelector('#categories-container');
  if (!container) return;

  renderCategoryItems(container, defaultCategories);

  try {
    const data = await api.get('/products/categories');

    const categories = data.categories || [];
    if (categories.length > 0) {
      renderCategoryItems(container, categories);
    } else {
      throw new Error('No categories found');
    }
  } catch (err) {
    console.error('Failed to load categories', err);
    // Keep the default categories already rendered above.
  }
}

function setupCategoryFiltering() {
  const container = document.getElementById('categories-container');
  if (!container) return;

  container.addEventListener('click', (event) => {
    const item = event.target.closest('.category-item');
    if (!item || !container.contains(item)) return;

    const category = item.dataset.category ? decodeURIComponent(item.dataset.category) : '';
    activeCategory = category;

    document.querySelectorAll('.category-item').forEach(i => i.classList.remove('active'));
    item.classList.add('active');

    loadFeaturedProducts(activeCategory);

    const featuredSection = document.querySelector('.featured-section');
    if (featuredSection) {
      featuredSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  });
}

// Load and display user profile
function loadUserProfile() {
  const user = getUser();
  const userNameEl = document.querySelector('.user-name');
  const userEmailEl = document.querySelector('.user-email');
  
  if (user) {
    userNameEl.textContent = user.name || 'User';
    userEmailEl.textContent = user.email || 'Not logged in';
  } else {
    userNameEl.textContent = 'Guest User';
    userEmailEl.textContent = 'Login to view profile';
  }
}

// Sidebar toggle functionality
function setupSidebarToggle() {
  const sidebar = document.getElementById('sidebar');
  const overlay = document.getElementById('sidebar-overlay');
  const toggle = document.getElementById('sidebar-toggle');
  const close = document.getElementById('sidebar-close');
  
  if (!sidebar) return;

  function setSidebarOpen(isOpen) {
    sidebar.classList.toggle('show', isOpen);
    if (overlay) overlay.classList.toggle('show', isOpen);
    if (toggle) toggle.setAttribute('aria-expanded', String(isOpen));
  }

  // Toggle sidebar on button click
  if (toggle) {
    toggle.setAttribute('aria-expanded', 'false');
    toggle.addEventListener('click', () => {
      setSidebarOpen(!sidebar.classList.contains('show'));
    });
  }

  // Close sidebar on close button click
  if (close) {
    close.addEventListener('click', (e) => {
      e.stopPropagation();
      setSidebarOpen(false);
    });
  }

  // Close sidebar when clicking on a category
  document.querySelectorAll('.category-item').forEach(item => {
    item.addEventListener('click', () => {
      // Only close on mobile (when transform is active)
      if (window.innerWidth <= 768) {
        setSidebarOpen(false);
      }
    });
  });

  // Close sidebar when clicking on overlay
  if (overlay) {
    overlay.addEventListener('click', () => setSidebarOpen(false));
  }

  // Close sidebar on Escape (mobile drawer mode)
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && sidebar.classList.contains('show')) {
      setSidebarOpen(false);
    }
  });

  // Handle resize to ensure sidebar is visible on desktop
  window.addEventListener('resize', () => {
    if (window.innerWidth > 768) {
      sidebar.classList.remove('show');
      if (overlay) overlay.classList.remove('show');
    }
  });
}

// Setup user profile button
function setupUserProfileButton() {
  const userProfileBtn = document.getElementById('user-profile-btn');
  const user = getUser();

  if (userProfileBtn) {
    userProfileBtn.addEventListener('click', () => {
      if (user) {
        window.location.href = './profile.html';
      } else {
        window.location.href = './login.html';
      }
    });
  }
}

document.addEventListener('DOMContentLoaded', () => {
  loadFeaturedProducts();
  loadCategories();
  setupCategoryFiltering();
  loadUserProfile();
  setupSidebarToggle();
  setupUserProfileButton();
  setupOrderTracking();
});

// Setup order tracking feature
function setupOrderTracking() {
  const user = getUser();
  const guestMessage = document.getElementById('tracking-guest-message');
  const loggedInWidget = document.getElementById('tracking-logged-in');

  if (user) {
    // User is logged in - show tracking widget
    if (guestMessage) guestMessage.style.display = 'none';
    if (loggedInWidget) loggedInWidget.style.display = 'block';
  } else {
    // User not logged in - show login prompt
    if (guestMessage) guestMessage.style.display = 'flex';
    if (loggedInWidget) loggedInWidget.style.display = 'none';
  }

  // Setup search functionality
  const trackingInput = document.getElementById('tracking-order-input');
  if (trackingInput) {
    trackingInput.addEventListener('keypress', (e) => {
      if (e.key === 'Enter') {
        searchOrder();
      }
    });
  }
  const trackOrderBtn = document.getElementById('track-order-btn');
  if (trackOrderBtn) trackOrderBtn.addEventListener('click', searchOrder);
}

// Search for order
async function searchOrder() {
  // Null check for input element
  const trackingInput = document.getElementById('tracking-order-input');
  if (!trackingInput) {
    console.error('Tracking input element not found');
    showToast('Error: Form element not found', 'error');
    return;
  }

  const orderNumber = trackingInput.value.trim();
  
  if (!orderNumber) {
    showToast('Please enter an order number', 'warning');
    return;
  }

  // Null check for result div
  const resultDiv = document.getElementById('tracking-result');
  if (!resultDiv) {
    console.error('Tracking result element not found');
    showToast('Error: Result element not found', 'error');
    return;
  }

  // Clear and show loading state
  resultDiv.textContent = '';
  resultDiv.classList.add('active');
  const spinner = document.createElement('div');
  spinner.className = 'loading-spinner';
  spinner.textContent = ' Loading...';
      const spinIcon = document.createElement('i'); spinIcon.className = 'fas fa-spinner'; spinner.insertBefore(spinIcon, spinner.firstChild);
  resultDiv.appendChild(spinner);

  try {
    // For demo purposes, create mock order data
    // In real app, this would call API endpoint like /orders/{order_id}
    const mockOrders = {
      'ORD-001': {
        id: 'ORD-001',
        date: '2025-04-15',
        total: 4990,
        status: 'delivered',
        items: ['E-COM Premium T-Shirt', 'Classic Hoodie'],
        timeline: [
          { stage: 'Order Placed', date: '2025-04-15', completed: true },
          { stage: 'Confirmed', date: '2025-04-15', completed: true },
          { stage: 'Packed', date: '2025-04-16', completed: true },
          { stage: 'Shipped', date: '2025-04-17', completed: true },
          { stage: 'Delivered', date: '2025-04-19', completed: true }
        ]
      },
      'ORD-002': {
        id: 'ORD-002',
        date: '2025-04-20',
        total: 2990,
        status: 'in-transit',
        items: ['Oversized Fit Pants'],
        timeline: [
          { stage: 'Order Placed', date: '2025-04-20', completed: true },
          { stage: 'Confirmed', date: '2025-04-20', completed: true },
          { stage: 'Packed', date: '2025-04-21', completed: true },
          { stage: 'Shipped', date: '2025-04-21', completed: true },
          { stage: 'Delivered', date: 'Pending', completed: false }
        ]
      }
    };

    const order = mockOrders[orderNumber.toUpperCase()];

    if (!order) {
      resultDiv.textContent = '';
      const notFoundDiv = document.createElement('div');
      notFoundDiv.style.color = 'var(--text-secondary)';
      notFoundDiv.style.padding = '2rem';
      notFoundDiv.style.textAlign = 'center';
      notFoundDiv.textContent = '';
      const nfIcon = document.createElement('i'); nfIcon.className = 'fas fa-search'; nfIcon.style.fontSize = '2rem'; nfIcon.style.opacity = '0.5'; nfIcon.style.marginBottom = '1rem'; nfIcon.style.display = 'block'; notFoundDiv.appendChild(nfIcon);
      const p = document.createElement('p');
      p.textContent = 'Order not found. Please check the order number and try again.';
      notFoundDiv.appendChild(p);
      resultDiv.appendChild(notFoundDiv);
      return;
    }

    // Display order details with proper sanitization
    const statusColors = {
      'delivered': '#4CAF50',
      'in-transit': '#FFC107',
      'pending': '#FF9800',
      'cancelled': '#F44336'
    };

    const statusText = {
      'delivered': 'Delivered',
      'in-transit': 'In Transit',
      'pending': 'Pending',
      'cancelled': 'Cancelled'
    };

    resultDiv.textContent = '';
    resultDiv.classList.add('active');

    const orderStatus = document.createElement('div');
    orderStatus.className = 'order-status';

    const orderHeader = document.createElement('div');
    orderHeader.className = 'order-header';

    // Order number
    const orderNumberDiv = document.createElement('div');
    orderNumberDiv.className = 'order-detail';
    const label1 = document.createElement('label');
    label1.textContent = 'Order Number';
    const p1 = document.createElement('p');
    safeText(p1, order.id);
    orderNumberDiv.appendChild(label1);
    orderNumberDiv.appendChild(p1);

    // Status
    const statusDiv = document.createElement('div');
    statusDiv.className = 'order-detail';
    const label2 = document.createElement('label');
    label2.textContent = 'Status';
    const p2 = document.createElement('p');
    p2.style.color = statusColors[order.status] || '#999';
    p2.textContent = statusText[order.status] || 'Unknown';
    statusDiv.appendChild(label2);
    statusDiv.appendChild(p2);

    // Order date
    const dateDiv = document.createElement('div');
    dateDiv.className = 'order-detail';
    const label3 = document.createElement('label');
    label3.textContent = 'Order Date';
    const p3 = document.createElement('p');
    try {
      p3.textContent = new Date(order.date).toLocaleDateString();
    } catch {
      p3.textContent = 'Invalid date';
    }
    dateDiv.appendChild(label3);
    dateDiv.appendChild(p3);

    // Total amount
    const totalDiv = document.createElement('div');
    totalDiv.className = 'order-detail';
    const label4 = document.createElement('label');
    label4.textContent = 'Total Amount';
    const p4 = document.createElement('p');
    const total = sanitizeNumber(order.total);
    p4.textContent = `Rs ${total.toLocaleString()}`;
    totalDiv.appendChild(label4);
    totalDiv.appendChild(p4);

    orderHeader.appendChild(orderNumberDiv);
    orderHeader.appendChild(statusDiv);
    orderHeader.appendChild(dateDiv);
    orderHeader.appendChild(totalDiv);
    orderStatus.appendChild(orderHeader);

    // Items section
    const itemsSection = document.createElement('div');
    itemsSection.style.marginBottom = '1.5rem';
    itemsSection.style.textAlign = 'left';

    const itemsTitle = document.createElement('strong');
    itemsTitle.style.color = 'var(--text-primary)';
    itemsTitle.textContent = 'Items:';
    itemsSection.appendChild(itemsTitle);

    const itemsList = document.createElement('ul');
    itemsList.style.margin = '0.5rem 0 0';
    itemsList.style.paddingLeft = '1.5rem';
    itemsList.style.color = 'var(--text-secondary)';

    if (Array.isArray(order.items)) {
      order.items.forEach(item => {
        const li = document.createElement('li');
        safeText(li, item);
        itemsList.appendChild(li);
      });
    }
    itemsSection.appendChild(itemsList);
    orderStatus.appendChild(itemsSection);

    // Timeline section
    const timelineSection = document.createElement('div');
    timelineSection.className = 'order-timeline';

    const timelineTitle = document.createElement('strong');
    timelineTitle.style.display = 'block';
    timelineTitle.style.marginBottom = '1rem';
    timelineTitle.style.color = 'var(--text-primary)';
    timelineTitle.textContent = 'Delivery Timeline';
    timelineSection.appendChild(timelineTitle);

    if (Array.isArray(order.timeline)) {
      order.timeline.forEach((item, idx) => {
        if (!item) return;

        const timelineItem = document.createElement('div');
        timelineItem.className = 'timeline-item';

        const dot = document.createElement('div');
        dot.className = 'timeline-dot';
        dot.style.background = item.completed ? 'var(--gold)' : 'var(--border)';
        dot.textContent = item.completed ? '✓' : idx + 1;

        const content = document.createElement('div');
        content.className = 'timeline-content';

        const stageStrong = document.createElement('strong');
        safeText(stageStrong, item.stage);

        const dateSpan = document.createElement('span');
        safeText(dateSpan, item.date);

        content.appendChild(stageStrong);
        content.appendChild(dateSpan);

        timelineItem.appendChild(dot);
        timelineItem.appendChild(content);
        timelineSection.appendChild(timelineItem);
      });
    }

    orderStatus.appendChild(timelineSection);
    resultDiv.appendChild(orderStatus);

  } catch (err) {
    console.error('Order tracking error:', err);
    // Don't expose raw backend errors to users
    showToast('Error fetching order details. Please try again later.', 'error');
    resultDiv.textContent = '';
    resultDiv.classList.remove('active');
  }
}

// ════════════════════════════════════════════════════
// SANITIZATION FUNCTIONS
// ════════════════════════════════════════════════════
function sanitizeNumber(num) {
  const parsed = parseFloat(num);
  return isNaN(parsed) ? 0 : parsed;
}

