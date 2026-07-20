# Security Policy

## Supported Versions

This is a single-branch project — security fixes land on `main` only. There are no maintained
release branches to backport to.

## Reporting a Vulnerability

**Please do not open a public GitHub issue for security vulnerabilities.**

Instead, report it privately via the contact listed in
[`frontend/.well-known/security.txt`](frontend/.well-known/security.txt) (RFC 9116). Replace the
placeholder address there with a real one before relying on this in production.

When reporting, please include:

- A description of the vulnerability and its potential impact.
- Steps to reproduce it (a minimal request/payload is ideal).
- The commit hash or version you tested against.

### What to expect

- **Acknowledgement**: within 3 business days.
- **Triage**: we'll confirm whether it's a genuine vulnerability and its severity within 7 days.
- **Fix timeline**: depends on severity — critical issues (auth bypass, remote code execution,
  payment/order integrity) are prioritized over lower-severity findings (missing headers,
  information disclosure with no direct exploit path).
- **Disclosure**: we ask for 90 days (or until a fix ships, whichever is sooner) before any
  public disclosure, so users have time to update.

## Scope

In scope:

- The FastAPI backend (`backend/`) — auth, payments, order/inventory logic, admin/rider APIs.
- The frontend (`frontend/`) — XSS, CSRF, insecure data handling.
- Configuration and deployment files (`Dockerfile`, `docker-compose*.yml`, CI workflows) if they
  would lead to a real misconfiguration in a standard deployment.

Out of scope:

- Findings that require an already-compromised admin/database credential.
- Missing rate limits on endpoints that aren't security-sensitive (contact this way instead of
  filing a report if you're unsure).
- Third-party services this app integrates with (Stripe, JazzCash, EasyPaisa, SendGrid,
  Google) — report those to the respective vendor.
- The placeholder legal pages (privacy policy, terms, refund policy) — those are explicitly
  marked as unreviewed sample content, not a security concern.

## Known Design Decisions (not vulnerabilities)

A few things that come up in automated scans but are intentional — see the referenced code for
the full reasoning:

- Every third-party integration (Stripe/JazzCash/EasyPaisa/SendGrid/S3/Google OAuth) defaults to
  **disabled**, and fails fast on boot if enabled with a placeholder credential
  (`backend/config/settings.py::_require_configured`).
- `utils/cache.py` and `utils/limiter.py` are process-local (no Redis backend) — the app refuses
  to boot with `WEB_CONCURRENCY > 1` in production rather than silently degrading. See
  `main.py::check_single_worker_deployment` and the README's "Deployment" section.
- CORS allows exactly the origins in `ALLOWED_ORIGINS` (comma-separated) — there is no
  wildcard `*` origin anywhere.
