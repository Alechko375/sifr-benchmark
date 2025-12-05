"""
CLI interface for SiFR Benchmark.
Each benchmark run creates an isolated directory with all data.
"""

import click
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
import json
import os
from datetime import datetime

from . import __version__
from .runner import BenchmarkRunner
from .formats import validate_sifr_file

console = Console()


def create_run_dir(base_path: str = "./benchmark_runs") -> Path:
    """Create isolated run directory with timestamp."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = Path(base_path) / f"run_{timestamp}"
    
    # Create subdirectories
    (run_dir / "captures" / "sifr").mkdir(parents=True, exist_ok=True)
    (run_dir / "captures" / "html").mkdir(parents=True, exist_ok=True)
    (run_dir / "captures" / "axtree").mkdir(parents=True, exist_ok=True)
    (run_dir / "captures" / "screenshots").mkdir(parents=True, exist_ok=True)
    (run_dir / "ground-truth").mkdir(parents=True, exist_ok=True)
    (run_dir / "results").mkdir(parents=True, exist_ok=True)
    
    return run_dir


@click.group()
@click.version_option(version=__version__)
def main():
    """SiFR Benchmark - Evaluate LLM understanding of web UI."""
    pass


@main.command()
@click.option("--models", "-m", default="gpt-4o-mini", help="Models to test")
@click.option("--formats", "-f", default="sifr,html_raw,axtree", help="Formats to test")
@click.option("--run-dir", "-d", required=True, type=click.Path(exists=True), help="Run directory with captures")
@click.option("--runs", "-r", default=1, type=int, help="Runs per test")
def run(models, formats, run_dir, runs):
    """Run benchmark on existing captures."""
    
    console.print(f"\n[bold blue]🚀 SiFR Benchmark v{__version__}[/bold blue]\n")
    
    run_path = Path(run_dir)
    model_list = [m.strip() for m in models.split(",")]
    format_list = [f.strip() for f in formats.split(",")]
    
    # Check API keys
    if any("gpt" in m for m in model_list) and not os.getenv("OPENAI_API_KEY"):
        console.print("[red]❌ OPENAI_API_KEY not set[/red]")
        return
    
    if any("claude" in m for m in model_list) and not os.getenv("ANTHROPIC_API_KEY"):
        console.print("[red]❌ ANTHROPIC_API_KEY not set[/red]")
        return
    
    runner = BenchmarkRunner(
        models=model_list,
        formats=format_list,
        runs=runs,
        base_dir=run_path
    )
    
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
        task = progress.add_task("Running benchmark...", total=None)
        results = runner.run()
        progress.update(task, completed=True)
    
    summary = runner.aggregate(results)
    
    # Display results
    table = Table(title="Benchmark Results")
    table.add_column("Format", style="cyan")
    table.add_column("Accuracy", style="green")
    table.add_column("Avg Tokens", style="yellow")
    table.add_column("Avg Latency", style="blue")
    
    for row in summary:
        table.add_row(row["format"], row["accuracy"], str(row["avg_tokens"]), row["avg_latency"])
    
    console.print(table)
    
    # Save results
    with open(run_path / "results" / "raw_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    with open(run_path / "results" / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    
    console.print(f"\n[green]✅ Results saved to {run_path}/results/[/green]")


@main.command()
@click.argument("urls", nargs=-1, required=True)
@click.option("--extension", "-e", required=True, help="Path to E2LLM extension")
@click.option("--models", "-m", default="gpt-4o-mini", help="Models to test")
@click.option("--runs", "-r", default=1, type=int, help="Runs per test")
@click.option("--base-dir", "-b", default="./benchmark_runs", help="Base directory for runs")
def full_benchmark_e2llm(urls, extension, models, runs, base_dir):
    """Full benchmark: capture → ground truth → test (isolated run)."""
    import asyncio
    
    try:
        from .capture_e2llm import capture_multiple
    except ImportError:
        console.print("[red]Error: playwright not installed[/red]")
        return
    
    # Create isolated run directory
    run_dir = create_run_dir(base_dir)
    
    console.print(f"[bold blue]🚀 Full Benchmark with E2LLM[/bold blue]")
    console.print(f"Run directory: [cyan]{run_dir}[/cyan]")
    console.print(f"URLs: {len(urls)}")
    
    # Step 1: Capture
    console.print("\n[bold]Step 1/3: Capturing with E2LLM...[/bold]")
    
    captures_dir = run_dir / "captures"
    results = asyncio.run(capture_multiple(
        urls=list(urls),
        extension_path=extension,
        output_dir=str(captures_dir)
    ))
    
    captured_pages = []
    for url in urls:
        page_id = url.replace("https://", "").replace("http://", "")
        page_id = page_id.replace("/", "_").replace(".", "_").rstrip("_")
        captured_pages.append(page_id)
        console.print(f"  ✅ Saved: {page_id}")
    
    console.print(f"[green]✅ Captured {len(results)} pages[/green]")
    
    # Step 2: Ground truth
    console.print("\n[bold]Step 2/3: Generating ground truth...[/bold]")
    from .ground_truth import generate_ground_truth
    
    for page_id in captured_pages:
        screenshot_path = captures_dir / "screenshots" / f"{page_id}.png"
        sifr_path = captures_dir / "sifr" / f"{page_id}.sifr"
        gt_output = run_dir / "ground-truth" / f"{page_id}.json"
        
        if not screenshot_path.exists():
            console.print(f"  ⚠️ {page_id}: screenshot not found")
            continue
            
        if not sifr_path.exists():
            console.print(f"  ⚠️ {page_id}: sifr not found")
            continue
        
        try:
            result = generate_ground_truth(screenshot_path, sifr_path, gt_output)
            if "error" in result:
                console.print(f"  ⚠️ {page_id}: {result['error']}")
            else:
                console.print(f"  ✅ {page_id}")
        except Exception as e:
            console.print(f"  ⚠️ {page_id}: {e}")
    
    # Step 3: Benchmark
    console.print("\n[bold]Step 3/3: Running benchmark...[/bold]")
    model_list = [m.strip() for m in models.split(",")]
    
    runner = BenchmarkRunner(
        models=model_list,
        formats=["sifr", "html_raw", "axtree"],
        runs=runs,
        base_dir=run_dir
    )
    
    bench_results = runner.run()
    summary = runner.aggregate(bench_results)
    
    # Display results
    table = Table(title="Benchmark Results")
    table.add_column("Format", style="cyan")
    table.add_column("Accuracy", style="green")
    table.add_column("Avg Tokens", style="yellow")
    table.add_column("Avg Latency", style="blue")
    
    for row in summary:
        table.add_row(row["format"], row["accuracy"], str(row["avg_tokens"]), row["avg_latency"])
    
    console.print(table)
    
    # Save results
    with open(run_dir / "results" / "raw_results.json", "w") as f:
        json.dump(bench_results, f, indent=2, default=str)
    
    with open(run_dir / "results" / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    
    # Save run metadata
    metadata = {
        "timestamp": datetime.now().isoformat(),
        "urls": list(urls),
        "models": model_list,
        "formats": ["sifr", "html_raw", "axtree"],
        "pages": captured_pages
    }
    with open(run_dir / "run_meta.json", "w") as f:
        json.dump(metadata, f, indent=2)
    
    console.print(f"\n[green]✅ Benchmark complete![/green]")
    console.print(f"[cyan]Results: {run_dir}[/cyan]")


@main.command()
@click.argument("path", type=click.Path(exists=True))
def validate(path):
    """Validate SiFR files."""
    path = Path(path)
    files = list(path.glob("**/*.sifr")) if path.is_dir() else [path]
    
    valid = invalid = 0
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
@click.argument("run_dirs", nargs=-1, type=click.Path(exists=True))
def compare(run_dirs):
    """Compare multiple benchmark runs."""
    if len(run_dirs) < 2:
        console.print("[red]Need at least 2 run directories[/red]")
        return
    
    table = Table(title="Run Comparison")
    table.add_column("Run", style="cyan")
    table.add_column("Date", style="dim")
    table.add_column("Pages", style="yellow")
    table.add_column("Best Format", style="green")
    table.add_column("Accuracy", style="magenta")
    table.add_column("Tokens", style="blue")
    
    for d in run_dirs:
        run_path = Path(d)
        summary_path = run_path / "results" / "summary.json"
        meta_path = run_path / "run_meta.json"
        
        if not summary_path.exists():
            continue
        
        with open(summary_path) as f:
            summary = json.load(f)
        
        meta = {}
        if meta_path.exists():
            with open(meta_path) as f:
                meta = json.load(f)
        
        if summary:
            best = max(summary, key=lambda x: float(x["accuracy"].rstrip("%") or 0))
            table.add_row(
                run_path.name,
                meta.get("timestamp", "")[:10],
                str(len(meta.get("pages", []))),
                best["format"],
                best["accuracy"],
                str(best["avg_tokens"])
            )
    
    console.print(table)


@main.command()
def list_runs():
    """List all benchmark runs."""
    runs_dir = Path("./benchmark_runs")
    if not runs_dir.exists():
        console.print("[yellow]No runs found[/yellow]")
        return
    
    table = Table(title="Benchmark Runs")
    table.add_column("Run", style="cyan")
    table.add_column("Date", style="dim")
    table.add_column("URLs", style="yellow")
    table.add_column("Status", style="green")
    
    for run_dir in sorted(runs_dir.iterdir(), reverse=True):
        if not run_dir.is_dir():
            continue
        
        meta_path = run_dir / "run_meta.json"
        results_path = run_dir / "results" / "summary.json"
        
        meta = {}
        if meta_path.exists():
            with open(meta_path) as f:
                meta = json.load(f)
        
        status = "✅ Complete" if results_path.exists() else "⏳ Partial"
        
        table.add_row(
            run_dir.name,
            meta.get("timestamp", "")[:16].replace("T", " "),
            str(len(meta.get("urls", []))),
            status
        )
    
    console.print(table)


@main.command()
def info():
    """Show benchmark information."""
    console.print(f"\n[bold blue]SiFR Benchmark v{__version__}[/bold blue]\n")
    console.print("""
[bold]Quick Start:[/bold]
  sifr-bench full-benchmark-e2llm https://news.ycombinator.com -e /path/to/extension

[bold]Commands:[/bold]
  full-benchmark-e2llm  Full pipeline (capture → ground truth → test)
  run                   Run benchmark on existing captures
  list-runs             Show all benchmark runs
  compare               Compare multiple runs

[bold]Run Structure:[/bold]
  benchmark_runs/run_YYYYMMDD_HHMMSS/
  ├── captures/
  │   ├── sifr/
  │   ├── html/
  │   ├── axtree/
  │   └── screenshots/
  ├── ground-truth/
  ├── results/
  └── run_meta.json
""")


if __name__ == "__main__":
    main()
