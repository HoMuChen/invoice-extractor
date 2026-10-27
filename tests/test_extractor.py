import base64

import anthropic
import httpx2 as httpx  # anthropic 1.x+ is built on httpx2
import pytest

from conftest import fake_response
from invoice_extractor.extractor import FALLBACK_BETA, MODEL, extract_all, extract_one
from invoice_extractor.models import Invoice


@pytest.fixture
def pdf(tmp_path):
    path = tmp_path / "a.pdf"
    path.write_bytes(b"%PDF-1.4 fake")
    return path


async def test_request_shape(make_client, pdf, invoice):
    client, messages = make_client(fake_response(invoice))
    result = await extract_one(client, pdf, effort="high")

    assert result.status == "OK" and result.invoice == invoice
    call = messages.calls[0]
    assert call["model"] == MODEL
    assert call["betas"] == [FALLBACK_BETA] and call["fallbacks"] == "default"
    assert call["output_format"] is Invoice
    assert call["output_config"] == {"effort": "high"}
    doc, text = call["messages"][0]["content"]
    assert doc["source"]["media_type"] == "application/pdf"
    assert base64.standard_b64decode(doc["source"]["data"]) == b"%PDF-1.4 fake"
    assert text["type"] == "text"


async def test_inconsistent_invoice_needs_review(make_client, pdf, invoice):
    invoice.total = 9999.0
    client, _ = make_client(fake_response(invoice))
    result = await extract_one(client, pdf)
    assert result.status == "REVIEW" and result.issues


@pytest.mark.parametrize(
    "stop_reason, parsed, message",
    [("refusal", None, "declined"), ("max_tokens", None, "truncated"), ("end_turn", None, "No structured output")],
)
async def test_unusable_responses_are_errors(make_client, pdf, stop_reason, parsed, message):
    client, _ = make_client(fake_response(parsed, stop_reason))
    result = await extract_one(client, pdf)
    assert result.status == "ERROR" and message in result.error


async def test_api_errors_are_recorded_per_file(make_client, pdf):
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    error = anthropic.BadRequestError("PDF too large", response=httpx.Response(400, request=request), body=None)
    client, _ = make_client(error)
    result = await extract_one(client, pdf)
    assert result.status == "ERROR" and "PDF too large" in result.error


async def test_extract_all_keeps_order_and_reports_progress(make_client, tmp_path, invoice):
    paths = []
    for name in ("a.pdf", "b.pdf", "c.pdf"):
        (tmp_path / name).write_bytes(b"%PDF")
        paths.append(tmp_path / name)
    client, messages = make_client(*(fake_response(invoice) for _ in paths))
    done = []
    results = await extract_all(paths, client=client, concurrency=2, on_done=done.append)
    assert [r.path.name for r in results] == ["a.pdf", "b.pdf", "c.pdf"]
    assert len(done) == 3 and len(messages.calls) == 3
