/* Shared product-card component for grid pages (customer home + shop).
   Plain global-scope script by design (no modules — see scripts/build-dist.js); load after
   api.js/auth.js/cart.js/ui-states.js and before the page's own JS. Markup pairs with
   shared/css/product-card.css; interaction layers (tilt, swatch reveal, magnetic buttons)
   come from the .product-card system in global.css + shared/js/product-tilt.js. */

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
