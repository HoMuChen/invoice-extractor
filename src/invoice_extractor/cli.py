"""Command-line entry point."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import anthropic
import typer
from rich.console import Console
from rich.progress import Progress
from rich.table import Table

from . import export, samples
from .evaluate import evaluate as score_against_truth
from .extractor import MODEL, extract_all

app = typer.Typer(add_completion=False, help="Turn invoice PDFs into a validated Excel workbook with Claude.")
console = Console()


@app.command("make-samples")
def make_samples(out: Annotated[Path, typer.Option(help="Directory for the synthetic PDFs.")] = Path("samples")) -> None:
    """Generate 12 fictional invoices (US/UK/EU layouts) with ground-truth JSON."""
    manifest = samples.generate(out)
    errors = sum(1 for m in manifest if m["injected_error"])
    console.print(f"Wrote {len(manifest)} PDFs to [bold]{out}[/] ({errors} with deliberate printing errors).")


@app.command()
def extract(
    input_dir: Annotated[Path, typer.Argument(help="Folder containing PDF invoices.")],
    out: Annotated[Path, typer.Option(help="Output workbook (.xlsx); a .json is written next to it.")] = Path("out/invoices.xlsx"),
    effort: Annotated[str, typer.Option(help="Claude effort: low | medium | high | xhigh | max.")] = "medium",
    concurrency: Annotated[int, typer.Option(help="PDFs processed in parallel.")] = 4,
    truth: Annotated[Path | None, typer.Option(help="Folder of ground-truth JSON to score accuracy against.")] = None,
) -> None:
    """Extract every PDF in INPUT_DIR, validate it, and write Excel + JSON."""
    pdfs = sorted(input_dir.glob("*.pdf"))
    if not pdfs:
        raise typer.BadParameter(f"No PDFs found in {input_dir}")
    try:
        results = asyncio.run(_run(pdfs, effort, concurrency))
    except anthropic.AuthenticationError:
        console.print("[red]Authentication failed.[/] Check ANTHROPIC_API_KEY or run `ant auth login`.")
        raise typer.Exit(1)
    except TypeError as exc:
        # The SDK raises TypeError when no credential source is configured at all.
        if "authentication method" not in str(exc):
            raise
        console.print("[red]No Anthropic credentials found.[/] Set ANTHROPIC_API_KEY or run `ant auth login`.")
        raise typer.Exit(1)

    export.write_xlsx(results, out)
    export.write_json(results, out.with_suffix(".json"))

    table = Table("file", "status", "invoice #", "total", "issues")
    for ex in results:
        inv = ex.invoice
        table.add_row(ex.path.name, ex.status, inv.invoice_number if inv else "",
                      f"{inv.total:,.2f} {inv.currency}" if inv else "", "; ".join(ex.issues) or ex.error)
    console.print(table)
    counts = {s: sum(1 for r in results if r.status == s) for s in ("OK", "REVIEW", "ERROR")}
    tokens_in = sum(r.input_tokens for r in results)
    tokens_out = sum(r.output_tokens for r in results)
    console.print(f"{counts['OK']} OK, {counts['REVIEW']} need review, {counts['ERROR']} errors "
                  f"· {MODEL} · {tokens_in:,} input / {tokens_out:,} output tokens")
    console.print(f"Saved [bold]{out}[/] and [bold]{out.with_suffix('.json')}[/]")

    if truth:
        score = score_against_truth(results, truth)
        console.print(f"Field accuracy vs ground truth: [bold]{score.correct}/{score.total} "
                      f"({score.accuracy:.1%})[/]")
        for line in score.mismatches[:20]:
            console.print(f"  [yellow]{line}[/]")


async def _run(pdfs: list[Path], effort: str, concurrency: int):
    with Progress(console=console) as progress:
        task = progress.add_task("Extracting", total=len(pdfs))
        return await extract_all(pdfs, effort=effort, concurrency=concurrency,
                                 on_done=lambda _: progress.advance(task))


if __name__ == "__main__":
    app()
