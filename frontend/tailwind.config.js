/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './**/*.html',
    './shared/js/components/**/*.js',
  ],
  // The hand-rolled design system in shared/css/global.css already resets and themes the page
  // (dark by default, [data-theme="light"] override) — Tailwind's preflight would fight that,
  // so utilities are additive only.
  corePlugins: { preflight: false },
  // Existing pages already use plain class names that collide with real Tailwind utilities
  // (container, flex, hidden, grid, ...) for their own hand-rolled CSS — e.g. admin/products.html
  // toggles a modal via classList.add('hidden') against a custom .hidden rule in admin.css.
  // Prefixing every generated utility avoids silently overriding those on pages that haven't
  // adopted Tailwind yet.
  prefix: 'tw-',
  theme: {
    extend: {
      // Same CSS custom properties global.css already swaps per-theme, so any of these
      // utilities (e.g. bg-surface, text-primary) repaint correctly in both themes for free —
      // no dark: variant needed.
      colors: {
        base: 'var(--bg-base)',
        surface: 'var(--bg-surface)',
        card: 'var(--bg-card)',
        'card-hover': 'var(--bg-card-hover)',
        input: 'var(--bg-input)',
        gold: 'var(--gold)',
        'gold-dim': 'var(--gold-dim)',
        'gold-hover': 'var(--gold-hover)',
        'gold-bright': 'var(--gold-bright)',
        primary: 'var(--text-primary)',
        secondary: 'var(--text-secondary)',
        muted: 'var(--text-muted)',
        success: 'var(--success)',
        danger: 'var(--error)',
        warning: 'var(--warning)',
        info: 'var(--info)',
      },
      fontFamily: {
        display: 'var(--font-display)',
        body: 'var(--font-body)',
        mono: 'var(--font-mono)',
      },
      borderRadius: {
        sm: 'var(--radius-sm)',
        md: 'var(--radius-md)',
        lg: 'var(--radius-lg)',
        pill: 'var(--radius-pill)',
      },
      boxShadow: {
        sm: 'var(--shadow-sm)',
        md: 'var(--shadow-md)',
        lg: 'var(--shadow-lg)',
        xl: 'var(--shadow-xl)',
        gold: 'var(--shadow-gold)',
      },
      transitionTimingFunction: {
        DEFAULT: 'var(--ease)',
      },
    },
  },
  plugins: [],
};
