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

document.addEventListener('DOMContentLoaded', loadFeaturedProducts);
