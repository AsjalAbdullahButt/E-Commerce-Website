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

    // Get unique categories from products
    const categories = data.categories || ['All', 'T-Shirts', 'Hoodies', 'Pants', 'Accessories'];
    
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
    const fallbackCategories = ['All', 'T-Shirts', 'Hoodies', 'Pants', 'Accessories'];
    container.innerHTML = fallbackCategories.map((cat, idx) => `
      <div class="category-item ${idx === 0 ? 'active' : ''}" data-category="${cat}">
        <i class="fas fa-tag"></i>
        <span>${cat}</span>
      </div>
    `).join('');
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
});
