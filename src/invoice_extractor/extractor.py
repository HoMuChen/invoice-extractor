"""Send each PDF to Claude and get a validated :class:`Invoice` back."""

from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass, field
from pathlib import Path

import anthropic

from .models import Invoice
from .validate import check

MODEL = "claude-opus-5-5"
# Server-side fallback: if a request is declined by a safety classifier, the API
# re-runs it on a suitable fallback model inside the same call.
FALLBACK_BETA = "server-side-fallback-2026-07-01"

SYSTEM_PROMPT = """You extract structured data from invoice PDFs for bookkeeping.

Copy every value exactly as it is printed on the document. Do not fix arithmetic, recompute totals,
or invent values that are not shown — downstream checks rely on seeing what the document actually says.

Normalize formats only:
- Dates as YYYY-MM-DD. Read the document's own convention (e.g. 03.04.2026 on a German invoice is 3 April).
- Amounts as plain numbers without currency symbols or thousands separators; read European formats
  like 1.234,56 as 1234.56.
- Currency as an ISO 4217 code inferred from symbols or text (€ -> EUR, £ -> GBP, $ on a US invoice -> USD).
- Use null for optional fields that are not printed, and 0 for tax or shipping when none is shown."""


@dataclass
class Extraction:
    path: Path
    invoice: Invoice | None = None
    issues: list[str] = field(default_factory=list)
    error: str = ""
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def status(self) -> str:
        if self.error:
            return "ERROR"
        return "REVIEW" if self.issues else "OK"


def _document_block(path: Path) -> dict:
    data = base64.standard_b64encode(path.read_bytes()).decode("ascii")
    return {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": data}}


async def extract_one(client: anthropic.AsyncAnthropic, path: Path, effort: str = "medium") -> Extraction:
    result = Extraction(path=path)
    try:
        response = await client.beta.messages.parse(
            model=MODEL,
            max_tokens=16000,
            betas=[FALLBACK_BETA],
            fallbacks="default",
            system=SYSTEM_PROMPT,
            output_config={"effort": effort},
            output_format=Invoice,
            messages=[{
                "role": "user",
                "content": [_document_block(path), {"type": "text", "text": "Extract this invoice."}],
            }],
        )
    except anthropic.BadRequestError as exc:
        result.error = f"Bad request: {exc.message}"
        return result
    except anthropic.AuthenticationError:
        raise  # A bad key affects every file; stop the run.
    except anthropic.RateLimitError:
        result.error = "Rate limited after retries"
        return result
    except anthropic.APIStatusError as exc:
        result.error = f"API error {exc.status_code}: {exc.message}"
        return result
    except anthropic.APIConnectionError:
        result.error = "Network error"
        return result

    result.input_tokens = response.usage.input_tokens
    result.output_tokens = response.usage.output_tokens
    if response.stop_reason == "refusal":
        result.error = "Model declined to process this document"
    elif response.stop_reason == "max_tokens":
        result.error = "Response truncated (max_tokens)"
    elif response.parsed_output is None:
        result.error = "No structured output returned"
    else:
        result.invoice = response.parsed_output
        result.issues = check(result.invoice)
    return result


async def extract_all(
    paths: list[Path],
    effort: str = "medium",
    concurrency: int = 4,
    client: anthropic.AsyncAnthropic | None = None,
    on_done=None,
) -> list[Extraction]:
    client = client or anthropic.AsyncAnthropic()
    sem = asyncio.Semaphore(concurrency)

    async def run(path: Path) -> Extraction:
        async with sem:
            result = await extract_one(client, path, effort)
        if on_done:
            on_done(result)
        return result

    return await asyncio.gather(*(run(p) for p in paths))
