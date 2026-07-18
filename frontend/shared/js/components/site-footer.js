// <site-footer variant="full|minimal" text="E-Commerce Admin Panel." customer-base="." auth-base="../auth">
//
// "full" is the 5-column footer used on every customer/auth page; "minimal" is the bare
// copyright bar used on admin/rider pages (text after "&copy; 2025 " differs between the two —
// "E-Commerce. All rights reserved." on rider, "E-Commerce Admin Panel." on admin — hence the
// free-text attribute rather than a fixed suffix). Renders into light DOM like <site-header> —
// nothing here is looked up by id/getElementById elsewhere, but light DOM keeps the pattern
// consistent and lets global.css style it without :host/::part plumbing.
class SiteFooter extends HTMLElement {
  connectedCallback() {
    const variant = this.getAttribute('variant') || 'full';

    if (variant === 'minimal') {
      const text = this.getAttribute('text') || 'E-Commerce. All rights reserved.';
      this.innerHTML = `
        <footer class="footer">
          <div class="footer-bottom"><p>&copy; 2025 ${text}</p></div>
        </footer>`;
      return;
    }

    const customerBase = this.getAttribute('customer-base') || '.';
    const authBase = this.getAttribute('auth-base') || '../auth';

    this.innerHTML = `
      <footer class="footer">
        <div class="footer-inner">
          <div class="footer-brand">
            <p class="footer-logo"><span class="logo-e">E</span><span class="logo-dash">-</span><span class="logo-com">COM</span></p>
            <p>Your one-stop shop for everything. Quality products, fast delivery.</p>
          </div>
          <div class="footer-col">
            <h4>Shop</h4>
            <a href="${customerBase}/shop.html">All Products</a>
            <a href="${customerBase}/about.html">Our Story</a>
            <a href="${customerBase}/contact.html">Contact Us</a>
          </div>
          <div class="footer-col">
            <h4>Account</h4>
            <a href="${authBase}/login.html">Login</a>
            <a href="${authBase}/register.html">Register</a>
            <a href="${customerBase}/profile.html">My Orders</a>
            <a href="${customerBase}/tracking.html">Track Order</a>
          </div>
          <div class="footer-col">
            <h4>Legal</h4>
            <a href="${customerBase}/privacy-policy.html">Privacy Policy</a>
            <a href="${customerBase}/terms.html">Terms of Service</a>
            <a href="${customerBase}/refund-policy.html">Refund Policy</a>
          </div>
          <div class="footer-col">
            <h4>Follow Us</h4>
            <div class="footer-socials">
              <a href="#" aria-label="Instagram"><i class="fab fa-instagram"></i></a>
              <a href="#" aria-label="Facebook"><i class="fab fa-facebook-f"></i></a>
              <a href="#" aria-label="TikTok"><i class="fab fa-tiktok"></i></a>
            </div>
          </div>
        </div>
        <div class="footer-bottom"><p>&copy; 2025 E-Commerce. All rights reserved.</p></div>
      </footer>`;
  }
}

customElements.define('site-footer', SiteFooter);
