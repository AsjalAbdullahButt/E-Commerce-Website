import io
from typing import Iterable

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

_STYLES = getSampleStyleSheet()
_GOLD = colors.HexColor("#B8860B")


def generate_invoice_pdf(order, items: Iterable[dict]) -> bytes:
    """Renders a simple order invoice/receipt as PDF bytes. reportlab (pure Python, no system
    libraries like wkhtmltopdf/weasyprint need) draws directly onto the page — no HTML template
    engine involved, matching the plain-Python email templates in services/email_templates.py."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=20 * mm, bottomMargin=20 * mm, leftMargin=20 * mm, rightMargin=20 * mm,
    )

    title_style = ParagraphStyle("InvoiceTitle", parent=_STYLES["Title"], textColor=_GOLD, fontSize=22)
    heading_style = ParagraphStyle("InvoiceHeading", parent=_STYLES["Heading3"], spaceBefore=12)

    elements = [
        Paragraph("E-COM", title_style),
        Paragraph("Order Invoice / Receipt", _STYLES["Heading2"]),
        Spacer(1, 8),
        Paragraph(f"Order Reference: <b>{order.id}</b>", _STYLES["Normal"]),
        Paragraph(f"Date: {order.created_at.strftime('%Y-%m-%d %H:%M') if order.created_at else ''}", _STYLES["Normal"]),
        Paragraph(f"Status: {order.status.capitalize()}", _STYLES["Normal"]),
        Spacer(1, 12),
        Paragraph("Bill To", heading_style),
        Paragraph(order.full_name, _STYLES["Normal"]),
        Paragraph(order.phone, _STYLES["Normal"]),
        Paragraph(f"{order.address}, {order.city} {order.postal_code}", _STYLES["Normal"]),
        Spacer(1, 12),
        Paragraph("Items", heading_style),
    ]

    items = list(items)
    table_data = [["Item", "Size/Color", "Qty", "Unit Price", "Total"]]
    for i in items:
        table_data.append([
            i["name"], f"{i['size']}/{i['color']}", str(i["quantity"]),
            f"Rs {i['price']:,.2f}", f"Rs {i['price'] * i['quantity']:,.2f}",
        ])
    items_table = Table(table_data, colWidths=[60 * mm, 35 * mm, 15 * mm, 30 * mm, 30 * mm])
    items_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _GOLD),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F5F5")]),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 12))

    totals_data = [
        ["Subtotal", f"Rs {order.subtotal:,.2f}"],
        ["Discount", f"-Rs {order.discount:,.2f}"],
        ["Tax", f"Rs {order.tax:,.2f}"],
        ["Delivery", f"Rs {order.delivery_fee:,.2f}"],
        ["Total", f"Rs {order.total:,.2f}"],
    ]
    totals_table = Table(totals_data, colWidths=[140 * mm, 30 * mm])
    totals_table.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("LINEABOVE", (0, -1), (-1, -1), 1, colors.black),
        ("FONTSIZE", (0, -1), (-1, -1), 12),
    ]))
    elements.append(totals_table)
    elements.append(Spacer(1, 12))
    elements.append(Paragraph(f"Payment Method: {(order.payment_method or 'cod').upper()}", _STYLES["Normal"]))
    elements.append(Paragraph(f"Payment Status: {order.payment_status.replace('_', ' ').capitalize()}", _STYLES["Normal"]))

    doc.build(elements)
    return buf.getvalue()
