// Minimal HTML-escaping helpers
function escapeHtml(s){
  if (s === null || s === undefined) return '';
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function safeText(node, text){
  if(!node) return;
  node.textContent = text == null ? '' : String(text);
}

// Expose as globals for non-module pages
window.escapeHtml = escapeHtml;
window.safeText = safeText;
