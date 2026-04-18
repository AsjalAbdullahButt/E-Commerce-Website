// === SHOP.JS ===
let currentPage = 1;

async function loadProducts() {
  try {
    // Sync wishlist from backend on initial load
    if (isLoggedIn()) {
      await syncWishlistFromServer();
    }

    const search = document.querySelector('[data-search]')?.value || '';
    const category = document.querySelector('[data-category]')?.value || '';
    const sort = document.querySelector('[data-sort]')?.value || 'newest';

    const params = new URLSearchParams({
      search,
      category,
      sort,
      page: currentPage,
      limit: 12
    });

    const data = await api.get(`/products?${params}`);
    const container = document.querySelector('.product-grid');
    if (!container) return;

    const html = data.products.map(p => {
      const isWishlisted = localStorage.getItem(`wishlist_${p.id}`);
      return `
        <div class="product-card">
          <div class="product-image-wrapper">
            <img src="${p.images?.[0] || './images/fallback.jpg'}" alt="${p.name}" onerror="this.src='./images/fallback.jpg'">
            <button class="wishlist-btn ${isWishlisted ? 'active' : ''}" onclick="toggleWishlist('${p.id}', event)">
              <i class="fas fa-heart"></i>
            </button>
          </div>
          <div class="product-content">
            <p class="product-name">${p.name}</p>
            <p class="product-price">Rs ${p.price.toLocaleString()}</p>
            <div class="product-actions">
              <a href="./product.html?id=${p.id}">View</a>
              <button onclick="quickAddToCart('${p.id}', this)">Add to Cart</button>
            </div>
          </div>
        </div>
      `;
    }).join('');

    container.innerHTML = html;

    // Update load more button
    const loadMoreBtn = document.querySelector('.load-more');
    if (loadMoreBtn) {
      loadMoreBtn.style.display = currentPage < data.pages ? 'flex' : 'none';
    }
  } catch (err) {
    console.error('Failed to load products', err);
    showToast('Failed to load products', 'error');
  }
}

async function toggleWishlist(productId, event) {
  event.preventDefault();
  const btn = event.currentTarget;

  if (!isLoggedIn()) {
    showToast('Please login to add to wishlist', 'warning');
    return;
  }

  try {
    if (btn.classList.contains('active')) {
      await api.delete(`/wishlist/${productId}`, true);
      btn.classList.remove('active');
      localStorage.removeItem(`wishlist_${productId}`);
      showToast('Removed from wishlist');
    } else {
      await api.post(`/wishlist/${productId}`, {}, true);
      btn.classList.add('active');
      localStorage.setItem(`wishlist_${productId}`, '1');
      showToast('Added to wishlist');
    }
  } catch (err) {
    showToast('Error updating wishlist', 'error');
  }
}

async function quickAddToCart(productId, buttonEl) {
  try {
    const product = await api.get(`/products/${productId}`);
    addToCartWithAnimation(buttonEl, {
      id: product.id,
      name: product.name,
      price: product.price,
      images: product.images,
      selectedSize: product.sizes?.[0] || '',
      selectedColor: product.colors?.[0]?.name || ''
    });
  } catch (err) {
    showToast('Failed to add to cart', 'error');
  }
}

async function syncWishlistFromServer() {
  try {
    const wishlist = await api.get('/wishlist', true);
    
    // Clear old wishlist keys
    Object.keys(localStorage)
      .filter(key => key.startsWith('wishlist_'))
      .forEach(key => localStorage.removeItem(key));
    
    // Add items from server
    if (Array.isArray(wishlist)) {
      wishlist.forEach(item => {
        const productId = item.product_id || item.id;
        if (productId) {
          localStorage.setItem(`wishlist_${productId}`, '1');
        }
      });
    }
  } catch (err) {
    // Fail silently - wishlist sync is not critical
    console.log('Wishlist sync skipped');
  }
}

document.addEventListener('DOMContentLoaded', () => {
  loadProducts();

  // Filter event listeners
  document.querySelector('[data-search]')?.addEventListener('input', () => {
    currentPage = 1;
    loadProducts();
  });
  document.querySelector('[data-category]')?.addEventListener('change', () => {
    currentPage = 1;
    loadProducts();
  });
  document.querySelector('[data-sort]')?.addEventListener('change', () => {
    currentPage = 1;
    loadProducts();
  });

  // Load more button
  document.querySelector('.load-more button')?.addEventListener('click', () => {
    currentPage++;
    loadProducts();
  });
});
