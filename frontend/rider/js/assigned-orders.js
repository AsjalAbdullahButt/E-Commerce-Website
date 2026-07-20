    let allOrders = [];

    document.addEventListener('DOMContentLoaded', () => {
      const user = requireRole(['rider']);
      if (user) {
        loadOrders();
      }
      document.getElementById('nav-logout-btn').addEventListener('click', logout);
      document.getElementById('status-filter').addEventListener('change', filterOrders);
      document.getElementById('list-view-btn').addEventListener('click', () => setView('list'));
      document.getElementById('map-view-btn').addEventListener('click', () => setView('map'));
    });

    async function loadOrders() {
      try {
        const orders = await api.get('/rider/orders', true);
        allOrders = orders || [];
        renderOrders(allOrders);
        if (currentView === 'map') renderMapView(allOrders);
      } catch (err) {
        console.error('Failed to load orders:', err);
        showToast('Failed to load orders', 'error');
        renderEmptyStateInto(document.getElementById('orders-container'), {
          icon: 'fa-triangle-exclamation',
          title: 'Failed to load orders',
          message: 'Check your connection, then pull down or reload to try again.',
        });
      }
    }

    function filterOrders() {
      const status = document.getElementById('status-filter').value;
      const filtered = status ? allOrders.filter(o => o.status === status) : allOrders;
      renderOrders(filtered);
    }

    // Pipeline the rider cares about. status_history (already returned by GET /rider/orders,
    // per backend/schemas/order.py) supplies the timestamp for each step that's been reached.
    const STATUS_PIPELINE = ['confirmed', 'packed', 'shipped', 'delivered'];

    // Same four-modifier badge scheme as the admin pages (shared/css/global.css).
    const STATUS_BADGE = { delivered: 'success', shipped: 'warning', cancelled: 'danger', returned: 'warning' };
    function statusBadgeClass(status) {
      return `status-badge status-badge--${STATUS_BADGE[status] || 'neutral'}`;
    }

    function buildStatusTimeline(order) {
      const timeline = document.createElement('div'); timeline.className = 'status-timeline';
      const currentIdx = STATUS_PIPELINE.indexOf(order.status);
      const history = Array.isArray(order.status_history) ? order.status_history : [];
      const isTerminalBad = order.status === 'cancelled' || order.status === 'returned';

      STATUS_PIPELINE.forEach((status, idx) => {
        const step = document.createElement('div'); step.className = 'tl-step';
        if (isTerminalBad) {
          step.classList.add(idx === 0 ? 'cancelled' : '');
        } else if (idx < currentIdx) {
          step.classList.add('done');
        } else if (idx === currentIdx) {
          step.classList.add('current');
        }

        const line = document.createElement('div'); line.className = 'tl-line';
        const lineFill = document.createElement('div'); lineFill.className = 'tl-line-fill';
        if (idx < currentIdx) lineFill.style.width = '100%';
        line.appendChild(lineFill);

        const dot = document.createElement('span'); dot.className = 'tl-dot';
        const icon = document.createElement('i');
        icon.className = idx < currentIdx ? 'fas fa-check' : 'fas fa-circle-dot';
        dot.appendChild(icon);

        const label = document.createElement('span'); label.className = 'tl-label'; label.textContent = formatStatus(status);

        const entry = history.find(h => h.status === status);
        step.appendChild(line);
        step.appendChild(dot);
        step.appendChild(label);
        if (entry?.timestamp) {
          const time = document.createElement('span'); time.className = 'tl-time';
          try { time.textContent = new Date(entry.timestamp).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }); } catch { /* skip */ }
          step.appendChild(time);
        }
        timeline.appendChild(step);
      });

      return timeline;
    }

    function renderOrders(orders) {
      const container = document.getElementById('orders-container');
      container.textContent = '';

      if (!orders || orders.length === 0) {
        renderEmptyStateInto(container, {
          icon: 'fa-box',
          title: 'No orders to display',
          message: 'Deliveries assigned to you will appear here.',
        });
        return;
      }

      const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

      orders.forEach((order, idx) => {
        const card = document.createElement('div'); card.className = 'order-card'; card.dataset.orderId = order.id;

        const header = document.createElement('div'); header.className = 'order-header';
        const left = document.createElement('div');
        const idDiv = document.createElement('div'); idDiv.className = 'order-id'; idDiv.textContent = `Order #${(order.id && order.id.substring) ? order.id.substring(0,8) : 'N/A'}`;
        const dateP = document.createElement('p'); dateP.style.color = 'var(--text-secondary)'; dateP.style.fontSize = '0.85rem'; dateP.style.marginTop = '0.25rem'; dateP.textContent = new Date(order.created_at).toLocaleDateString();
        left.appendChild(idDiv); left.appendChild(dateP);

        const statusSpan = document.createElement('span'); statusSpan.className = statusBadgeClass(order.status);
        const statusIcon = document.createElement('i'); statusIcon.className = 'fas fa-circle-dot';
        const statusText = document.createTextNode(' ' + formatStatus(order.status));
        statusSpan.appendChild(statusIcon); statusSpan.appendChild(statusText);

        header.appendChild(left); header.appendChild(statusSpan);

        card.appendChild(header);
        card.appendChild(buildStatusTimeline(order));

        const details = document.createElement('div'); details.className = 'order-details';
        const addrGroup = document.createElement('div'); addrGroup.className = 'detail-group';
        const addrLabel = document.createElement('span'); addrLabel.className = 'detail-label'; addrLabel.textContent = 'Delivery Address';
        const addr = order.shipping_address;
        const addrValue = document.createElement('span'); addrValue.className = 'detail-value';
        addrValue.textContent = addr ? `${addr.address}, ${addr.city} ${addr.postal_code}` : 'N/A';
        addrGroup.appendChild(addrLabel); addrGroup.appendChild(addrValue);

        const countGroup = document.createElement('div'); countGroup.className = 'detail-group';
        const countLabel = document.createElement('span'); countLabel.className = 'detail-label'; countLabel.textContent = 'Items Count';
        const countValue = document.createElement('span'); countValue.className = 'detail-value'; const strong = document.createElement('strong'); strong.textContent = String(order.items?.length || 0); countValue.appendChild(strong); countValue.appendChild(document.createTextNode(' item(s)'));
        countGroup.appendChild(countLabel); countGroup.appendChild(countValue);

        details.appendChild(addrGroup); details.appendChild(countGroup);

        const itemsList = document.createElement('div'); itemsList.className = 'items-list';
        const itemsTitle = document.createElement('strong'); itemsTitle.style.display = 'block'; itemsTitle.style.marginBottom = '0.5rem'; itemsTitle.style.color = 'var(--text-secondary)'; itemsTitle.textContent = 'Items:';
        itemsList.appendChild(itemsTitle);
        (order.items || []).forEach(item => {
          const itemDiv = document.createElement('div'); itemDiv.className = 'item';
          itemDiv.textContent = `${item.name} x${item.quantity} - Rs ${item.price}`;
          itemsList.appendChild(itemDiv);
        });

        // Backend only allows a rider to set 'shipped' (from confirmed/packed) or 'delivered'
        // (from shipped) — see backend/utils/order_transitions.py.
        const controls = document.createElement('div'); controls.className = 'status-controls';
        const shipBtn = document.createElement('button');
        shipBtn.className = `btn-status ${order.status === 'shipped' ? 'active' : ''}`;
        shipBtn.textContent = 'Mark Shipped';
        shipBtn.disabled = !['confirmed', 'packed'].includes(order.status);
        shipBtn.addEventListener('click', () => updateStatus(order.id, 'shipped'));

        const delBtn = document.createElement('button');
        delBtn.className = `btn-status ${order.status === 'delivered' ? 'active' : ''}`;
        delBtn.textContent = 'Mark Delivered';
        delBtn.disabled = order.status !== 'shipped';
        delBtn.addEventListener('click', () => openProofOfDeliveryModal(order.id));

        controls.appendChild(shipBtn); controls.appendChild(delBtn);

        card.appendChild(details); card.appendChild(itemsList); card.appendChild(controls);

        if (!reduced) {
          card.style.opacity = '0';
          card.style.transform = 'translateY(14px)';
        }
        container.appendChild(card);
      });

      if (!reduced) {
        requestAnimationFrame(() => {
          Array.from(container.children).forEach((card, idx) => {
            card.style.transition = `opacity var(--duration-slow) var(--ease) ${idx * 50}ms, transform var(--duration-slow) var(--ease) ${idx * 50}ms`;
            card.style.opacity = '1';
            card.style.transform = 'none';
          });
        });
      }
    }

    function formatStatus(status) {
      const map = {
        confirmed: 'Confirmed',
        packed: 'Packed',
        shipped: 'Shipped',
        delivered: 'Delivered',
      };
      return map[status] || status || 'Unknown';
    }

    async function updateStatus(orderId, newStatus) {
      const card = document.querySelector(`.order-card[data-order-id="${CSS.escape(orderId)}"]`);
      card?.classList.add('status-updating');
      try {
        await api.patch(`/rider/orders/${orderId}/status`, { status: newStatus }, true);
        showToast('Status updated successfully', 'success');
        closeMapSheet();
        loadOrders();
      } catch (err) {
        console.error('Failed to update status:', err);
        showToast('Failed to update status', 'error');
        card?.classList.remove('status-updating');
      }
    }

    // === MAP VIEW ===
    // No lat/lng is stored anywhere in this app (db/order.py only has address/city/postal_code
    // text fields) and there's no route-optimization requirement, so geocoding happens client-side
    // against OpenStreetMap's free Nominatim API, one address string at a time, with results cached
    // in localStorage indefinitely (an address's coordinates don't change) to stay well under
    // Nominatim's 1 req/sec public-usage-policy limit even on repeat visits.
    const GEOCODE_CACHE_KEY = 'rider_geocode_cache_v1';
    let leafletMap = null;
    let mapMarkersLayer = null;
    let currentView = 'list';

    function loadGeocodeCache() {
      try { return JSON.parse(localStorage.getItem(GEOCODE_CACHE_KEY)) || {}; }
      catch { return {}; }
    }

    function saveGeocodeCache(cache) {
      try { localStorage.setItem(GEOCODE_CACHE_KEY, JSON.stringify(cache)); } catch { /* storage full/unavailable, skip */ }
    }

    function sleep(ms) { return new Promise((resolve) => setTimeout(resolve, ms)); }

    async function geocodeAddress(addr) {
      const query = `${addr.address}, ${addr.city}, ${addr.postal_code}, Pakistan`;
      const cache = loadGeocodeCache();
      if (cache[query]) return cache[query];

      const url = `https://nominatim.openstreetmap.org/search?format=json&limit=1&q=${encodeURIComponent(query)}`;
      const resp = await fetch(url, { headers: { Accept: 'application/json' } });
      if (!resp.ok) return null;
      const results = await resp.json();
      if (!results.length) return null;

      const coords = { lat: parseFloat(results[0].lat), lon: parseFloat(results[0].lon) };
      cache[query] = coords;
      saveGeocodeCache(cache);
      return coords;
    }

    function setView(view) {
      currentView = view;
      document.getElementById('list-view-btn').classList.toggle('active', view === 'list');
      document.getElementById('map-view-btn').classList.toggle('active', view === 'map');
      document.getElementById('orders-container').classList.toggle('hidden', view === 'map');
      document.getElementById('map-view').classList.toggle('visible', view === 'map');
      if (view !== 'map') closeMapSheet();

      if (view === 'map') {
        renderMapView(allOrders);
      }
    }

    // === MAP BOTTOM SHEET ===
    // Top map / bottom sheet layout: marker tap opens a fixed, thumb-reachable panel with the
    // delivery details and full-size action buttons ("Mark Delivered" still goes through the
    // proof-of-delivery photo modal, so completion stays an unmistakable two-step action).
    function openMapSheet(order) {
      const sheet = document.getElementById('map-bottom-sheet');
      sheet.textContent = '';

      const handle = document.createElement('div'); handle.className = 'map-sheet-handle';

      const header = document.createElement('div'); header.className = 'map-sheet-header';
      const idEl = document.createElement('strong'); idEl.className = 'order-id';
      idEl.textContent = `Order #${(order.id && order.id.substring) ? order.id.substring(0, 8) : 'N/A'}`;
      const statusEl = document.createElement('span'); statusEl.className = statusBadgeClass(order.status);
      statusEl.textContent = formatStatus(order.status);
      header.appendChild(idEl); header.appendChild(statusEl);

      const addr = order.shipping_address;
      const addrEl = document.createElement('p'); addrEl.className = 'map-sheet-addr';
      addrEl.textContent = addr ? `${addr.address}, ${addr.city} ${addr.postal_code}` : 'No address on record';

      const itemsEl = document.createElement('p'); itemsEl.className = 'map-sheet-items';
      itemsEl.textContent = `${order.items?.length || 0} item(s)`;

      const actions = document.createElement('div'); actions.className = 'map-sheet-actions';
      const shipBtn = document.createElement('button'); shipBtn.className = 'btn-status'; shipBtn.type = 'button';
      shipBtn.textContent = 'Mark Shipped';
      shipBtn.disabled = !['confirmed', 'packed'].includes(order.status);
      shipBtn.addEventListener('click', () => updateStatus(order.id, 'shipped'));
      const delBtn = document.createElement('button'); delBtn.className = 'btn-status'; delBtn.type = 'button';
      delBtn.textContent = 'Mark Delivered';
      delBtn.disabled = order.status !== 'shipped';
      delBtn.addEventListener('click', () => openProofOfDeliveryModal(order.id));
      actions.appendChild(shipBtn); actions.appendChild(delBtn);

      sheet.appendChild(handle); sheet.appendChild(header); sheet.appendChild(addrEl);
      sheet.appendChild(itemsEl); sheet.appendChild(actions);
      sheet.hidden = false;

      handle.addEventListener('click', closeMapSheet);
    }

    function closeMapSheet() {
      const sheet = document.getElementById('map-bottom-sheet');
      sheet.hidden = true;
      sheet.textContent = '';
    }

    async function renderMapView(orders) {
      if (!leafletMap) {
        leafletMap = L.map('map-view').setView([30.3753, 69.3451], 5); // Pakistan-centered default
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
          attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
          maxZoom: 19,
        }).addTo(leafletMap);
        mapMarkersLayer = L.layerGroup().addTo(leafletMap);
      }
      mapMarkersLayer.clearLayers();

      const deliverable = (orders || []).filter(o => o.shipping_address);
      if (!deliverable.length) return;

      const note = document.getElementById('map-geocoding-note');
      const noteText = document.getElementById('map-geocoding-text');
      note.classList.add('visible');

      const bounds = [];
      let done = 0;
      for (const order of deliverable) {
        noteText.textContent = `Locating addresses... (${done + 1}/${deliverable.length})`;
        let coords = null;
        try { coords = await geocodeAddress(order.shipping_address); }
        catch (err) { console.error('Geocoding failed for order', order.id, err); }
        done += 1;

        if (coords) {
          const marker = L.marker([coords.lat, coords.lon]).addTo(mapMarkersLayer);
          marker.bindPopup(buildMapPopupHtml(order));
          marker.on('click', () => openMapSheet(order));
          bounds.push([coords.lat, coords.lon]);
        }

        // Nominatim's usage policy caps public, unauthenticated use at ~1 request/second.
        if (done < deliverable.length) await sleep(1000);
      }

      note.classList.remove('visible');
      if (bounds.length) leafletMap.fitBounds(bounds, { padding: [40, 40], maxZoom: 14 });
      setTimeout(() => leafletMap.invalidateSize(), 100);
    }

    // Popup is informational only — actions live in the bottom sheet (openMapSheet), which
    // opens on the same marker tap.
    function buildMapPopupHtml(order) {
      const addr = order.shipping_address;
      const shortId = (order.id && order.id.substring) ? order.id.substring(0, 8) : 'N/A';
      const wrap = document.createElement('div'); wrap.className = 'map-popup';

      const idEl = document.createElement('strong'); idEl.className = 'order-id'; idEl.textContent = `Order #${shortId}`;
      const statusEl = document.createElement('span'); statusEl.className = statusBadgeClass(order.status); statusEl.textContent = formatStatus(order.status);
      const addrEl = document.createElement('span'); addrEl.className = 'popup-addr'; addrEl.textContent = `${addr.address}, ${addr.city} ${addr.postal_code}`;

      wrap.appendChild(idEl); wrap.appendChild(document.createElement('br'));
      wrap.appendChild(statusEl); wrap.appendChild(addrEl);
      return wrap;
    }

    // === PROOF OF DELIVERY ===
    let podOrderId = null;
    let podFile = null;

    function openProofOfDeliveryModal(orderId) {
      podOrderId = orderId;
      podFile = null;
      document.getElementById('pod-file-input').value = '';
      const preview = document.getElementById('pod-preview');
      preview.src = '';
      preview.classList.remove('visible');
      document.getElementById('pod-submit-btn').disabled = true;
      document.getElementById('pod-modal-overlay').classList.add('visible');
    }

    function closeProofOfDeliveryModal() {
      document.getElementById('pod-modal-overlay').classList.remove('visible');
      podOrderId = null;
      podFile = null;
    }

    async function submitProofOfDelivery() {
      if (!podOrderId || !podFile) return;
      const submitBtn = document.getElementById('pod-submit-btn');
      submitBtn.disabled = true;
      submitBtn.textContent = 'Submitting...';

      try {
        const token = getAccessToken();
        const formData = new FormData();
        formData.append('proof_photo', podFile);

        const res = await fetch(`${API_BASE}/rider/orders/${podOrderId}/complete`, {
          method: 'POST',
          credentials: 'include',
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          body: formData,
        });

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          throw new Error(errData.detail || `Request failed with status ${res.status}`);
        }

        showToast('Delivery confirmed', 'success');
        closeProofOfDeliveryModal();
        closeMapSheet();
        loadOrders();
        if (currentView === 'map' && leafletMap) leafletMap.closePopup();
      } catch (err) {
        console.error('Failed to submit proof of delivery:', err);
        showToast(err.message || 'Failed to confirm delivery', 'error');
      } finally {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Confirm Delivered';
      }
    }

    document.getElementById('pod-file-input').addEventListener('change', (e) => {
      const file = e.target.files[0];
      const preview = document.getElementById('pod-preview');
      const submitBtn = document.getElementById('pod-submit-btn');
      if (!file) {
        podFile = null;
        preview.classList.remove('visible');
        submitBtn.disabled = true;
        return;
      }
      podFile = file;
      preview.src = URL.createObjectURL(file);
      preview.classList.add('visible');
      submitBtn.disabled = false;
    });

    document.getElementById('pod-cancel-btn').addEventListener('click', closeProofOfDeliveryModal);
    document.getElementById('pod-submit-btn').addEventListener('click', submitProofOfDelivery);
    document.getElementById('pod-modal-overlay').addEventListener('click', (e) => {
      if (e.target.id === 'pod-modal-overlay') closeProofOfDeliveryModal();
    });
