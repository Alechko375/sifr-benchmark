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
import time

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
    
    model_list = [m.strip() for m in models.split(",")]
    format_list = [f.strip() for f in formats.split(",")]
    page_list = [p.strip() for p in pages.split(",")] if pages else None
    
    if any("gpt" in m for m in model_list):
        if not os.getenv("OPENAI_API_KEY"):
            console.print("[red]❌ OPENAI_API_KEY not set[/red]")
            return
    
    if any("claude" in m for m in model_list):
        if not os.getenv("ANTHROPIC_API_KEY"):
            console.print("[red]❌ ANTHROPIC_API_KEY not set[/red]")
            return
    
    table = Table(title="Configuration")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="green")
    table.add_row("Models", ", ".join(model_list))
    table.add_row("Formats", ", ".join(format_list))
    table.add_row("Pages", ", ".join(page_list) if page_list else "all")
    table.add_row("Runs", str(runs))
    console.print(table)
    console.print()
    
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
    
    if output:
        output_dir = Path(output)
    else:
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


@main.command()
@click.argument("url")
@click.option("--name", "-n", default=None, help="Base name for output files")
@click.option("--output", "-o", default="datasets/formats", help="Output directory")
def capture(url, name, output):
    """Capture a page in all formats (SiFR, HTML, Screenshot, AXTree)."""
    from .capture import capture_page, check_playwright
    
    if not check_playwright():
        console.print("[red]Playwright not installed![/red]")
        console.print("Run: pip install playwright && playwright install chromium")
        return
    
    if not name:
        from urllib.parse import urlparse
        name = urlparse(url).netloc.replace(".", "_").replace("www_", "")
    
    console.print(f"\n[bold]Capturing: {url}[/bold]\n")
    
    result = capture_page(url, Path(output), name)
    
    if result.error:
        console.print(f"[red]Error: {result.error}[/red]")
        return
    
    console.print(f"[green]✅ SiFR:[/green] {result.sifr_path}")
    console.print(f"[green]✅ HTML:[/green] {result.html_path}")
    console.print(f"[green]✅ Screenshot:[/green] {result.screenshot_path}")
    console.print(f"[green]✅ AXTree:[/green] {result.axtree_path}")
    console.print(f"\n[bold]Done! Run:[/bold] sifr-bench run --formats sifr,html_raw")


@main.command()
@click.argument("page_name")
@click.option("--base-dir", "-d", default=".", help="Base directory")
def ground_truth(page_name, base_dir):
    """Generate ground truth for a page using GPT-4o Vision."""
    from .ground_truth import generate_ground_truth_for_page
    
    console.print(f"\n[bold]Generating ground truth for: {page_name}[/bold]\n")
    
    result = generate_ground_truth_for_page(page_name, Path(base_dir))
    
    if "error" in result:
        console.print(f"[red]Error: {result['error']}[/red]")
        return
    
    console.print("[green]✅ Ground truth generated![/green]")
    console.print(f"\nTitle: {result.get('title', 'N/A')}")
    console.print(f"Navigation: {result.get('navigation', {}).get('items', [])}")
    console.print(f"Primary button: {result.get('primary_button', {}).get('text', 'N/A')}")
    
    if result.get("_meta", {}).get("tokens"):
        console.print(f"\nTokens used: {result['_meta']['tokens']}")


@main.command()
@click.argument("url")
@click.argument("results_file", type=click.Path(exists=True))
@click.option("--headless/--no-headless", default=True, help="Run browser in headless mode")
def verify(url, results_file, headless):
    """Verify benchmark results by executing actions."""
    from .verify import verify_from_file
    
    console.print(f"\n[bold]Verifying results: {results_file}[/bold]\n")
    
    results = verify_from_file(url, Path(results_file), headless)
    
    format_stats = {}
    for r in results:
        if r.format not in format_stats:
            format_stats[r.format] = {"success": 0, "total": 0}
        format_stats[r.format]["total"] += 1
        if r.action_success:
            format_stats[r.format]["success"] += 1
    
    table = Table(title="Verification Results")
    table.add_column("Format", style="cyan")
    table.add_column("Success", style="green")
    table.add_column("Total", style="yellow")
    table.add_column("Rate", style="magenta")
    
    for fmt, stats in format_stats.items():
        rate = f"{stats['success']/stats['total']*100:.1f}%" if stats['total'] > 0 else "N/A"
        table.add_row(fmt, str(stats['success']), str(stats['total']), rate)
    
    console.print(table)


@main.command()
@click.argument("url")
@click.option("--name", "-n", default=None, help="Page name")
@click.option("--models", "-m", default="gpt-4o-mini", help="Models to test")
@click.option("--delay", "-d", default=60, type=int, help="Delay between heavy formats (seconds)")
def full_benchmark(url, name, models, delay):
    """Run full benchmark: capture → ground truth → test → verify."""
    from .capture import capture_page
    from .ground_truth import generate_ground_truth_for_page
    
    if not name:
        from urllib.parse import urlparse
        name = urlparse(url).netloc.replace(".", "_").replace("www_", "")
    
    console.print(f"\n[bold blue]🚀 Full Benchmark: {url}[/bold blue]\n")
    
    console.print("[bold]Step 1/4: Capturing page...[/bold]")
    result = capture_page(url, Path("datasets/formats"), name)
    if result.error:
        console.print(f"[red]Capture error: {result.error}[/red]")
        return
    console.print("[green]✅ Captured[/green]\n")
    
    console.print("[bold]Step 2/4: Generating ground truth (GPT-4o Vision)...[/bold]")
    gt = generate_ground_truth_for_page(name)
    if "error" in gt:
        console.print(f"[red]Ground truth error: {gt['error']}[/red]")
        return
    console.print("[green]✅ Ground truth generated[/green]\n")
    
    console.print("[bold]Step 3/4: Running benchmark...[/bold]")
    
    formats = ["sifr", "axtree", "html_raw"]
    all_results = []
    
    for i, fmt in enumerate(formats):
        console.print(f"  Testing format: {fmt}")
        
        runner = BenchmarkRunner(
            models=models.split(","),
            formats=[fmt],
            pages=[name],
            runs=1
        )
        results = runner.run()
        all_results.extend(results)
        
        if i < len(formats) - 1:
            if fmt == "html_raw" or formats[i+1] == "html_raw":
                console.print(f"  [yellow]Waiting {delay}s for rate limit...[/yellow]")
                time.sleep(delay)
            else:
                time.sleep(5)
    
    console.print("[green]✅ Benchmark complete[/green]\n")
    
    console.print("[bold]Step 4/4: Results[/bold]")
    
    table = Table(title="Full Benchmark Results")
    table.add_column("Format", style="cyan")
    table.add_column("Avg Tokens", style="yellow")
    table.add_column("Avg Latency", style="blue")
    
    format_data = {}
    for r in all_results:
        fmt = r.get("format")
        if fmt not in format_data:
            format_data[fmt] = {"tokens": [], "latency": []}
        if r.get("tokens"):
            format_data[fmt]["tokens"].append(r["tokens"])
        if r.get("latency_ms"):
            format_data[fmt]["latency"].append(r["latency_ms"])
    
    for fmt, data in format_data.items():
        avg_tokens = int(sum(data["tokens"]) / len(data["tokens"])) if data["tokens"] else 0
        avg_latency = f"{int(sum(data['latency']) / len(data['latency']))}ms" if data["latency"] else "N/A"
        table.add_row(fmt, str(avg_tokens), avg_latency)
    
    console.print(table)
    console.print(f"\n[green]✅ Full benchmark complete![/green]")


@main.command()
@click.argument("urls", nargs=-1, required=True)
@click.option("--extension", "-e", required=True, help="Path to E2LLM extension folder")
@click.option("--output", "-o", default="./datasets/formats", help="Output directory")
@click.option("--profile", default="./e2llm-chrome-profile", help="Chrome profile directory")
def capture_e2llm(urls, extension, output, profile):
    """Capture pages using E2LLM extension API."""
    import asyncio
    
    try:
        from .capture_e2llm import capture_multiple
    except ImportError:
        console.print("[red]Error: playwright not installed[/red]")
        console.print("Run: pip install playwright && playwright install chromium")
        return
    
    console.print(f"[bold]🚀 E2LLM Capture[/bold]")
    console.print(f"Extension: {extension}")
    console.print(f"URLs: {len(urls)}")
    
    results = asyncio.run(capture_multiple(
        urls=list(urls),
        extension_path=extension,
        output_dir=output,
        user_data_dir=profile
    ))
    
    console.print(f"\n[green]✅ Captured {len(results)} pages[/green]")


@main.command()
@click.argument("urls", nargs=-1, required=True)
@click.option("--extension", "-e", required=True, help="Path to E2LLM extension folder")
@click.option("--models", "-m", default="gpt-4o-mini", help="Models to test")
@click.option("--runs", "-r", default=1, type=int, help="Number of runs per test")
def full_benchmark_e2llm(urls, extension, models, runs):
    """Full benchmark using E2LLM extension for capture."""
    import asyncio
    
    try:
        from .capture_e2llm import capture_multiple
    except ImportError:
        console.print("[red]Error: playwright not installed[/red]")
        console.print("Run: pip install playwright && playwright install chromium")
        return
    
    console.print(f"[bold]🚀 Full Benchmark with E2LLM[/bold]")
    console.print(f"URLs: {len(urls)}")
    
    console.print("\n[bold]Step 1/3: Capturing with E2LLM...[/bold]")
    results = asyncio.run(capture_multiple(
        urls=list(urls),
        extension_path=extension,
        output_dir="./datasets/formats"
    ))
    console.print(f"[green]✅ Captured {len(results)} pages[/green]")
    
    console.print("\n[bold]Step 2/3: Generating ground truth...[/bold]")
    from .ground_truth import generate_ground_truth_for_page
    for url in urls:
        page_id = url.replace("https://", "").replace("http://", "")
        page_id = page_id.replace("/", "_").replace(".", "_").rstrip("_")
        try:
            generate_ground_truth_for_page(page_id)
            console.print(f"  ✅ {page_id}")
        except Exception as e:
            console.print(f"  ⚠️ {page_id}: {e}")
    
    console.print("\n[bold]Step 3/3: Running benchmark...[/bold]")
    model_list = [m.strip() for m in models.split(",")]
    
    runner = BenchmarkRunner(
        models=model_list,
        formats=["sifr", "html_raw", "axtree"],
        runs=runs
    )
    
    bench_results = runner.run()
    summary = runner.aggregate(bench_results)
    
    table = Table(title="Benchmark Results")
    table.add_column("Format")
    table.add_column("Accuracy")
    table.add_column("Avg Tokens")
    table.add_column("Avg Latency")
    
    for row in summary:
        table.add_row(
            row["format"],
            row["accuracy"],
            str(row["avg_tokens"]),
            row["avg_latency"]
        )
    
    console.print(table)
    console.print("\n[green]✅ Benchmark complete![/green]")


if __name__ == "__main__":
    main()
