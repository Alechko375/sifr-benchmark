"""
CLI interface for SiFR Benchmark.

Usage:
    sifr-bench run --models gpt-4o,claude-sonnet --formats sifr,html
    sifr-bench compare results/run1 results/run2
    sifr-bench validate examples/
"""

import click
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
import json
import os

from . import __version__
from .runner import BenchmarkRunner
from .formats import validate_sifr_file

console = Console()


@click.group()
@click.version_option(version=__version__)
def main():
    """SiFR Benchmark - Evaluate LLM understanding of web UI."""
    pass


@main.command()
@click.option("--models", "-m", default="gpt-4o-mini", help="Models to test (comma-separated)")
@click.option("--formats", "-f", default="sifr,html_raw", help="Formats to test (comma-separated)")
@click.option("--pages", "-p", default=None, help="Pages to test (comma-separated)")
@click.option("--runs", "-r", default=3, type=int, help="Runs per configuration")
@click.option("--output", "-o", default=None, help="Output directory")
@click.option("--tasks", "-t", default=None, help="Path to tasks.json")
def run(models, formats, pages, runs, output, tasks):
    """Run the benchmark."""
    
    console.print(f"\n[bold blue]🚀 SiFR Benchmark v{__version__}[/bold blue]\n")
    
    # Parse inputs
    model_list = [m.strip() for m in models.split(",")]
    format_list = [f.strip() for f in formats.split(",")]
    page_list = [p.strip() for p in pages.split(",")] if pages else None
    
    # Check API keys
    if any("gpt" in m for m in model_list):
        if not os.getenv("OPENAI_API_KEY"):
            console.print("[red]❌ OPENAI_API_KEY not set[/red]")
            return
    
    if any("claude" in m for m in model_list):
        if not os.getenv("ANTHROPIC_API_KEY"):
            console.print("[red]❌ ANTHROPIC_API_KEY not set[/red]")
            return
    
    # Display config
    table = Table(title="Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Models", ", ".join(model_list))
    table.add_row("Formats", ", ".join(format_list))
    table.add_row("Pages", ", ".join(page_list) if page_list else "all")
    table.add_row("Runs", str(runs))
    console.print(table)
    console.print()
    
    # Run benchmark
    runner = BenchmarkRunner(
        models=model_list,
        formats=format_list,
        pages=page_list,
        runs=runs,
        tasks_path=tasks,
    )
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Running benchmark...", total=None)
        results = runner.run()
        progress.update(task, completed=True)
    
    # Display results
    summary = runner.aggregate(results)
    
    results_table = Table(title="Results")
    results_table.add_column("Model", style="cyan")
    results_table.add_column("Format", style="magenta")
    results_table.add_column("Accuracy", style="green")
    results_table.add_column("Avg Tokens", style="yellow")
    results_table.add_column("Avg Latency", style="blue")
    
    for row in summary:
        results_table.add_row(
            row["model"],
            row["format"],
            row["accuracy"],
            str(row["avg_tokens"]),
            row["avg_latency"],
        )
    
    console.print(results_table)
    
    # Save results
    if output:
        output_dir = Path(output)
    else:
        import time
        output_dir = Path(f"results/run_{int(time.time())}")
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    with open(output_dir / "raw_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    with open(output_dir / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    
    console.print(f"\n[green]✅ Results saved to {output_dir}/[/green]")


@main.command()
@click.argument("path", type=click.Path(exists=True))
def validate(path):
    """Validate SiFR files."""
    
    console.print(f"\n[bold]Validating: {path}[/bold]\n")
    
    path = Path(path)
    files = list(path.glob("**/*.sifr")) if path.is_dir() else [path]
    
    valid = 0
    invalid = 0
    
    for f in files:
        try:
            errors = validate_sifr_file(f)
            if errors:
                console.print(f"[red]❌ {f.name}[/red]")
                for err in errors:
                    console.print(f"   {err}")
                invalid += 1
            else:
                console.print(f"[green]✅ {f.name}[/green]")
                valid += 1
        except Exception as e:
            console.print(f"[red]❌ {f.name}: {e}[/red]")
            invalid += 1
    
    console.print(f"\n[bold]Summary: {valid} valid, {invalid} invalid[/bold]")


@main.command()
@click.argument("result_dirs", nargs=-1, type=click.Path(exists=True))
def compare(result_dirs):
    """Compare multiple benchmark results."""
    
    if len(result_dirs) < 2:
        console.print("[red]Need at least 2 result directories to compare[/red]")
        return
    
    console.print(f"\n[bold]Comparing {len(result_dirs)} results[/bold]\n")
    
    summaries = []
    for d in result_dirs:
        summary_path = Path(d) / "summary.json"
        if summary_path.exists():
            with open(summary_path) as f:
                summaries.append({"dir": d, "data": json.load(f)})
    
    # Build comparison table
    table = Table(title="Comparison")
    table.add_column("Run", style="cyan")
    table.add_column("Best Model", style="green")
    table.add_column("Best Format", style="magenta")
    table.add_column("Top Accuracy", style="yellow")
    
    for s in summaries:
        if s["data"]:
            best = max(s["data"], key=lambda x: float(x["accuracy"].rstrip("%")))
            table.add_row(
                Path(s["dir"]).name,
                best["model"],
                best["format"],
                best["accuracy"],
            )
    
    console.print(table)


@main.command()
def info():
    """Show benchmark information."""
    
    console.print(f"\n[bold blue]SiFR Benchmark v{__version__}[/bold blue]\n")
    
    info_text = """
[bold]What is SiFR?[/bold]
Structured Interface Format for Representation - a compact way 
to describe web UI for LLMs. 70% fewer tokens, 2x accuracy.

[bold]Supported Models:[/bold]
  • gpt-4o, gpt-4o-mini (OpenAI)
  • claude-sonnet, claude-haiku (Anthropic)

[bold]Supported Formats:[/bold]
  • sifr - Structured semantic format
  • html_raw - Complete HTML
  • html_clean - HTML without scripts/styles  
  • axtree - Accessibility tree

[bold]Quick Start:[/bold]
  export OPENAI_API_KEY=sk-...
  sifr-bench run --models gpt-4o-mini --formats sifr,html_raw

[bold]Links:[/bold]
  GitHub: https://github.com/Alechko375/sifr-benchmark
  Spec:   https://github.com/Alechko375/sifr-benchmark/blob/main/SPEC.md
"""
    console.print(info_text)


if __name__ == "__main__":
    main()
