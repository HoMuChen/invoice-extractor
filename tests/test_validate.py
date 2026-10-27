from invoice_extractor.validate import check


def test_consistent_invoice_has_no_issues(invoice):
    assert check(invoice) == []


def test_line_amount_mismatch(invoice):
    invoice.line_items[1].amount = 247.50
    invoice.subtotal = 1447.50
    invoice.total = 1566.09
    assert check(invoice) == ["Line 2: 2.5 x 95.00 = 237.50, printed 247.50"]


def test_subtotal_and_total_mismatch(invoice):
    invoice.subtotal = 1400.00
    issues = check(invoice)
    assert "Line items sum to 1437.50, subtotal printed 1400.00" in issues
    assert "Subtotal + tax + shipping = 1518.59, total printed 1556.09" in issues


def test_one_cent_rounding_tolerated(invoice):
    invoice.total = 1556.10
    assert check(invoice) == []


def test_dates_and_currency(invoice):
    invoice.invoice_date = "04/03/2026"
    invoice.currency = "$"
    issues = check(invoice)
    assert "Invoice date not a valid date: '04/03/2026'" in issues
    assert "Currency is not an ISO code: '$'" in issues


def test_due_before_issue(invoice):
    invoice.due_date = "2026-03-01"
    assert check(invoice) == ["Due date is before invoice date"]


def test_missing_optional_due_date_is_fine(invoice):
    invoice.due_date = None
    assert check(invoice) == []
