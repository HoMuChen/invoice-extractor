from types import SimpleNamespace

import pytest

from invoice_extractor.models import Invoice, LineItem


@pytest.fixture
def invoice() -> Invoice:
    return Invoice(
        invoice_number="INV-1001",
        invoice_date="2026-03-04",
        due_date="2026-04-03",
        vendor_name="Bluepeak Digital LLC",
        vendor_address="77 Congress St, Austin, TX 78701",
        customer_name="Atlas Coworking",
        currency="USD",
        line_items=[
            LineItem(description="SEO audit", quantity=1, unit_price=1200.00, amount=1200.00),
            LineItem(description="Consulting hours", quantity=2.5, unit_price=95.00, amount=237.50),
        ],
        subtotal=1437.50,
        tax=118.59,
        shipping=0,
        total=1556.09,
    )


class FakeMessages:
    """Stands in for ``client.beta.messages``; records each request and replays canned responses."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def parse(self, **kwargs):
        self.calls.append(kwargs)
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def fake_response(parsed=None, stop_reason="end_turn"):
    return SimpleNamespace(parsed_output=parsed, stop_reason=stop_reason,
                           usage=SimpleNamespace(input_tokens=1500, output_tokens=300))


@pytest.fixture
def make_client():
    def _make(*responses):
        messages = FakeMessages(responses)
        return SimpleNamespace(beta=SimpleNamespace(messages=messages)), messages
    return _make
