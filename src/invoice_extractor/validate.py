"""Arithmetic and sanity checks that flag invoices needing a human look."""

from __future__ import annotations

from datetime import date

from .models import Invoice

TOLERANCE = 0.011  # Allow for one-cent rounding on printed values.


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= TOLERANCE


def _is_iso_date(value: str | None) -> bool:
    if not value:
        return False
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


def check(invoice: Invoice) -> list[str]:
    """Return human-readable issues; an empty list means the invoice is internally consistent."""
    issues: list[str] = []
    if not invoice.invoice_number.strip():
        issues.append("Missing invoice number")
    if not _is_iso_date(invoice.invoice_date):
        issues.append(f"Invoice date not a valid date: {invoice.invoice_date!r}")
    if invoice.due_date is not None and not _is_iso_date(invoice.due_date):
        issues.append(f"Due date not a valid date: {invoice.due_date!r}")
    if _is_iso_date(invoice.invoice_date) and _is_iso_date(invoice.due_date) and invoice.due_date < invoice.invoice_date:
        issues.append("Due date is before invoice date")
    if len(invoice.currency) != 3 or not invoice.currency.isalpha():
        issues.append(f"Currency is not an ISO code: {invoice.currency!r}")
    if not invoice.line_items:
        issues.append("No line items")

    for i, item in enumerate(invoice.line_items, start=1):
        if not _close(item.quantity * item.unit_price, item.amount):
            issues.append(
                f"Line {i}: {item.quantity:g} x {item.unit_price:.2f} = "
                f"{item.quantity * item.unit_price:.2f}, printed {item.amount:.2f}"
            )

    lines_sum = round(sum(item.amount for item in invoice.line_items), 2)
    if invoice.line_items and not _close(lines_sum, invoice.subtotal):
        issues.append(f"Line items sum to {lines_sum:.2f}, subtotal printed {invoice.subtotal:.2f}")
    expected_total = round(invoice.subtotal + invoice.tax + invoice.shipping, 2)
    if not _close(expected_total, invoice.total):
        issues.append(
            f"Subtotal + tax + shipping = {expected_total:.2f}, total printed {invoice.total:.2f}"
        )
    return issues
