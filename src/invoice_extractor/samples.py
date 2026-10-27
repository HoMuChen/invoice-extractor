"""Generate synthetic invoice PDFs (three layouts, US/UK/EU formats) with ground-truth JSON.

Everything here is fictional. Some invoices deliberately contain printing errors (a wrong line
amount or total) so the validation step has something real to catch.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

from reportlab.lib.pagesizes import A4, LETTER
from reportlab.pdfgen.canvas import Canvas

from .models import Invoice, LineItem

VENDORS = [
    ("Northwind Facility Services", "418 Harbor Ave, Seattle, WA 98104"),
    ("Bluepeak Digital LLC", "77 Congress St, Austin, TX 78701"),
    ("Kestrel & Finch Ltd", "12 Albion Road, Bristol BS1 4QX, United Kingdom"),
    ("Thornbury Print Co.", "5 Mill Lane, Leeds LS2 7EW, United Kingdom"),
    ("Brandt Industrietechnik GmbH", "Hafenstraße 21, 20457 Hamburg, Germany"),
    ("Lumen Atelier SARL", "9 Rue des Tanneurs, 69001 Lyon, France"),
]
CUSTOMERS = ["Harbor View Dental", "Oakridge Property Group", "Cobalt Robotics Inc", "Maple & Co. Bakery",
             "Silverline Logistics", "Greenfield Clinic", "Atlas Coworking"]
CATALOG = [
    ("Website maintenance (monthly)", 1, 450.00), ("SEO audit", 1, 1200.00), ("Consulting hours", 0.5, 95.00),
    ("Copywriting – landing page", 1, 380.00), ("Office cleaning visit", 1, 140.00),
    ("Replacement air filter MERV 13", 1, 18.75), ("Business cards (box of 500)", 1, 42.50),
    ("Brochure printing A5", 1, 0.85), ("Server hosting (monthly)", 1, 79.00), ("Data migration", 1, 650.00),
    ("Hydraulic seal kit", 1, 23.40), ("On-site technician hour", 0.5, 88.00), ("Logo redesign", 1, 900.00),
    ("Photography session", 1, 520.00), ("Delivery pallet", 1, 35.00),
]


@dataclass
class Style:
    layout: str
    currency: str
    symbol: str
    vendor_range: tuple[int, int]
    tax_label: str
    tax_rate: float
    pagesize: tuple[float, float]

    def money(self, value: float) -> str:
        if self.layout == "eu":
            text = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            return f"{text} {self.symbol}"
        return f"{self.symbol}{value:,.2f}"

    def day(self, d: date) -> str:
        if self.layout == "us":
            return d.strftime("%B %-d, %Y")
        if self.layout == "uk":
            return d.strftime("%d/%m/%Y")
        return d.strftime("%d.%m.%Y")


STYLES = {
    "us": Style("us", "USD", "$", (0, 2), "Sales tax (8.25%)", 0.0825, LETTER),
    "uk": Style("uk", "GBP", "£", (2, 4), "VAT @ 20%", 0.20, A4),
    "eu": Style("eu", "EUR", "€", (4, 6), "MwSt./VAT 19%", 0.19, A4),
}


def build_invoice(seed: int, layout: str, n_lines: int, error: str | None = None) -> Invoice:
    """Create the ground-truth invoice; ``error`` injects a printing mistake ('line' or 'total')."""
    rng = random.Random(seed)
    style = STYLES[layout]
    vendor_name, vendor_address = VENDORS[rng.randrange(*style.vendor_range)]
    issued = date(2026, 1, 1) + timedelta(days=rng.randrange(0, 270))
    items = []
    for _ in range(n_lines):
        desc, step, price = rng.choice(CATALOG)
        qty = step * rng.randint(1, 12) if step < 1 else float(rng.choice([1, 1, 2, 3, 5, 10, 250]))
        unit = round(price * rng.uniform(0.9, 1.1), 2)
        items.append(LineItem(description=desc, quantity=qty, unit_price=unit, amount=round(qty * unit, 2)))
    if error == "line":
        bad = items[len(items) // 2]
        bad.amount = round(bad.amount + 10, 2)
    subtotal = round(sum(i.amount for i in items), 2)
    tax = round(subtotal * style.tax_rate, 2)
    shipping = float(rng.choice([0, 0, 15, 25]))
    total = round(subtotal + tax + shipping, 2)
    if error == "total":
        total = round(total + 5, 2)
    prefix = {"us": "INV-", "uk": "KF", "eu": "RE-2026-"}[layout]
    return Invoice(
        invoice_number=f"{prefix}{rng.randint(1000, 9999)}",
        invoice_date=issued.isoformat(),
        due_date=(issued + timedelta(days=rng.choice([14, 30]))).isoformat() if rng.random() > 0.2 else None,
        vendor_name=vendor_name,
        vendor_address=vendor_address,
        customer_name=rng.choice(CUSTOMERS),
        currency=style.currency,
        line_items=items,
        subtotal=subtotal,
        tax=tax,
        shipping=shipping,
        total=total,
    )


def render_pdf(inv: Invoice, layout: str, path: Path) -> None:
    style = STYLES[layout]
    width, height = style.pagesize
    c = Canvas(str(path), pagesize=style.pagesize)
    c.setTitle(f"Invoice {inv.invoice_number}")
    margin = 50
    labels = {
        "us": dict(title="INVOICE", no="Invoice #", date="Invoice date", due="Due date", bill="Bill to",
                   cols=("Description", "Qty", "Unit price", "Amount"), sub="Subtotal", ship="Shipping",
                   total="TOTAL"),
        "uk": dict(title="Tax Invoice", no="Inv No.", date="Issued", due="Payment due", bill="Invoice to",
                   cols=("Item", "Qty/Hrs", "Rate", "Line total"), sub="Net amount", ship="Delivery",
                   total="Amount due"),
        "eu": dict(title="Rechnung / Invoice", no="Invoice No.", date="Date", due="Due", bill="Customer",
                   cols=("Pos. / Description", "Qty", "Price", "Total"), sub="Net total", ship="Freight",
                   total="Gross total"),
    }[layout]

    def header() -> float:
        y = height - margin
        c.setFont("Helvetica-Bold", 20)
        if layout == "uk":
            c.drawRightString(width - margin, y, labels["title"])
        else:
            c.drawString(margin, y, labels["title"])
        c.setFont("Helvetica-Bold", 11)
        vx = margin if layout == "uk" else width - margin
        draw = c.drawString if layout == "uk" else c.drawRightString
        draw(vx, y - 30, inv.vendor_name)
        c.setFont("Helvetica", 9)
        for i, part in enumerate(inv.vendor_address.split(", ")):
            draw(vx, y - 44 - 12 * i, part)
        y -= 110
        c.setFont("Helvetica", 10)
        meta = [(labels["no"], inv.invoice_number), (labels["date"], style.day(date.fromisoformat(inv.invoice_date)))]
        if inv.due_date:
            meta.append((labels["due"], style.day(date.fromisoformat(inv.due_date))))
        for i, (k, v) in enumerate(meta):
            c.drawString(margin, y - 14 * i, f"{k}: {v}")
        c.setFont("Helvetica-Bold", 10)
        c.drawString(width / 2, y, f"{labels['bill']}:")
        c.setFont("Helvetica", 10)
        c.drawString(width / 2, y - 14, inv.customer_name)
        return y - 60

    def table_header(y: float) -> float:
        c.setFont("Helvetica-Bold", 10)
        cols = labels["cols"]
        c.drawString(margin, y, cols[0])
        c.drawRightString(width - margin - 200, y, cols[1])
        c.drawRightString(width - margin - 100, y, cols[2])
        c.drawRightString(width - margin, y, cols[3])
        c.line(margin, y - 4, width - margin, y - 4)
        return y - 18

    y = table_header(header())
    c.setFont("Helvetica", 10)
    for n, item in enumerate(inv.line_items, start=1):
        if y < 140:
            c.setFont("Helvetica-Oblique", 8)
            c.drawRightString(width - margin, 40, "continued on next page")
            c.showPage()
            y = table_header(height - margin)
            c.setFont("Helvetica", 10)
        desc = f"{n}. {item.description}" if layout == "eu" else item.description
        c.drawString(margin, y, desc)
        c.drawRightString(width - margin - 200, y, f"{item.quantity:g}")
        c.drawRightString(width - margin - 100, y, style.money(item.unit_price))
        c.drawRightString(width - margin, y, style.money(item.amount))
        y -= 16

    y -= 10
    c.line(width - margin - 220, y + 6, width - margin, y + 6)
    rows = [(labels["sub"], inv.subtotal), (style.tax_label, inv.tax)]
    if inv.shipping:
        rows.append((labels["ship"], inv.shipping))
    for label, value in rows:
        c.drawString(width - margin - 220, y - 8, label)
        c.drawRightString(width - margin, y - 8, style.money(value))
        y -= 16
    c.setFont("Helvetica-Bold", 12)
    c.drawString(width - margin - 220, y - 12, labels["total"])
    c.drawRightString(width - margin, y - 12, style.money(inv.total))
    c.setFont("Helvetica", 8)
    c.drawString(margin, 40, "Sample document generated for testing. All names and figures are fictional.")
    c.save()


# (seed, layout, line count, injected error)
SAMPLE_SET = [
    (1, "us", 3, None), (2, "us", 6, None), (3, "us", 4, "total"), (4, "us", 32, None),
    (5, "uk", 2, None), (6, "uk", 5, None), (7, "uk", 7, "line"), (8, "uk", 4, None),
    (9, "eu", 3, None), (10, "eu", 8, None), (11, "eu", 5, "total"), (12, "eu", 6, None),
]


def generate(out_dir: Path) -> list[dict]:
    """Write ``invoice_XX.pdf`` + ``truth/invoice_XX.json`` and return a manifest."""
    truth_dir = out_dir / "truth"
    truth_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    for seed, layout, n_lines, error in SAMPLE_SET:
        name = f"invoice_{seed:02d}"
        inv = build_invoice(seed, layout, n_lines, error)
        render_pdf(inv, layout, out_dir / f"{name}.pdf")
        (truth_dir / f"{name}.json").write_text(inv.model_dump_json(indent=2))
        manifest.append({"file": f"{name}.pdf", "layout": layout, "lines": n_lines, "injected_error": error})
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest
