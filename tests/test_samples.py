import json

from invoice_extractor.models import Invoice
from invoice_extractor.samples import SAMPLE_SET, build_invoice, generate
from invoice_extractor.validate import check


def test_generate_writes_pdfs_truth_and_manifest(tmp_path):
    manifest = generate(tmp_path)
    assert len(manifest) == len(SAMPLE_SET) == 12
    for entry in manifest:
        pdf = tmp_path / entry["file"]
        assert pdf.read_bytes().startswith(b"%PDF")
        truth = Invoice.model_validate_json((tmp_path / "truth" / pdf.with_suffix(".json").name).read_text())
        assert len(truth.line_items) == entry["lines"]
    assert json.loads((tmp_path / "manifest.json").read_text()) == manifest


def test_validator_flags_exactly_the_injected_errors():
    for seed, layout, n_lines, error in SAMPLE_SET:
        issues = check(build_invoice(seed, layout, n_lines, error))
        assert bool(issues) == bool(error), (seed, issues)


def test_generation_is_deterministic():
    assert build_invoice(3, "us", 4) == build_invoice(3, "us", 4)
