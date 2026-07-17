"""Plain-HTML email bodies — no template engine dependency (matches the rest of this codebase,
which builds every other response shape as plain dicts/f-strings rather than pulling in Jinja2).
Each function returns (subject, html_body) for services.email.EmailService.send().
"""
from typing import Iterable

_WRAPPER = """
<div style="font-family:Arial,Helvetica,sans-serif;max-width:560px;margin:0 auto;color:#1a1a1a;">
  <h2 style="color:#111;border-bottom:2px solid #d4af37;padding-bottom:8px;">E-COM</h2>
  {body}
  <p style="margin-top:32px;font-size:12px;color:#888;">
    This is an automated message from E-COM. Please don't reply directly to this email.
  </p>
</div>
"""


def _wrap(body: str) -> str:
    return _WRAPPER.format(body=body)


def password_reset_email(name: str, reset_link: str) -> tuple[str, str]:
    subject = "Reset your E-COM password"
    body = f"""
      <p>Hi {name},</p>
      <p>We received a request to reset your E-COM account password. Click the button below to choose a new one — this link expires in 30 minutes.</p>
      <p style="margin:24px 0;">
        <a href="{reset_link}" style="background:#d4af37;color:#111;padding:12px 24px;text-decoration:none;border-radius:6px;font-weight:bold;">Reset Password</a>
      </p>
      <p>If you didn't request this, you can safely ignore this email — your password won't be changed.</p>
    """
    return subject, _wrap(body)


def order_confirmation_email(order, items: Iterable[dict]) -> tuple[str, str]:
    subject = f"Order confirmed — #{order.id[:8]}"
    rows = "".join(
        f"""<tr>
              <td style="padding:6px 0;">{i['name']} ({i['size']}/{i['color']}) × {i['quantity']}</td>
              <td style="padding:6px 0;text-align:right;">Rs {i['price'] * i['quantity']:,.0f}</td>
            </tr>"""
        for i in items
    )
    body = f"""
      <p>Hi {order.full_name},</p>
      <p>Thanks for your order — we've got it and it's being prepared. Here's a summary:</p>
      <table style="width:100%;border-collapse:collapse;margin:16px 0;">
        {rows}
        <tr><td style="padding-top:12px;border-top:1px solid #ddd;font-weight:bold;">Total</td>
            <td style="padding-top:12px;border-top:1px solid #ddd;text-align:right;font-weight:bold;">Rs {order.total:,.0f}</td></tr>
      </table>
      <p><strong>Shipping to:</strong> {order.address}, {order.city} {order.postal_code}</p>
      <p><strong>Payment method:</strong> {order.payment_method.upper()}</p>
      <p>Order reference: <code>{order.id}</code></p>
    """
    return subject, _wrap(body)


_STATUS_COPY = {
    "confirmed": "Your order has been confirmed and is being prepared.",
    "shipped": "Your order is on its way!",
    "delivered": "Your order has been delivered. We hope you love it!",
    "cancelled": "Your order has been cancelled.",
    "returned": "Your return has been processed.",
}


def order_status_update_email(order, new_status: str) -> tuple[str, str]:
    subject = f"Order #{order.id[:8]} — {new_status.capitalize()}"
    message = _STATUS_COPY.get(new_status, f"Your order status changed to {new_status}.")
    body = f"""
      <p>Hi {order.full_name},</p>
      <p>{message}</p>
      <p>Order reference: <code>{order.id}</code></p>
      <p>Current status: <strong style="text-transform:capitalize;">{new_status}</strong></p>
    """
    return subject, _wrap(body)


def return_request_submitted_email(order) -> tuple[str, str]:
    subject = f"Return request received — Order #{order.id[:8]}"
    body = f"""
      <p>Hi {order.full_name},</p>
      <p>We've received your return request and it's being reviewed. We'll email you once it's approved or rejected.</p>
      <p>Order reference: <code>{order.id}</code></p>
    """
    return subject, _wrap(body)


def return_request_resolved_email(order, approved: bool, admin_note: str = None) -> tuple[str, str]:
    subject = f"Return request {'approved' if approved else 'rejected'} — Order #{order.id[:8]}"
    message = (
        "Your return has been approved and a refund will be processed."
        if approved else
        "Your return request was not approved."
    )
    note_html = f"<p><strong>Note from our team:</strong> {admin_note}</p>" if admin_note else ""
    body = f"""
      <p>Hi {order.full_name},</p>
      <p>{message}</p>
      {note_html}
      <p>Order reference: <code>{order.id}</code></p>
    """
    return subject, _wrap(body)


def low_stock_alert_email(products: Iterable[dict]) -> tuple[str, str]:
    products = list(products)
    subject = f"Low stock alert — {len(products)} product(s) need restocking"
    rows = "".join(
        f"""<tr>
              <td style="padding:6px 0;">{p['name']}</td>
              <td style="padding:6px 0;text-align:right;">{p['total_stock']} left</td>
            </tr>"""
        for p in products
    )
    body = f"""
      <p>The following products have dropped to or below the low-stock threshold:</p>
      <table style="width:100%;border-collapse:collapse;margin:16px 0;">{rows}</table>
      <p>Restock soon to avoid running out.</p>
    """
    return subject, _wrap(body)
