"""Schema Claude fills in for every invoice (also used as the structured-output format)."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class LineItem(BaseModel):
    description: str
    quantity: float
    unit_price: float
    amount: float = Field(description="Line total exactly as printed.")


class Invoice(BaseModel):
    invoice_number: str
    invoice_date: str = Field(description="YYYY-MM-DD")
    due_date: Optional[str] = Field(description="YYYY-MM-DD, or null if not printed.")
    vendor_name: str
    vendor_address: Optional[str]
    customer_name: str
    currency: str = Field(description="ISO 4217 code, e.g. USD, EUR, GBP.")
    line_items: list[LineItem]
    subtotal: float
    tax: float = Field(description="Total tax/VAT; 0 if none is printed.")
    shipping: float = Field(description="Shipping/delivery charge; 0 if none is printed.")
    total: float = Field(description="Grand total / amount due exactly as printed.")
