# invoice-extractor

**Drop a folder of invoice PDFs in, get a clean Excel workbook out — with every arithmetic error flagged.**

`invoice-extractor` sends each PDF to Claude, gets back structured data that is validated against a typed
schema, then double-checks the numbers itself: line totals, subtotal, tax and grand total. Anything that
doesn't add up is marked **REVIEW** with a plain-English reason, so a person only looks at the invoices that need it.

Illustrative output:

```
$ invoice-extractor extract ./invoices --out out/invoices.xlsx
┏━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ file           ┃ status ┃ invoice #      ┃        total ┃ issues                                            ┃
┡━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ invoice_07.pdf │ REVIEW │ KF7499         │ 5,762.28 GBP │ Line 4: 1 x 348.53 = 348.53, printed 358.53       │
│ invoice_10.pdf │ OK     │ RE-2026-8484   │ 7,333.65 EUR │                                                   │
└────────────────┴────────┴────────────────┴──────────────┴───────────────────────────────────────────────────┘
```

## What you get

An `.xlsx` with three sheets (plus the same data as `.json`):

| sheet | contents |
|---|---|
| **Invoices** | one row per PDF: number, dates, vendor, customer, currency, subtotal, tax, shipping, total, status (colour-coded OK / REVIEW / ERROR) |
| **Line Items** | every line of every invoice: description, quantity, unit price, amount |
| **Review** | only the problems — e.g. `Line items sum to 4,791.90, subtotal printed 4,801.90` |

## Handles real-world formats

- US, UK and European conventions — `March 4, 2026`, `04/03/2026` (UK), `04.03.2026`; `$1,234.56`, `£1,234.56`, `1.234,56 €`
  — all normalized to ISO dates, plain numbers and ISO currency codes
- Different layouts and labels (`Amount due`, `Gross total`, `Net amount`, `VAT @ 20%`, `MwSt.`)
- Multi-page invoices
- Values are copied **as printed**, never "fixed" by the model — so a vendor's arithmetic mistake is caught
  instead of silently corrected

## Try it on the sample set

The repo can generate 12 fictional invoices across three layouts (US / UK / EU), including a 32-line
two-page invoice and 3 invoices with deliberate printing errors, each with ground-truth JSON:

```bash
uv sync
uv run invoice-extractor make-samples --out samples
export ANTHROPIC_API_KEY=...        # or: ant auth login
uv run invoice-extractor extract samples --out out/samples.xlsx --truth samples/truth
```

`--truth` scores every extracted field (header fields plus quantity / unit price / amount of every line)
against the ground truth.

## How it works

1. Each PDF is sent to **Claude Opus 5.5** as a native PDF document (no OCR step, layout is preserved).
2. The response is constrained to a Pydantic `Invoice` schema with structured outputs, so it is always valid,
   typed JSON.
3. `validate.py` checks quantity × unit price, line sum vs. subtotal, subtotal + tax + shipping vs. total,
   date validity and currency codes (±1 cent tolerance).
4. Results are written to Excel/JSON; PDFs are processed concurrently (`--concurrency`, default 4).

Options: `--effort low|medium|high|xhigh|max` (default `medium`), `--concurrency N`, `--truth DIR`.
Server-side fallback is enabled, so a request declined by a safety classifier is retried on a fallback model
automatically.

## Development

```bash
uv sync
uv run pytest     # 20 tests; the Claude API is faked, no key needed
```

## Need something like this for your documents?

Purchase orders, bank statements, receipts, contracts, forms — I build extraction pipelines that land data
in Excel, Google Sheets or your database, with validation rules for your business. Reach out on Upwork.

## License

MIT
