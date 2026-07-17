// === PRODUCT.JS ===
function swatchColorMap(name) {
  const map = { black: '#111111', white: '#f5f5f5', grey: '#888888', gray: '#888888', navy: '#1b2a4a', beige: '#d8c7a1', olive: '#5c5c33', maroon: '#5c1f2e' };
  const key = String(name || '').trim().toLowerCase();
  return map[key] || key || '#888';
}

async function loadProduct() {
  const id = new URLSearchParams(window.location.search).get('id');
  
  // NULL ID GUARD — Show friendly error page
  if (!id) {
    const main = document.querySelector('main');
    if (main) {
      const wrapper = document.createElement('div'); wrapper.style.textAlign = 'center'; wrapper.style.padding = '6rem 2rem';
      const icon = document.createElement('i'); icon.className = 'fas fa-box-open'; icon.style.fontSize = '3rem'; icon.style.opacity = '0.3'; icon.style.color = 'var(--gold)';
      const h2 = document.createElement('h2'); h2.style.marginTop = '1rem'; h2.textContent = 'Product Not Found';
      const p = document.createElement('p'); p.style.color = 'var(--text-secondary)'; p.style.margin = '0.5rem 0 2rem'; p.textContent = 'No product ID was provided.';
      const a = document.createElement('a'); a.href = './shop.html'; a.className = 'btn-primary'; a.textContent = 'Browse Shop';
      wrapper.appendChild(icon); wrapper.appendChild(h2); wrapper.appendChild(p); wrapper.appendChild(a);
      main.appendChild(wrapper);
    }
    return; // Stop all further execution
  }

  try {
    const product = await api.get(`/products/${id}`);

    // Update main image
    const mainImg = document.querySelector('.main-image img');
    if (mainImg) {
      mainImg.src = product.images?.[0] || '../images/fallback.jpg';
      mainImg.alt = product.name || 'Product';
      mainImg.onerror = () => mainImg.src = '../images/fallback.jpg';
    }

    // Update thumbnails
    const thumbnails = document.querySelector('.thumbnails');
    if (thumbnails && product.images) {
      thumbnails.textContent = '';
      product.images.forEach((img, idx) => {
        const div = document.createElement('div'); div.className = `thumbnail ${idx === 0 ? 'active' : ''}`;
        div.dataset.src = encodeURIComponent(img);
        const im = document.createElement('img'); im.src = img; im.alt = `Thumbnail ${idx + 1}`; im.onerror = () => im.src = '../images/fallback.jpg';
        div.appendChild(im);
        div.addEventListener('click', () => {
          const src = div.dataset.src ? decodeURIComponent(div.dataset.src) : im.src;
          changeImage(src, div);
        });
        thumbnails.appendChild(div);
      });
    }

    // Update details
    document.querySelector('.product-name').textContent = product.name;
    document.querySelector('.product-price').textContent = `Rs ${Number(product.price || 0).toLocaleString()}`;
    document.querySelector('.product-description').textContent = product.description;

    setupVariantSelectors(product);

    // Load reviews
    await loadReviews(id);
  } catch (err) {
    console.error('Failed to load product', err);
    showToast('Failed to load product', 'error');
  }
}

function setupVariantSelectors(product) {
  const variants = Array.isArray(product.variants) ? product.variants : [];
  const sizeContainer = document.querySelector('.size-options');
  const colorContainer = document.querySelector('.color-options');
  const qtySpan = document.querySelector('.quantity-input span');
  const qtyMinus = document.querySelector('.quantity-input button:first-child');
  const qtyPlus = document.querySelector('.quantity-input button:last-child');
  const addBtn = document.querySelector('.add-to-cart-btn');
  const stockIndicator = document.querySelector('.stock-indicator');

  const sizes = [...new Set(variants.map(v => v.size))];
  const colors = [...new Set(variants.map(v => v.color))];

  const state = { size: null, color: null };

  function findVariant() {
    return variants.find(v => v.size === state.size && v.color === state.color) || null;
  }

  function refresh() {
    const variant = findVariant();
    const stock = variant ? variant.stock : 0;
    const qty = Math.max(1, parseInt(qtySpan?.textContent, 10) || 1);

    if (qtySpan) qtySpan.textContent = String(Math.min(qty, Math.max(stock, 1)));
    if (qtyMinus) qtyMinus.disabled = !variant || stock === 0;
    if (qtyPlus) qtyPlus.disabled = !variant || stock === 0 || qty >= stock;

    if (addBtn) {
      const ready = Boolean(state.size && state.color);
      if (!ready) {
        addBtn.disabled = false;
        addBtn.textContent = 'Add to Cart';
      } else if (!variant || stock === 0) {
        addBtn.disabled = true;
        addBtn.textContent = 'Out of Stock';
      } else {
        addBtn.disabled = false;
        addBtn.textContent = 'Add to Cart';
      }
    }

    if (stockIndicator) {
      stockIndicator.classList.remove('in-stock', 'low-stock', 'out-of-stock-msg');
      if (!state.size || !state.color) {
        stockIndicator.textContent = '';
      } else if (!variant || stock === 0) {
        stockIndicator.classList.add('out-of-stock-msg');
        stockIndicator.textContent = 'Out of stock in this size/color';
      } else if (stock <= 5) {
        stockIndicator.classList.add('low-stock');
        stockIndicator.textContent = '';
        const dot = document.createElement('span'); dot.className = 'stock-dot';
        stockIndicator.appendChild(dot);
        stockIndicator.appendChild(document.createTextNode(`Only ${stock} left in stock`));
      } else {
        stockIndicator.classList.add('in-stock');
        stockIndicator.textContent = '';
        const dot = document.createElement('span'); dot.className = 'stock-dot';
        stockIndicator.appendChild(dot);
        stockIndicator.appendChild(document.createTextNode('In stock'));
      }
    }
  }

  if (sizeContainer) {
    sizeContainer.textContent = '';
    sizes.forEach(size => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'size-btn';
      btn.textContent = size;
      const hasStock = variants.some(v => v.size === size && v.stock > 0);
      if (!hasStock) btn.classList.add('out-of-stock');
      btn.addEventListener('click', () => {
        state.size = size;
        sizeContainer.querySelectorAll('.size-btn').forEach(b => b.classList.remove('selected'));
        btn.classList.add('selected');
        refresh();
      });
      sizeContainer.appendChild(btn);
    });
  }

  if (colorContainer) {
    colorContainer.textContent = '';
    colors.forEach(color => {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'size-btn color-btn';
      btn.setAttribute('data-color', color);
      const dot = document.createElement('span');
      dot.className = 'color-btn-dot';
      dot.style.background = swatchColorMap(color);
      btn.appendChild(dot);
      btn.appendChild(document.createTextNode(color));
      const hasStock = variants.some(v => v.color === color && v.stock > 0);
      if (!hasStock) btn.classList.add('out-of-stock');
      btn.addEventListener('click', () => {
        state.color = color;
        colorContainer.querySelectorAll('.color-btn').forEach(b => b.classList.remove('selected'));
        btn.classList.add('selected');
        refresh();
      });
      colorContainer.appendChild(btn);
    });
  }

  qtyMinus?.addEventListener('click', () => {
    let qty = parseInt(qtySpan.textContent, 10) || 1;
    if (qty > 1) qtySpan.textContent = qty - 1;
    refresh();
  });

  qtyPlus?.addEventListener('click', () => {
    const variant = findVariant();
    let qty = parseInt(qtySpan.textContent, 10) || 1;
    if (variant && qty < variant.stock) qtySpan.textContent = qty + 1;
    refresh();
  });

  addBtn?.addEventListener('click', () => {
    if (!state.size || !state.color) {
      showToast('Please select a size and color', 'warning');
      return;
    }
    const variant = findVariant();
    if (!variant || variant.stock <= 0) {
      showToast('This size/color combination is out of stock', 'error');
      return;
    }
    const qty = Math.min(parseInt(qtySpan.textContent, 10) || 1, variant.stock);
    const item = {
      id: product.id,
      name: product.name,
      price: product.price,
      images: product.images,
      selectedSize: state.size,
      selectedColor: state.color,
    };

    // addToCartWithAnimation() already calls addToCart() once (plus the fly-to-cart animation),
    // so only the remaining qty-1 units are added directly here — calling it with `{}` on top of
    // this loop (the previous code) pushed a second, field-less cart line on every click, which
    // POST /orders then rejected outright since that line has no product_id/name/price/size/color.
    for (let i = 0; i < qty - 1; i++) {
      addToCart(item);
    }
    addToCartWithAnimation(addBtn, item);
  });

  refresh();
}

function changeImage(imageSrc, element) {
  const mainImg = document.querySelector('.main-image img');
  if (mainImg) {
    if (mainImg.src === imageSrc) return;
    mainImg.classList.add('fading');
    setTimeout(() => {
      mainImg.src = imageSrc;
      mainImg.classList.remove('fading');
    }, 180);
  }
  document.querySelectorAll('.thumbnail').forEach(t => t.classList.remove('active'));
  element.classList.add('active');
}

function setupImageZoom() {
  const wrapper = document.querySelector('.main-image');
  const img = wrapper?.querySelector('img');
  if (!wrapper || !img) return;
  const fine = window.matchMedia('(pointer: fine)').matches;
  if (!fine) return;

  wrapper.addEventListener('mousemove', (e) => {
    const rect = wrapper.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * 100;
    const y = ((e.clientY - rect.top) / rect.height) * 100;
    wrapper.style.setProperty('--zoom-x', `${x}%`);
    wrapper.style.setProperty('--zoom-y', `${y}%`);
    wrapper.classList.add('zoomed');
  });

  wrapper.addEventListener('mouseleave', () => {
    wrapper.classList.remove('zoomed');
  });
}

async function loadReviews(productId) {
  try {
    const reviews = await api.get(`/reviews/${productId}`);
    const section = document.querySelector('.reviews-section');
    if (!section || !reviews.length) return;

    const container = section.querySelector('.reviews-content') || null;
    const wrapper = document.createElement('div'); wrapper.className = 'reviews-content';
    reviews.forEach(r => {
      const rev = document.createElement('div'); rev.className = 'review';
      const header = document.createElement('div'); header.className = 'review-header';
      const name = document.createElement('p'); name.className = 'review-name'; name.textContent = r.user_name || 'Anonymous';
      const rating = document.createElement('p'); rating.className = 'review-rating'; rating.textContent = `${'⭐'.repeat(Number(r.rating)||0)} (${String(r.rating) || '0'}/5)`;
      header.appendChild(name); header.appendChild(rating);
      const comment = document.createElement('p'); comment.className = 'review-comment'; comment.textContent = r.comment || '';
      rev.appendChild(header); rev.appendChild(comment);
      wrapper.appendChild(rev);
    });

    if (container) {
      container.textContent = '';
      container.appendChild(wrapper);
    } else if (section) {
      section.insertBefore(wrapper, section.firstChild);
    }
  } catch (err) {
    console.error('Failed to load reviews', err);
  }
}

document.addEventListener('DOMContentLoaded', () => {
  loadProduct();
  setupImageZoom();
});

