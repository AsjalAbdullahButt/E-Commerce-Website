// === HOME.JS ===
async function loadFeaturedProducts() {
  try {
    const data = await api.get('/products?limit=4&sort=newest');
    const container = document.querySelector('.product-grid');
    if (!container) return;

    container.innerHTML = data.products.map(p => `
      <a href="./product.html?id=${p.id}" class="product-card">
        <div class="product-image">
          <img src="${p.images?.[0] || './images/fallback.jpg'}" alt="${p.name}" onerror="this.src='./images/fallback.jpg'">
        </div>
        <div class="product-info">
          <p class="product-name">${p.name}</p>
          <p class="product-price">Rs ${p.price.toLocaleString()}</p>
        </div>
      </a>
    `).join('');
  } catch (err) {
    console.error('Failed to load featured products', err);
  }
}

// Load categories from API
async function loadCategories() {
  try {
    const data = await api.get('/products/categories');
    const container = document.querySelector('#categories-container');
    if (!container) return;

    const categories = data.categories || [];
    if (categories.length === 0) {
      throw new Error('No categories found');
    }
    
    container.innerHTML = categories.map((cat, idx) => `
      <div class="category-item ${idx === 0 ? 'active' : ''}" data-category="${cat}">
        <i class="fas fa-tag"></i>
        <span>${cat}</span>
      </div>
    `).join('');

    // Add click handlers to categories
    document.querySelectorAll('.category-item').forEach(item => {
      item.addEventListener('click', () => {
        document.querySelectorAll('.category-item').forEach(i => i.classList.remove('active'));
        item.classList.add('active');
        const category = item.dataset.category;
        // You can add filtering logic here
        console.log('Selected category:', category);
      });
    });
  } catch (err) {
    console.error('Failed to load categories', err);
    // Fallback categories if API fails
    const container = document.querySelector('#categories-container');
    if (container) {
      const fallbackCategories = ['All', 'T-Shirts', 'Hoodies', 'Pants', 'Accessories'];
      container.innerHTML = fallbackCategories.map((cat, idx) => `
        <div class="category-item ${idx === 0 ? 'active' : ''}" data-category="${cat}">
          <i class="fas fa-tag"></i>
          <span>${cat}</span>
        </div>
      `).join('');
    }
  }
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
  
  if (!sidebar || !toggle) return;

  // Toggle sidebar on button click
  toggle.addEventListener('click', () => {
    const isOpen = sidebar.classList.toggle('show');
    if (overlay) {
      overlay.classList.toggle('show', isOpen);
    }
  });

  // Close sidebar on close button click
  if (close) {
    close.addEventListener('click', () => {
      sidebar.classList.remove('show');
      if (overlay) overlay.classList.remove('show');
    });
  }
  
  // Close sidebar when clicking on a category
  document.querySelectorAll('.category-item').forEach(item => {
    item.addEventListener('click', () => {
      sidebar.classList.remove('show');
      if (overlay) overlay.classList.remove('show');
    });
  });
  
  // Close sidebar when clicking on overlay
  if (overlay) {
    overlay.addEventListener('click', () => {
      sidebar.classList.remove('show');
      overlay.classList.remove('show');
    });
  }
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
  resultDiv.innerHTML = '';
  resultDiv.classList.add('active');
  const spinner = document.createElement('div');
  spinner.className = 'loading-spinner';
  spinner.innerHTML = '<i class="fas fa-spinner"></i> Loading...';
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
      resultDiv.innerHTML = '';
      const notFoundDiv = document.createElement('div');
      notFoundDiv.style.color = 'var(--text-secondary)';
      notFoundDiv.style.padding = '2rem';
      notFoundDiv.style.textAlign = 'center';
      notFoundDiv.innerHTML = '<i class="fas fa-search" style="font-size: 2rem; opacity: 0.5; margin-bottom: 1rem; display: block;"></i>';
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

    resultDiv.innerHTML = '';
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
    p1.textContent = sanitizeString(order.id);
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
        li.textContent = sanitizeString(item);
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
        stageStrong.textContent = sanitizeString(item.stage);

        const dateSpan = document.createElement('span');
        dateSpan.textContent = sanitizeString(item.date);

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
    resultDiv.innerHTML = '';
    resultDiv.classList.remove('active');
  }
}

// ════════════════════════════════════════════════════
// SANITIZATION FUNCTIONS
// ════════════════════════════════════════════════════
function sanitizeString(str) {
  if (typeof str !== 'string') return '';
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#x27;')
    .substring(0, 500); // Limit length
}

function sanitizeNumber(num) {
  const parsed = parseFloat(num);
  return isNaN(parsed) ? 0 : parsed;
