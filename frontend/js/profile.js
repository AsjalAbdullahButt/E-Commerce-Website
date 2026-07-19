// === PROFILE.JS ===
document.addEventListener('DOMContentLoaded', async () => {
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
  // .tab-content prefix matters: the tab BUTTONS carry the same data-tab attribute and come
  // first in the DOM, so an unscoped [data-tab=...] query grabs a button instead.
  const profileContent = document.querySelector('.tab-content[data-tab="profile"]');
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
  const ordersContent = document.querySelector('.tab-content[data-tab="orders"]');
  if (ordersContent) {
    try {
      const ordersResponse = await api.get('/orders/me', true);
      const orders = ordersResponse.data || [];
        if (orders.length === 0) {
          renderEmptyStateInto(ordersContent, {
            icon: 'fa-receipt',
            title: 'No orders yet',
            message: 'Your orders will appear here after your first purchase.',
          });
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
      renderEmptyStateInto(ordersContent, {
        icon: 'fa-triangle-exclamation',
        title: 'Failed to load orders',
        message: 'Reload the page to try again.',
      });
    }
  }

  // Load wishlist
  const wishlistContent = document.querySelector('.tab-content[data-tab="wishlist"]');
  if (wishlistContent) {
    try {
      const wishlist = await api.get('/wishlist', true);
      if (wishlist.length === 0) {
        renderEmptyStateInto(wishlistContent, {
          icon: 'fa-heart',
          title: 'Wishlist is empty',
          message: 'Tap the heart on any product to save it here.',
        });
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
      renderEmptyStateInto(wishlistContent, {
        icon: 'fa-triangle-exclamation',
        title: 'Failed to load wishlist',
        message: 'Reload the page to try again.',
      });
    }
  }

  loadAddresses();
});

// ════════════════════════════════════════════════════
// SAVED ADDRESSES
// ════════════════════════════════════════════════════
async function loadAddresses() {
  const content = document.querySelector('.tab-content[data-tab="addresses"]');
  if (!content) return;
  content.textContent = '';

  let addresses = [];
  try {
    addresses = await api.get('/addresses', true);
  } catch (err) {
    renderEmptyStateInto(content, {
      icon: 'fa-triangle-exclamation',
      title: 'Failed to load addresses',
      message: 'Reload the page to try again.',
    });
    return;
  }

  const wrap = document.createElement('div'); wrap.className = 'addresses-wrap';

  if (addresses.length === 0) {
    renderEmptyStateInto(wrap, {
      icon: 'fa-location-dot',
      title: 'No saved addresses yet',
      message: 'Addresses you save at checkout will appear here.',
    });
  } else {
    const grid = document.createElement('div'); grid.className = 'addresses-grid';
    addresses.forEach(addr => grid.appendChild(renderAddressCard(addr)));
    wrap.appendChild(grid);
  }

  const addBtn = document.createElement('button');
  addBtn.className = 'edit-profile-btn';
  addBtn.textContent = '+ Add Address';
  addBtn.addEventListener('click', () => showAddressForm(null));
  wrap.appendChild(addBtn);

  const formHost = document.createElement('div');
  formHost.id = 'address-form-host';
  wrap.appendChild(formHost);

  content.appendChild(wrap);
}

function renderAddressCard(addr) {
  const card = document.createElement('div'); card.className = 'address-card';
  if (addr.is_default) card.classList.add('is-default');

  const header = document.createElement('div'); header.className = 'address-card-header';
  const labelSpan = document.createElement('strong'); labelSpan.textContent = addr.label || 'Address';
  header.appendChild(labelSpan);
  if (addr.is_default) {
    const badge = document.createElement('span'); badge.className = 'default-badge'; badge.textContent = 'Default';
    header.appendChild(badge);
  }
  card.appendChild(header);

  const body = document.createElement('p'); body.className = 'address-card-body';
  safeText(body, `${addr.full_name}\n${addr.phone}\n${addr.address}, ${addr.city} ${addr.postal_code}`);
  card.appendChild(body);

  const actions = document.createElement('div'); actions.className = 'address-card-actions';
  if (!addr.is_default) {
    const defaultBtn = document.createElement('button'); defaultBtn.className = 'save-btn'; defaultBtn.textContent = 'Set Default';
    defaultBtn.addEventListener('click', async () => {
      try {
        await api.post(`/addresses/${addr.id}/default`, {}, true);
        loadAddresses();
      } catch (err) {
        showToast('Failed to set default address', 'error');
      }
    });
    actions.appendChild(defaultBtn);
  }
  const editBtn = document.createElement('button'); editBtn.className = 'save-btn'; editBtn.textContent = 'Edit';
  editBtn.addEventListener('click', () => showAddressForm(addr));
  actions.appendChild(editBtn);
  const deleteBtn = document.createElement('button'); deleteBtn.className = 'cancel-btn'; deleteBtn.textContent = 'Delete';
  deleteBtn.addEventListener('click', async () => {
    if (!window.confirm('Delete this address?')) return;
    try {
      await api.delete(`/addresses/${addr.id}`, true);
      loadAddresses();
    } catch (err) {
      showToast('Failed to delete address', 'error');
    }
  });
  actions.appendChild(deleteBtn);
  card.appendChild(actions);

  return card;
}

function showAddressForm(addr) {
  const host = document.getElementById('address-form-host');
  if (!host) return;
  host.textContent = '';

  const form = document.createElement('div'); form.className = 'edit-form full';

  const makeField = (labelText, id, value, type = 'text') => {
    const group = document.createElement('div'); group.className = 'form-group';
    const label = document.createElement('label'); label.textContent = labelText;
    const input = document.createElement('input'); input.type = type; input.id = id; input.value = value || '';
    group.appendChild(label); group.appendChild(input);
    return group;
  };

  form.appendChild(makeField('Label (e.g. Home, Work)', 'addr-label', addr?.label));
  form.appendChild(makeField('Full Name', 'addr-fullName', addr?.full_name));
  form.appendChild(makeField('Phone', 'addr-phone', addr?.phone, 'tel'));
  form.appendChild(makeField('Address', 'addr-address', addr?.address));
  form.appendChild(makeField('City', 'addr-city', addr?.city));
  form.appendChild(makeField('Postal Code', 'addr-postal', addr?.postal_code));

  const defaultGroup = document.createElement('div'); defaultGroup.className = 'form-group';
  const defaultLabel = document.createElement('label');
  const defaultCheckbox = document.createElement('input'); defaultCheckbox.type = 'checkbox'; defaultCheckbox.id = 'addr-isDefault';
  defaultCheckbox.checked = Boolean(addr?.is_default);
  defaultCheckbox.style.width = 'auto'; defaultCheckbox.style.marginRight = '0.5rem';
  defaultLabel.appendChild(defaultCheckbox);
  defaultLabel.appendChild(document.createTextNode('Set as default address'));
  defaultGroup.appendChild(defaultLabel);
  form.appendChild(defaultGroup);

  const actionsDiv = document.createElement('div'); actionsDiv.className = 'form-actions';
  const saveBtn = document.createElement('button'); saveBtn.className = 'save-btn'; saveBtn.textContent = 'Save Address';
  saveBtn.addEventListener('click', () => saveAddress(addr?.id));
  const cancelBtn = document.createElement('button'); cancelBtn.className = 'cancel-btn'; cancelBtn.textContent = 'Cancel';
  cancelBtn.addEventListener('click', () => { host.textContent = ''; });
  actionsDiv.appendChild(saveBtn); actionsDiv.appendChild(cancelBtn);
  form.appendChild(actionsDiv);

  host.appendChild(form);
}

async function saveAddress(existingId) {
  const payload = {
    label: document.getElementById('addr-label').value.trim() || null,
    full_name: document.getElementById('addr-fullName').value.trim(),
    phone: document.getElementById('addr-phone').value.trim(),
    address: document.getElementById('addr-address').value.trim(),
    city: document.getElementById('addr-city').value.trim(),
    postal_code: document.getElementById('addr-postal').value.trim(),
    is_default: document.getElementById('addr-isDefault').checked,
  };

  if (!payload.full_name || !payload.phone || !payload.address || !payload.city) {
    showToast('Please fill all required address fields', 'warning');
    return;
  }

  try {
    if (existingId) {
      await api.put(`/addresses/${existingId}`, payload, true);
    } else {
      await api.post('/addresses', payload, true);
    }
    showToast('Address saved');
    loadAddresses();
  } catch (err) {
    showToast(err.message || 'Failed to save address', 'error');
  }
}

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

