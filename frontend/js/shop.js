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
      const img = escapeHtml(p.images?.[0] || '../images/fallback.jpg');
      const name = escapeHtml(p.name || '-');
      const price = escapeHtml((Number(p.price) || 0).toLocaleString());
      const id = encodeURIComponent(p.id);
      return `
        <div class="product-card">
          <div class="product-image-wrapper">
            <img src="${img}" alt="${name}" onerror="this.src='../images/fallback.jpg'">
            <button class="wishlist-btn ${isWishlisted ? 'active' : ''}" onclick="toggleWishlist('${id}', event)">
              <i class="fas fa-heart"></i>
            </button>
          </div>
          <div class="product-content">
            <p class="product-name">${name}</p>
            <p class="product-price">Rs ${price}</p>
            <div class="product-actions">
              <a href="./product.html?id=${id}">View</a>
              <button onclick="quickAddToCart('${id}', this)">Add to Cart</button>
            </div>
          </div>
        </div>
      `;
    }).join('');

    container.textContent = '';
    const frag = document.createDocumentFragment();
    data.products.forEach(p => {
      const card = document.createElement('div'); card.className = 'product-card';
      const wrapper = document.createElement('div'); wrapper.className = 'product-image-wrapper';
      const img = document.createElement('img'); img.src = p.images?.[0] || '../images/fallback.jpg'; img.alt = p.name || '-'; img.onerror = () => img.src = '../images/fallback.jpg';
      const wishBtn = document.createElement('button'); wishBtn.className = `wishlist-btn ${localStorage.getItem(`wishlist_${p.id}`) ? 'active' : ''}`; wishBtn.addEventListener('click', (e) => { e.preventDefault(); toggleWishlist(encodeURIComponent(p.id), e); });
      const heart = document.createElement('i'); heart.className = 'fas fa-heart'; wishBtn.appendChild(heart);
      wrapper.appendChild(img); wrapper.appendChild(wishBtn);
      const content = document.createElement('div'); content.className = 'product-content';
      const nameP = document.createElement('p'); nameP.className = 'product-name'; nameP.textContent = p.name || '-';
      const priceP = document.createElement('p'); priceP.className = 'product-price'; priceP.textContent = `Rs ${Number(p.price||0).toLocaleString()}`;
      const actions = document.createElement('div'); actions.className = 'product-actions';
      const viewA = document.createElement('a'); viewA.href = `./product.html?id=${encodeURIComponent(p.id)}`; viewA.textContent = 'View';
      const addBtn = document.createElement('button'); addBtn.textContent = 'Add to Cart'; addBtn.addEventListener('click', () => quickAddToCart(encodeURIComponent(p.id), addBtn));
      actions.appendChild(viewA); actions.appendChild(addBtn);
      content.appendChild(nameP); content.appendChild(priceP); content.appendChild(actions);
      card.appendChild(wrapper); card.appendChild(content);
      frag.appendChild(card);
    });
    container.appendChild(frag);

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
    const variants = Array.isArray(product.variants) ? product.variants : [];
    const inStock = variants.find(v => v.stock > 0);

    if (variants.length && !inStock) {
      showToast('This product is out of stock', 'error');
      return;
    }
    if (variants.length > 1) {
      // Multiple size/color combos exist — let the shopper choose on the product page
      // instead of guessing which variant "Quick Add" should pick.
      window.location.href = `./product.html?id=${encodeURIComponent(productId)}`;
      return;
    }

    addToCartWithAnimation(buttonEl, {
      id: product.id,
      name: product.name,
      price: product.price,
      images: product.images,
      selectedSize: inStock?.size || '',
      selectedColor: inStock?.color || ''
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

