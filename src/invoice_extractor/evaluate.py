"""Score extractions against ground-truth JSON (used with the synthetic sample set)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .extractor import Extraction
from .models import Invoice

HEADER_FIELDS = ["invoice_number", "invoice_date", "due_date", "vendor_name", "customer_name", "currency",
                 "subtotal", "tax", "shipping", "total"]


@dataclass
class Score:
    correct: int = 0
    total: int = 0
    mismatches: list[str] = field(default_factory=list)

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.0


def _norm(value):
    if isinstance(value, float):
        return round(value, 2)
    if isinstance(value, str):
        return " ".join(value.lower().split())
    return value


def compare(predicted: Invoice | None, truth: Invoice, label: str, score: Score) -> None:
    """Field-level comparison: header fields + quantity/unit price/amount of every line."""
    pairs = [(f, getattr(predicted, f, None) if predicted else None, getattr(truth, f)) for f in HEADER_FIELDS]
    pred_lines = predicted.line_items if predicted else []
    for i, t_line in enumerate(truth.line_items):
        p_line = pred_lines[i] if i < len(pred_lines) else None
        for f in ("quantity", "unit_price", "amount"):
            pairs.append((f"line{i + 1}.{f}", getattr(p_line, f, None), getattr(t_line, f)))
    for name, got, want in pairs:
        score.total += 1
        if _norm(got) == _norm(want):
            score.correct += 1
        else:
            score.mismatches.append(f"{label} {name}: got {got!r}, expected {want!r}")


def evaluate(results: list[Extraction], truth_dir: Path) -> Score:
    score = Score()
    for ex in results:
        truth_file = truth_dir / (ex.path.stem + ".json")
        if not truth_file.exists():
            continue
        truth = Invoice.model_validate(json.loads(truth_file.read_text()))
        compare(ex.invoice, truth, ex.path.name, score)
    return score
