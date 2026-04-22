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
  const orderNumber = document.getElementById('tracking-order-input').value.trim();
  
  if (!orderNumber) {
    showToast('Please enter an order number', 'warning');
    return;
  }

  const resultDiv = document.getElementById('tracking-result');
  resultDiv.innerHTML = '<div class="loading-spinner"><i class="fas fa-spinner"></i> Loading...</div>';

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
      resultDiv.innerHTML = `<div style="color: var(--text-secondary); padding: 2rem; text-align: center;">
        <i class="fas fa-search" style="font-size: 2rem; opacity: 0.5; margin-bottom: 1rem; display: block;"></i>
        <p>Order not found. Please check the order number and try again.</p>
      </div>`;
      return;
    }

    // Display order details
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

    resultDiv.innerHTML = `
      <div class="order-status">
        <div class="order-header">
          <div class="order-detail">
            <label>Order Number</label>
            <p>${order.id}</p>
          </div>
          <div class="order-detail">
            <label>Status</label>
            <p style="color: ${statusColors[order.status]}">${statusText[order.status]}</p>
          </div>
          <div class="order-detail">
            <label>Order Date</label>
            <p>${new Date(order.date).toLocaleDateString()}</p>
          </div>
          <div class="order-detail">
            <label>Total Amount</label>
            <p>Rs ${order.total.toLocaleString()}</p>
          </div>
        </div>
        
        <div style="margin-bottom: 1.5rem; text-align: left;">
          <strong style="color: var(--text-primary);">Items:</strong>
          <ul style="margin: 0.5rem 0 0; padding-left: 1.5rem; color: var(--text-secondary);">
            ${order.items.map(item => `<li>${item}</li>`).join('')}
          </ul>
        </div>

        <div class="order-timeline">
          <strong style="display: block; margin-bottom: 1rem; color: var(--text-primary);">Delivery Timeline</strong>
          ${order.timeline.map((item, idx) => `
            <div class="timeline-item">
              <div class="timeline-dot" style="background: ${item.completed ? 'var(--gold)' : 'var(--border)'}">
                ${item.completed ? '✓' : idx + 1}
              </div>
              <div class="timeline-content">
                <strong>${item.stage}</strong>
                <span>${item.date}</span>
              </div>
            </div>
          `).join('')}
        </div>
      </div>
    `;

  } catch (err) {
    console.error('Order tracking error:', err);
    showToast('Error fetching order details', 'error');
    resultDiv.innerHTML = '';
  }
}
