// === TRACKING.JS ===
async function loadTrackingData() {
  try {
    const orderId = new URLSearchParams(window.location.search).get('id');
    if (!orderId) {
      showToast('Order not found', 'error');
      return;
    }

    const order = await api.get(`/orders/${orderId}`, isLoggedIn());
    
    // Null check for order
    if (!order) {
      showToast('Order data is invalid', 'error');
      return;
    }

    // Safe: use textContent instead of innerHTML for user data
    const orderIdElement = document.querySelector('.order-id');
    if (orderIdElement) {
      orderIdElement.textContent = `Order #${sanitizeString(orderId.substring(0, 8))}...`;
    }

    // Status timeline with sanitized data
    const statuses = ['pending', 'confirmed', 'packed', 'shipped', 'delivered'];
    const timeline = document.querySelector('.status-timeline');
    
    if (timeline) {
      timeline.innerHTML = '';
      
      statuses.forEach((status, idx) => {
        const completed = statuses.indexOf(order.status) >= idx;
        const active = status === order.status;
        
        const step = document.createElement('div');
        step.className = 'timeline-step';
        
        const dot = document.createElement('div');
        dot.className = `timeline-dot ${active ? 'active' : ''} ${completed ? 'completed' : ''}`;
        dot.textContent = active ? '●' : completed ? '✓' : '◦';
        
        const content = document.createElement('div');
        content.className = 'timeline-content';
        
        const statusP = document.createElement('p');
        statusP.className = 'timeline-status';
        statusP.style.textTransform = 'capitalize';
        statusP.textContent = status;
        
        content.appendChild(statusP);
        step.appendChild(dot);
        step.appendChild(content);
        timeline.appendChild(step);
      });
    }

    // Order items with sanitized data
    const itemsContainer = document.querySelector('.order-items');
    if (itemsContainer && Array.isArray(order.items)) {
      itemsContainer.innerHTML = '';
      
      const title = document.createElement('h3');
      title.className = 'items-title';
      title.textContent = 'Items';
      itemsContainer.appendChild(title);
      
      order.items.forEach(item => {
        if (!item) return;
        
        const itemDiv = document.createElement('div');
        itemDiv.className = 'order-item';
        
        const imageDiv = document.createElement('div');
        imageDiv.className = 'item-image';
        const img = document.createElement('img');
        img.src = sanitizeUrl(item.image);
        img.alt = sanitizeString(item.name || 'Product image');
        img.onerror = () => { img.src = './images/fallback.jpg'; };
        imageDiv.appendChild(img);
        
        const detailsDiv = document.createElement('div');
        detailsDiv.className = 'item-details';
        
        const nameP = document.createElement('p');
        nameP.className = 'item-name';
        nameP.textContent = sanitizeString(item.name || 'Unknown');
        
        const optionsP = document.createElement('p');
        optionsP.className = 'item-options';
        optionsP.textContent = `${sanitizeString(item.size || 'N/A')} · ${sanitizeString(item.color || 'N/A')}`;
        
        const qtyP = document.createElement('p');
        qtyP.className = 'item-qty';
        qtyP.textContent = `Qty: ${sanitizeNumber(item.quantity)}`;
        
        detailsDiv.appendChild(nameP);
        detailsDiv.appendChild(optionsP);
        detailsDiv.appendChild(qtyP);
        
        const priceP = document.createElement('p');
        priceP.className = 'item-price';
        priceP.textContent = `Rs ${sanitizeNumber(item.price * item.quantity).toLocaleString()}`;
        
        itemDiv.appendChild(imageDiv);
        itemDiv.appendChild(detailsDiv);
        itemDiv.appendChild(priceP);
        itemsContainer.appendChild(itemDiv);
      });
    }

    // Shipping info with sanitized data
    const shippingDiv = document.querySelector('.shipping-info');
    if (shippingDiv) {
      shippingDiv.innerHTML = '';
      
      const title = document.createElement('h3');
      title.className = 'info-title';
      title.textContent = 'Shipping Address';
      
      const addr = order.shipping_address;
      if (addr) {
        const addressDiv = document.createElement('div');
        addressDiv.className = 'shipping-address';
        
        const content = [
          sanitizeString(addr.full_name || 'N/A'),
          sanitizeString(addr.phone || 'N/A'),
          sanitizeString(addr.address || 'N/A'),
          `${sanitizeString(addr.city || 'N/A')}, ${sanitizeString(addr.postal_code || 'N/A')}`
        ].join('\n');
        
        addressDiv.textContent = content;
        shippingDiv.appendChild(title);
        shippingDiv.appendChild(addressDiv);
      }
    }
  } catch (err) {
    console.error('Failed to load tracking data', err);
    // Don't expose raw backend errors to users
    showToast('Failed to load order. Please try again later.', 'error');
  }
}

// ════════════════════════════════════════════════════
// SANITIZATION FUNCTIONS
// ════════════════════════════════════════════════════
function sanitizeString(str) {
  if (typeof str !== 'string') return '';
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#x27;')
    .substring(0, 500); // Limit length
}

function sanitizeUrl(url) {
  if (typeof url !== 'string') return './images/fallback.jpg';
  // Only allow http, https, and data URLs
  if (url.startsWith('http://') || url.startsWith('https://') || url.startsWith('data:')) {
    return url;
  }
  return './images/fallback.jpg';
}

function sanitizeNumber(num) {
  const parsed = parseFloat(num);
  return isNaN(parsed) ? 0 : parsed;
}

document.addEventListener('DOMContentLoaded', loadTrackingData);
