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
    profileContent.textContent = '';
    const infoWrap = document.createElement('div'); infoWrap.className = 'profile-info';
    const makeInfoItem = (label, value) => {
      const div = document.createElement('div'); div.className = 'info-item';
      const sLabel = document.createElement('span'); sLabel.className = 'info-label'; sLabel.textContent = label;
      const sVal = document.createElement('span'); sVal.className = 'info-value'; sVal.textContent = value;
      div.appendChild(sLabel); div.appendChild(sVal); return div;
    };
    infoWrap.appendChild(makeInfoItem('Name', user.name || ''));
    infoWrap.appendChild(makeInfoItem('Email', user.email || ''));
    infoWrap.appendChild(makeInfoItem('Phone', user.phone || 'Not provided'));
    infoWrap.appendChild(makeInfoItem('Address', user.address || 'Not provided'));
    const editBtn = document.createElement('button'); editBtn.className = 'edit-profile-btn'; editBtn.textContent = 'Edit Profile'; editBtn.addEventListener('click', showEditForm);
    infoWrap.appendChild(editBtn);

    const editFormWrap = document.createElement('div'); editFormWrap.id = 'edit-form'; editFormWrap.style.display = 'none'; editFormWrap.style.marginTop = '2rem';
    const editForm = document.createElement('div'); editForm.className = 'edit-form full';
    const nameGroup = document.createElement('div'); nameGroup.className = 'form-group'; const nameLabel = document.createElement('label'); nameLabel.textContent = 'Name'; const nameInput = document.createElement('input'); nameInput.type = 'text'; nameInput.id = 'edit-name'; nameInput.value = user.name || '';
    nameGroup.appendChild(nameLabel); nameGroup.appendChild(nameInput);
    const phoneGroup = document.createElement('div'); phoneGroup.className = 'form-group'; const phoneLabel = document.createElement('label'); phoneLabel.textContent = 'Phone'; const phoneInput = document.createElement('input'); phoneInput.type = 'tel'; phoneInput.id = 'edit-phone'; phoneInput.value = user.phone || '';
    phoneGroup.appendChild(phoneLabel); phoneGroup.appendChild(phoneInput);
    const addrGroup = document.createElement('div'); addrGroup.className = 'form-group'; const addrLabel = document.createElement('label'); addrLabel.textContent = 'Address'; const addrTextarea = document.createElement('textarea'); addrTextarea.id = 'edit-address'; addrTextarea.textContent = user.address || '';
    addrGroup.appendChild(addrLabel); addrGroup.appendChild(addrTextarea);
    const actionsDiv = document.createElement('div'); actionsDiv.className = 'form-actions'; const saveBtn = document.createElement('button'); saveBtn.className = 'save-btn'; saveBtn.textContent = 'Save Changes'; saveBtn.addEventListener('click', saveProfile); const cancelBtn = document.createElement('button'); cancelBtn.className = 'cancel-btn'; cancelBtn.textContent = 'Cancel'; cancelBtn.addEventListener('click', hideEditForm);
    actionsDiv.appendChild(saveBtn); actionsDiv.appendChild(cancelBtn);
    editForm.appendChild(nameGroup); editForm.appendChild(phoneGroup); editForm.appendChild(addrGroup); editForm.appendChild(actionsDiv);
    editFormWrap.appendChild(editForm);
    infoWrap.appendChild(editFormWrap);
    profileContent.appendChild(infoWrap);
  }

  // Load orders
  const ordersContent = document.querySelector('[data-tab="orders"]');
  if (ordersContent) {
    try {
      const orders = await api.get('/orders/me', true);
        if (orders.length === 0) {
          ordersContent.textContent = '';
          const p = document.createElement('p'); p.style.textAlign = 'center'; p.style.color = 'var(--text-secondary)'; p.textContent = 'No orders yet'; ordersContent.appendChild(p);
        } else {
          ordersContent.textContent = '';
          const table = document.createElement('table'); table.className = 'orders-table';
          const thead = document.createElement('thead'); const trHead = document.createElement('tr'); ['Order ID','Date','Total','Status','Action'].forEach(h => { const th = document.createElement('th'); th.textContent = h; trHead.appendChild(th); }); thead.appendChild(trHead);
          const tbody = document.createElement('tbody');
          orders.forEach(o => {
            const row = document.createElement('tr');
            const idTd = document.createElement('td'); idTd.textContent = `${o.id.substring(0,8)}...`;
            const dateTd = document.createElement('td'); dateTd.textContent = new Date(o.created_at).toLocaleDateString();
            const totalTd = document.createElement('td'); totalTd.textContent = `Rs ${(Number(o.total)||0).toLocaleString()}`;
            const statusTd = document.createElement('td'); const span = document.createElement('span'); span.className = `order-status ${o.status}`; span.textContent = o.status; statusTd.appendChild(span);
            const actionTd = document.createElement('td'); const link = document.createElement('a'); link.href = `./tracking.html?id=${encodeURIComponent(o.id)}`; link.style.color = 'var(--gold)'; link.textContent = 'Track'; actionTd.appendChild(link);
            row.appendChild(idTd); row.appendChild(dateTd); row.appendChild(totalTd); row.appendChild(statusTd); row.appendChild(actionTd);
            tbody.appendChild(row);
          });
          table.appendChild(thead); table.appendChild(tbody); ordersContent.appendChild(table);
        }
    } catch (err) {
      ordersContent.textContent = '';
      const errP = document.createElement('p'); errP.style.color = 'var(--error)'; errP.textContent = 'Failed to load orders'; ordersContent.appendChild(errP);
    }
  }

  // Load wishlist
  const wishlistContent = document.querySelector('[data-tab="wishlist"]');
  if (wishlistContent) {
    try {
      const wishlist = await api.get('/wishlist', true);
      if (wishlist.length === 0) {
        wishlistContent.textContent = '';
        const p = document.createElement('p'); p.style.textAlign = 'center'; p.style.color = 'var(--text-secondary)'; p.textContent = 'Wishlist is empty'; wishlistContent.appendChild(p);
      } else {
        wishlistContent.textContent = '';
        const grid = document.createElement('div'); grid.className = 'wishlist-grid';
        wishlist.forEach(p => {
          const item = document.createElement('div'); item.className = 'wishlist-item';
          const imgWrap = document.createElement('div'); imgWrap.className = 'wishlist-image';
          const img = document.createElement('img'); img.src = p.images?.[0] || '../images/fallback.jpg'; img.alt = p.name || ''; img.onerror = () => img.src = '../images/fallback.jpg'; imgWrap.appendChild(img);
          const info = document.createElement('div'); info.className = 'wishlist-info';
          const nameP = document.createElement('p'); nameP.className = 'wishlist-name'; nameP.textContent = p.name;
          const priceP = document.createElement('p'); priceP.className = 'wishlist-price'; priceP.textContent = `Rs ${(Number(p.price)||0).toLocaleString()}`;
          const actions = document.createElement('div'); actions.className = 'wishlist-actions';
          const viewBtn = document.createElement('button'); viewBtn.textContent = 'View'; viewBtn.addEventListener('click', () => { location.href = `./product.html?id=${encodeURIComponent(p.id)}`; });
          const remBtn = document.createElement('button'); remBtn.textContent = 'Remove'; remBtn.addEventListener('click', () => removeWishlistItem(encodeURIComponent(p.id)));
          actions.appendChild(viewBtn); actions.appendChild(remBtn);
          info.appendChild(nameP); info.appendChild(priceP); info.appendChild(actions);
          item.appendChild(imgWrap); item.appendChild(info); grid.appendChild(item);
        });
        wishlistContent.appendChild(grid);
      }
    } catch (err) {
      wishlistContent.textContent = '';
      const errP2 = document.createElement('p'); errP2.style.color = 'var(--error)'; errP2.textContent = 'Failed to load wishlist'; wishlistContent.appendChild(errP2);
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

