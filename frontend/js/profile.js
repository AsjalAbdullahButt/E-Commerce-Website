// === PROFILE.JS ===
document.addEventListener('DOMContentLoaded', async () => {
  requireAuth(['customer']);

  const user = getUser();
  const tabs = document.querySelectorAll('.tab-btn');
  const contents = document.querySelectorAll('.tab-content');

  tabs.forEach(tab => {
    tab.addEventListener('click', () => {
      tabs.forEach(t => t.classList.remove('active'));
      contents.forEach(c => c.classList.remove('active'));
      tab.classList.add('active');
      document.querySelector(`.tab-content[data-tab="${tab.dataset.tab}"]`)?.classList.add('active');
    });
  });

  // Load profile info
  const profileContent = document.querySelector('[data-tab="profile"]');
  if (profileContent) {
    profileContent.innerHTML = `
      <div class="profile-info">
        <div class="info-item">
          <span class="info-label">Name</span>
          <span class="info-value">${user.name}</span>
        </div>
        <div class="info-item">
          <span class="info-label">Email</span>
          <span class="info-value">${user.email}</span>
        </div>
        <div class="info-item">
          <span class="info-label">Phone</span>
          <span class="info-value">${user.phone || 'Not provided'}</span>
        </div>
        <div class="info-item">
          <span class="info-label">Address</span>
          <span class="info-value">${user.address || 'Not provided'}</span>
        </div>
        <button class="edit-profile-btn" onclick="showEditForm()">Edit Profile</button>
        <div id="edit-form" style="display:none; margin-top: 2rem;">
          <div class="edit-form full">
            <div class="form-group">
              <label>Name</label>
              <input type="text" id="edit-name" value="${user.name}">
            </div>
            <div class="form-group">
              <label>Phone</label>
              <input type="tel" id="edit-phone" value="${user.phone || ''}">
            </div>
            <div class="form-group">
              <label>Address</label>
              <textarea id="edit-address">${user.address || ''}</textarea>
            </div>
            <div class="form-actions">
              <button class="save-btn" onclick="saveProfile()">Save Changes</button>
              <button class="cancel-btn" onclick="hideEditForm()">Cancel</button>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  // Load orders
  const ordersContent = document.querySelector('[data-tab="orders"]');
  if (ordersContent) {
    try {
      const orders = await api.get('/orders/me', true);
      if (orders.length === 0) {
        ordersContent.innerHTML = '<p style="text-align:center;color:var(--text-secondary);">No orders yet</p>';
      } else {
        ordersContent.innerHTML = `
          <table class="orders-table">
            <thead>
              <tr>
                <th>Order ID</th>
                <th>Date</th>
                <th>Total</th>
                <th>Status</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              ${orders.map(o => `
                <tr>
                  <td>${o.id.substring(0, 8)}...</td>
                  <td>${new Date(o.created_at).toLocaleDateString()}</td>
                  <td>Rs ${o.total.toLocaleString()}</td>
                  <td><span class="order-status ${o.status}">${o.status}</span></td>
                  <td><a href="./tracking.html?id=${o.id}" style="color:var(--gold);">Track</a></td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        `;
      }
    } catch (err) {
      ordersContent.innerHTML = '<p style="color:var(--error);">Failed to load orders</p>';
    }
  }

  // Load wishlist
  const wishlistContent = document.querySelector('[data-tab="wishlist"]');
  if (wishlistContent) {
    try {
      const wishlist = await api.get('/wishlist', true);
      if (wishlist.length === 0) {
        wishlistContent.innerHTML = '<p style="text-align:center;color:var(--text-secondary);">Wishlist is empty</p>';
      } else {
        wishlistContent.innerHTML = `
          <div class="wishlist-grid">
            ${wishlist.map(p => `
              <div class="wishlist-item">
                <div class="wishlist-image">
                  <img src="${p.images?.[0]}" alt="${p.name}" onerror="this.src='./images/fallback.jpg'">
                </div>
                <div class="wishlist-info">
                  <p class="wishlist-name">${p.name}</p>
                  <p class="wishlist-price">Rs ${p.price.toLocaleString()}</p>
                  <div class="wishlist-actions">
                    <button onclick="location.href='./product.html?id=${p.id}'">View</button>
                    <button onclick="removeWishlistItem('${p.id}')">Remove</button>
                  </div>
                </div>
              </div>
            `).join('')}
          </div>
        `;
      }
    } catch (err) {
      wishlistContent.innerHTML = '<p style="color:var(--error);">Failed to load wishlist</p>';
    }
  }
});

function showEditForm() {
  document.getElementById('edit-form').style.display = 'block';
  document.querySelector('.edit-profile-btn').style.display = 'none';
}

function hideEditForm() {
  document.getElementById('edit-form').style.display = 'none';
  document.querySelector('.edit-profile-btn').style.display = 'block';
}

async function saveProfile() {
  const name = document.getElementById('edit-name').value;
  const phone = document.getElementById('edit-phone').value;
  const address = document.getElementById('edit-address').value;

  try {
    await api.patch('/auth/me', { name, phone, address }, true);
    const user = getUser();
    Object.assign(user, { name, phone, address });
    localStorage.setItem('ecom_user', JSON.stringify(user));
    showToast('Profile updated successfully!');
    location.reload();
  } catch (err) {
    showToast('Failed to update profile', 'error');
  }
}

async function removeWishlistItem(productId) {
  try {
    await api.delete(`/wishlist/${productId}`, true);
    showToast('Removed from wishlist');
    location.reload();
  } catch (err) {
    showToast('Failed to remove item', 'error');
  }
}
