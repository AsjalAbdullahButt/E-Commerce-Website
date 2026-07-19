// === SHOP.JS ===
let currentPage = 1;

// swatchColor + renderProductCardSkeletons come from shared/js/ui-states.js, loaded before this file.

// buildProductCard/toggleWishlist/quickAddToCart come from shared/js/product-card.js,
// loaded before this file.

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
      renderProductCardSkeletons(container, 8);
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

