// === PRODUCT.JS ===
async function loadProduct() {
  const id = new URLSearchParams(window.location.search).get('id');
  
  // NULL ID GUARD — Show friendly error page
  if (!id) {
    const main = document.querySelector('main');
    if (main) {
      main.innerHTML = `
        <div style="text-align:center;padding:6rem 2rem;">
          <i class="fas fa-box-open" style="font-size:3rem;opacity:0.3;color:var(--gold)"></i>
          <h2 style="margin-top:1rem;">Product Not Found</h2>
          <p style="color:var(--text-secondary);margin:0.5rem 0 2rem;">No product ID was provided.</p>
          <a href="./shop.html" class="btn-primary">Browse Shop</a>
        </div>`;
    }
    return; // Stop all further execution
  }

  try {
    const product = await api.get(`/products/${id}`);

    // Update main image
    const mainImg = document.querySelector('.main-image img');
    if (mainImg) {
      mainImg.src = product.images?.[0] || './images/fallback.jpg';
      mainImg.onerror = () => mainImg.src = './images/fallback.jpg';
    }

    // Update thumbnails
    const thumbnails = document.querySelector('.thumbnails');
    if (thumbnails && product.images) {
      thumbnails.innerHTML = product.images.map((img, idx) => `
        <div class="thumbnail ${idx === 0 ? 'active' : ''}" onclick="changeImage('${img}', this)">
          <img src="${img}" alt="Thumbnail ${idx + 1}" onerror="this.src='./images/fallback.jpg'">
        </div>
      `).join('');
    }

    // Update details
    document.querySelector('.product-name').textContent = product.name;
    document.querySelector('.product-price').textContent = `Rs ${product.price.toLocaleString()}`;
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

    const html = reviews.map(r => `
      <div class="review">
        <div class="review-header">
          <p class="review-name">${r.user_name}</p>
          <p class="review-rating">${'⭐'.repeat(r.rating)} (${r.rating}/5)</p>
        </div>
        <p class="review-comment">${r.comment}</p>
      </div>
    `).join('');

    const container = section.querySelector('.reviews-content') || section;
    if (!container.querySelector('.reviews-content')) {
      container.innerHTML = `<div class="reviews-content">${html}</div>` + container.innerHTML;
    } else {
      container.querySelector('.reviews-content').innerHTML = html;
    }
  } catch (err) {
    console.error('Failed to load reviews', err);
  }
}

document.addEventListener('DOMContentLoaded', loadProduct);
