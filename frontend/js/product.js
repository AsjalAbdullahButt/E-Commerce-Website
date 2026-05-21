// === PRODUCT.JS ===
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

    // Update size options
    const sizeBtns = document.querySelectorAll('.size-btn');
    sizeBtns.forEach(btn => {
      btn.onclick = () => {
        document.querySelectorAll('.size-btn').forEach(b => b.classList.remove('selected'));
        btn.classList.add('selected');
      };
    });

    // Update color swatches
    const colorSwatches = document.querySelectorAll('.color-swatch');
    colorSwatches.forEach(swatch => {
      swatch.onclick = () => {
        document.querySelectorAll('.color-swatch').forEach(s => s.classList.remove('selected'));
        swatch.classList.add('selected');
      };
      // Set first as selected
      if (colorSwatches[0] === swatch) swatch.classList.add('selected');
    });

    // Quantity handlers
    const qtyMinus = document.querySelector('.quantity-input button:first-child');
    const qtyPlus = document.querySelector('.quantity-input button:last-child');
    const qtySpan = document.querySelector('.quantity-input span');

    qtyMinus?.addEventListener('click', () => {
      let qty = parseInt(qtySpan.textContent);
      if (qty > 1) qtySpan.textContent = qty - 1;
    });

    qtyPlus?.addEventListener('click', () => {
      let qty = parseInt(qtySpan.textContent);
      qtySpan.textContent = qty + 1;
    });

    // Add to cart button
    const addBtn = document.querySelector('.add-to-cart-btn');
    if (addBtn) {
      addBtn.addEventListener('click', () => {
        const size = document.querySelector('.size-btn.selected')?.textContent;
        const color = document.querySelector('.color-swatch.selected')?.getAttribute('data-color');
        const qty = parseInt(document.querySelector('.quantity-input span').textContent);

        if (!size) {
          showToast('Please select a size', 'warning');
          return;
        }

        for (let i = 0; i < qty; i++) {
          addToCart({
            id: product.id,
            name: product.name,
            price: product.price,
            images: product.images,
            selectedSize: size,
            selectedColor: color || product.colors?.[0]?.name || ''
          });
        }

        addToCartWithAnimation(addBtn, {});
      });
    }

    // Load reviews
    await loadReviews(id);
  } catch (err) {
    console.error('Failed to load product', err);
    showToast('Failed to load product', 'error');
  }
}

function changeImage(imageSrc, element) {
  document.querySelector('.main-image img').src = imageSrc;
  document.querySelectorAll('.thumbnail').forEach(t => t.classList.remove('active'));
  element.classList.add('active');
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

document.addEventListener('DOMContentLoaded', loadProduct);

