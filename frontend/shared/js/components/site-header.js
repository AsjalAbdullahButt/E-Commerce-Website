// <site-header variant="shop|auth-form|minimal|staff"
//              links='[{"href":"./index.html","label":"Home","active":true}]'
//              logo-href="./index.html" profile-href="./profile.html" login-href="../auth/login.html">
//
// Variants (the four header shapes that existed, duplicated, across every page pre-refactor):
//   shop      — customer pages: nav links + profile/login/logout + cart + theme
//   auth-form — login/register: nav links + cart + theme, no account icons (you're not in one yet)
//   minimal   — forgot/reset-password: logo + theme only, no links, no actions
//   staff     — admin/rider pages: nav links + logout + theme, no cart/profile
//
// Renders into light DOM (no shadow root) on purpose: shared/js/auth.js, cart.js and the
// inline theme-toggle bootstrap in auth.js all look up nav-logout-btn / nav-profile-btn /
// cart-toggle / theme-toggle / theme-icon via plain document.getElementById(...), so the ids
// have to stay globally addressable exactly like the markup this replaces. This file must load
// (as a plain, non-deferred <script>) before the parser reaches the <site-header> tag so the
// element upgrades — and its innerHTML is set — before those scripts' DOMContentLoaded handlers
// run later in the page.
class SiteHeader extends HTMLElement {
  connectedCallback() {
    const variant = this.getAttribute('variant') || 'shop';
    const logoHref = this.getAttribute('logo-href') || './index.html';
    let links = [];
    try {
      links = JSON.parse(this.getAttribute('links') || '[]');
    } catch {
      links = [];
    }

    const linksHtml = links.length
      ? `<ul class="nav-links" id="nav-links">${links
          .map((l) => `<li><a href="${l.href}"${l.active ? ' class="active"' : ''}>${l.label}</a></li>`)
          .join('')}</ul>`
      : '';

    const themeToggle = `
      <button class="nav-icon theme-toggle" id="theme-toggle" aria-label="Toggle theme" title="Switch theme">
        <i class="fas fa-moon" id="theme-icon"></i>
      </button>`;

    const logoutBtn = `
      <button class="nav-icon" id="nav-logout-btn" aria-label="Logout"><i class="fas fa-sign-out-alt"></i></button>`;

    const cartBtn = `
      <button class="nav-icon cart-icon-btn" id="cart-toggle" aria-label="Cart">
        <i class="fas fa-shopping-bag"></i>
        <span class="cart-badge" id="cart-badge">0</span>
      </button>`;

    const cartMarkup = `
      <div class="cart-overlay" id="cart-overlay"></div>
      <aside class="cart-drawer" id="cart-drawer" role="dialog" aria-modal="true" aria-label="Shopping cart" aria-hidden="true"></aside>`;

    let actionsHtml;
    let extraHtml = '';
    switch (variant) {
      case 'shop': {
        const profileHref = this.getAttribute('profile-href') || './profile.html';
        const loginHref = this.getAttribute('login-href') || '../auth/login.html';
        actionsHtml = `
          <a href="${profileHref}" class="nav-icon" id="nav-profile-btn" aria-label="Profile"><i class="fas fa-user"></i></a>
          <a href="${loginHref}" class="nav-icon" id="nav-login-btn" aria-label="Login"><i class="fas fa-sign-in-alt"></i></a>
          ${logoutBtn}${cartBtn}${themeToggle}`;
        extraHtml = cartMarkup;
        break;
      }
      case 'auth-form':
        actionsHtml = `${cartBtn}${themeToggle}`;
        extraHtml = cartMarkup;
        break;
      case 'staff':
        actionsHtml = `${logoutBtn}${themeToggle}`;
        break;
      case 'minimal':
      default:
        actionsHtml = themeToggle;
        break;
    }

    this.innerHTML = `
      <nav class="navbar" id="navbar" aria-label="Main navigation">
        <div class="nav-inner">
          <a class="nav-logo" href="${logoHref}"><span class="logo-e">E</span><span class="logo-dash">-</span><span class="logo-com">COM</span></a>
          ${linksHtml}
          <div class="nav-actions">${actionsHtml}</div>
        </div>
      </nav>
      ${extraHtml}`;
  }
}

customElements.define('site-header', SiteHeader);
