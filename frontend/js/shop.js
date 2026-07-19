// === SHOP.JS ===
let currentPage = 1;

const SWATCH_COLOR_MAP = {
  black: '#111111', white: '#f5f5f5', grey: '#888888', gray: '#888888',
  navy: '#1b2a4a', beige: '#d8c7a1', olive: '#5c5c33', maroon: '#5c1f2e'
};

function swatchColor(name) {
  const key = String(name || '').trim().toLowerCase();
  return SWATCH_COLOR_MAP[key] || key || '#888';
}

function renderSkeletonCards(container, count) {
  container.textContent = '';
  const frag = document.createDocumentFragment();
  for (let i = 0; i < count; i++) {
    const card = document.createElement('div');
    card.className = 'product-card-skeleton';
    const img = document.createElement('div'); img.className = 'skel-image skeleton';
    const line1 = document.createElement('div'); line1.className = 'skel-line skeleton';
    const line2 = document.createElement('div'); line2.className = 'skel-line price skeleton';
    card.appendChild(img); card.appendChild(line1); card.appendChild(line2);
    frag.appendChild(card);
  }
  container.appendChild(frag);
}

function buildProductCard(p) {
  const isWishlisted = localStorage.getItem(`wishlist_${p.id}`);
  const card = document.createElement('div'); card.className = 'product-card'; card.dataset.id = p.id;
  const wrapper = document.createElement('div'); wrapper.className = 'product-image-wrapper';
  const img = document.createElement('img'); img.src = p.images?.[0] || '../images/fallback.jpg'; img.alt = p.name || '-'; img.onerror = () => img.src = '../images/fallback.jpg';
  wrapper.appendChild(img);

  if (p.images?.[1]) {
    const altImg = document.createElement('img'); altImg.className = 'product-image-alt'; altImg.src = p.images[1]; altImg.alt = ''; altImg.loading = 'lazy';
    wrapper.appendChild(altImg);
  }

  const wishBtn = document.createElement('button'); wishBtn.className = `wishlist-btn pop-btn ${isWishlisted ? 'active' : ''}`; wishBtn.addEventListener('click', (e) => { e.preventDefault(); toggleWishlist(encodeURIComponent(p.id), e); });
  const heart = document.createElement('i'); heart.className = 'fas fa-heart'; wishBtn.appendChild(heart);
  wrapper.appendChild(wishBtn);

  const variants = Array.isArray(p.variants) ? p.variants : [];
  const colors = [...new Set(variants.map(v => v.color).filter(Boolean))];
  if (colors.length > 1) {
    const swatches = document.createElement('div'); swatches.className = 'color-swatches';
    colors.slice(0, 5).forEach(color => {
      const sw = document.createElement('span'); sw.className = 'swatch'; sw.title = color;
      sw.style.background = swatchColor(color);
      swatches.appendChild(sw);
    });
    wrapper.appendChild(swatches);
  }

  const content = document.createElement('div'); content.className = 'product-content';
  const nameP = document.createElement('p'); nameP.className = 'product-name'; nameP.textContent = p.name || '-';
  const priceP = document.createElement('p'); priceP.className = 'product-price'; priceP.textContent = `Rs ${Number(p.price || 0).toLocaleString()}`;
  const actions = document.createElement('div'); actions.className = 'product-actions';
  const viewA = document.createElement('a'); viewA.href = `./product.html?id=${encodeURIComponent(p.id)}`; viewA.textContent = 'View';
  const addBtn = document.createElement('button'); addBtn.className = 'magnetic-btn'; addBtn.textContent = 'Add to Cart'; addBtn.addEventListener('click', () => quickAddToCart(encodeURIComponent(p.id), addBtn));
  actions.appendChild(viewA); actions.appendChild(addBtn);
  content.appendChild(nameP); content.appendChild(priceP); content.appendChild(actions);
  card.appendChild(wrapper); card.appendChild(content);
  return card;
}

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

    const container = document.querySelector('.product-grid');
    if (!container) return;

    const isFreshQuery = currentPage === 1;
    const existingCards = isFreshQuery ? Array.from(container.querySelectorAll('.product-card')) : [];
    const oldRects = new Map();
    existingCards.forEach(card => oldRects.set(card.dataset.id, card.getBoundingClientRect()));

    // First-ever load (empty grid): show a skeleton state instead of a blank gap.
    if (isFreshQuery && existingCards.length === 0) {
      renderSkeletonCards(container, 8);
    }

    const data = await api.get(`/products?${params}`);

    if (isFreshQuery) {
      container.textContent = '';
      if (!data.products || data.products.length === 0) {
        renderEmptyStateInto(container, {
          icon: 'fa-box-open',
          title: 'No products found',
          message: 'Try different filters, or clear them to browse the full catalog.',
        });
      }
      const frag = document.createDocumentFragment();
      data.products.forEach(p => frag.appendChild(buildProductCard(p)));
      container.appendChild(frag);

      // FLIP: cards that existed before just moved/reflowed — invert then play.
      // Cards that are new to this result set get a staggered fade/slide entrance.
      const newCards = Array.from(container.querySelectorAll('.product-card'));
      newCards.forEach((card, idx) => {
        const oldRect = oldRects.get(card.dataset.id);
        if (oldRect) {
          const newRect = card.getBoundingClientRect();
          const dx = oldRect.left - newRect.left;
          const dy = oldRect.top - newRect.top;
          if (dx || dy) {
            card.style.transition = 'none';
            card.style.transform = `translate(${dx}px, ${dy}px)`;
            requestAnimationFrame(() => {
              card.style.transition = `transform var(--duration-slow) var(--ease)`;
              card.style.transform = '';
            });
          }
        } else {
          card.style.opacity = '0';
          card.style.transform = 'translateY(16px)';
          requestAnimationFrame(() => {
            card.style.transition = `opacity var(--duration-slow) var(--ease) ${idx * 30}ms, transform var(--duration-slow) var(--ease) ${idx * 30}ms`;
            card.style.opacity = '1';
            card.style.transform = 'none';
          });
        }
      });
    } else {
      // Load-more: append with a simple entrance, existing cards stay untouched.
      const frag = document.createDocumentFragment();
      data.products.forEach((p, idx) => {
        const card = buildProductCard(p);
        card.style.opacity = '0';
        card.style.transform = 'translateY(16px)';
        frag.appendChild(card);
      });
      container.appendChild(frag);
      requestAnimationFrame(() => {
        Array.from(container.querySelectorAll('.product-card')).slice(-data.products.length).forEach((card, idx) => {
          card.style.transition = `opacity var(--duration-slow) var(--ease) ${idx * 30}ms, transform var(--duration-slow) var(--ease) ${idx * 30}ms`;
          card.style.opacity = '1';
          card.style.transform = 'none';
        });
      });
    }

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

