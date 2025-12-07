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
from collections import defaultdict

from . import __version__
from .runner import BenchmarkRunner, FormatResult, FailureReason, ALL_FORMATS
from .formats import validate_sifr_file, DEFAULT_MAX_CHARS

console = Console()

DEFAULT_TARGET_SIZE_KB = DEFAULT_MAX_CHARS // 1024

STATUS_ICONS = {
    "success": "✅",
    "warning": "⚠️",
    "failed": "❌",
    "skipped": "⏭️",
    "not_supported": "🚫",
}

FOOTNOTE_TEMPLATES = {
    FailureReason.TRUNCATED: "Truncated: {original_kb}KB → {truncated_kb}KB",
    FailureReason.CONTEXT_EXCEEDED: "Exceeds context: {tokens:,} tokens > {limit:,} limit ({model})",
    FailureReason.NOT_CAPTURED: "Not captured: file not found for {format}",
    FailureReason.ID_MISMATCH: "ID mismatch: AXTree uses own IDs, incompatible with ground truth",
    FailureReason.NO_VISION: "Not supported: {model} doesn't support vision",
}


# ============================================================
# PROMPTS - Each format gets native instructions
# ============================================================

EXECUTION_PROMPTS = {
    "sifr": """You are a web automation agent. The page is described in SiFR format.

{context}

TASK: {task}

Instructions:
- Find the element that matches the task
- Return ONLY the element ID (like a002, btn001, input001)
- Element IDs are in ====NODES==== section
- Element text is in ====DETAILS==== section under same ID

Respond with just the element ID, nothing else.

ANSWER:""",

    "html_raw": """You are a web automation agent. The page HTML is below.

{context}

TASK: {task}

Instructions:
- Find the element that matches the task
- Return a CSS selector that uniquely identifies it
- Prefer: #id, [data-testid], .specific-class
- If no good selector, return the exact visible text

Respond with just the selector or text, nothing else.

ANSWER:""",

    "axtree": """You are a web automation agent. The page accessibility tree is below.

{context}

TASK: {task}

Instructions:
- Find the element that matches the task
- Return the exact text/name of the element as shown in the tree
- This will be used for text-based element lookup

Respond with just the element text, nothing else.

ANSWER:""",

    "screenshot": """You are a web automation agent looking at a screenshot.

TASK: {task}

Instructions:
- Find the element that matches the task
- Return the exact visible text of the element
- This will be used for text-based element lookup

Respond with just the element text, nothing else.

ANSWER:""",
}


def format_footnote(reason: FailureReason, details: dict, model: str) -> str:
    template = FOOTNOTE_TEMPLATES.get(reason, str(reason))
    details = details.copy()
    details["model"] = model
    try:
        return template.format(**details)
    except KeyError:
        return f"{reason.value}: {details}"


def render_ground_truth_summary(gt_path: Path, verbose: bool = False):
    if not gt_path.exists():
        return
    with open(gt_path) as f:
        gt = json.load(f)
    tasks = gt.get("tasks", [])
    if not tasks:
        return
    type_counts = {}
    for task in tasks:
        task_type = task.get("type", "unknown").replace("action_", "")
        type_counts[task_type] = type_counts.get(task_type, 0) + 1
    type_str = ", ".join(f"{count} {t}" for t, count in sorted(type_counts.items()))
    console.print(f"  [dim]Tasks: {len(tasks)} ({type_str})[/dim]")
    if verbose:
        for task in tasks:
            q = task.get("question", "")[:50]
            a = task.get("answer", "")
            text = task.get("element_text", "")
            console.print(f"    • {q}... → [cyan]{a}[/cyan] ({text})")


def render_errors(results: list[dict], format_name: str, model: str = None, verbose: bool = False):
    format_results = [r for r in results if r.get("format") == format_name]
    if model:
        format_results = [r for r in format_results if r.get("model") == model]
    if not format_results:
        return
    if all(r.get("error") for r in format_results):
        return
    errors = [r for r in format_results if r.get("score", 0) == 0 and not r.get("error")]
    successes = [r for r in format_results if r.get("score", 0) > 0]
    total = len([r for r in format_results if not r.get("error")])
    error_count = len(errors)
    if total == 0:
        return
    if error_count == 0:
        if verbose:
            console.print(f"  [dim]{format_name}:[/dim] [green]All {total} tasks passed[/green]")
        return
    console.print(f"  [dim]{format_name}:[/dim] [yellow]{error_count}/{total} errors[/yellow]")
    for r in errors:
        task_id = r.get("task_id", "?")
        expected = r.get("expected", "?")
        got = r.get("response", "none") or "none"
        console.print(f"    [red]✗[/red] {task_id}: expected [cyan]{expected}[/cyan], got [yellow]{got}[/yellow]")
    if verbose and successes:
        for r in successes:
            task_id = r.get("task_id", "?")
            expected = r.get("expected", "?")
            console.print(f"    [green]✓[/green] {task_id}: [cyan]{expected}[/cyan]")


def aggregate_by_page(results: list[dict], runner: BenchmarkRunner) -> dict[str, list[FormatResult]]:
    by_page = defaultdict(list)
    for r in results:
        by_page[r["page_id"]].append(r)
    aggregated = {}
    for page_id, page_results in by_page.items():
        aggregated[page_id] = runner.aggregate(page_results)
    return aggregated


def aggregate_by_model(results: list[dict], runner: BenchmarkRunner) -> dict[str, list[FormatResult]]:
    by_model = defaultdict(list)
    for r in results:
        by_model[r.get("model", "unknown")].append(r)
    aggregated = {}
    for model, model_results in by_model.items():
        aggregated[model] = runner.aggregate(model_results)
    return aggregated


def aggregate_by_page_and_model(results: list[dict], runner: BenchmarkRunner) -> dict[str, dict[str, list[FormatResult]]]:
    by_page = defaultdict(lambda: defaultdict(list))
    for r in results:
        by_page[r["page_id"]][r.get("model", "unknown")].append(r)
    aggregated = {}
    for page_id, models in by_page.items():
        aggregated[page_id] = {}
        for model, model_results in models.items():
            aggregated[page_id][model] = runner.aggregate(model_results)
    return aggregated


def render_benchmark_results(site_name: str, results: list[FormatResult], model: str):
    table = Table(title=f"Benchmark Results: {site_name}")
    table.add_column("Format", style="cyan")
    table.add_column("Accuracy", justify="right")
    table.add_column("Tokens", justify="right")
    table.add_column("Latency", justify="right")
    table.add_column("Status", justify="center")
    footnotes = []
    footnote_idx = 1
    for r in results:
        acc = f"{r.accuracy * 100:.1f}%" if r.accuracy is not None else "—"
        tokens = f"{r.tokens:,}" if r.tokens else "—"
        latency = f"{r.latency_ms:,}ms" if r.latency_ms else "—"
        if r.status == "not_supported":
            status = f"{STATUS_ICONS['not_supported']} [{footnote_idx}]"
            footnotes.append((footnote_idx, r.failure_reason, r.failure_details))
            footnote_idx += 1
        elif r.failure_reason:
            status = f"{STATUS_ICONS[r.status]} [{footnote_idx}]"
            footnotes.append((footnote_idx, r.failure_reason, r.failure_details))
            footnote_idx += 1
        else:
            status = STATUS_ICONS[r.status]
        table.add_row(r.format_name, acc, tokens, latency, status)
    console.print(table)
    if footnotes:
        console.print()
        for idx, reason, details in footnotes:
            msg = format_footnote(reason, details, model)
            console.print(f"[dim][{idx}] {msg}[/dim]")


def render_multi_model_results(site_name: str, results_by_model: dict[str, list[FormatResult]]):
    all_formats = set()
    for model_results in results_by_model.values():
        for r in model_results:
            all_formats.add(r.format_name)
    models = list(results_by_model.keys())
    table = Table(title=f"Benchmark Results: {site_name}")
    table.add_column("Format", style="cyan")
    for model in models:
        table.add_column(model, justify="right")
    format_data = {}
    for model, model_results in results_by_model.items():
        for r in model_results:
            if r.format_name not in format_data:
                format_data[r.format_name] = {}
            acc = f"{r.accuracy * 100:.1f}%" if r.accuracy is not None else "—"
            format_data[r.format_name][model] = acc
    def sort_key(fmt):
        first_model = models[0]
        acc_str = format_data.get(fmt, {}).get(first_model, "0%")
        try:
            return -float(acc_str.rstrip("%"))
        except:
            return 0
    for fmt in sorted(format_data.keys(), key=sort_key):
        row = [fmt]
        for model in models:
            row.append(format_data[fmt].get(model, "—"))
        table.add_row(*row)
    console.print(table)


def render_execution_results(results: list[dict], site_name: str):
    """Render execution-based benchmark results."""
    table = Table(title=f"Execution Results: {site_name}")
    table.add_column("Format", style="cyan")
    table.add_column("Success", justify="right", style="green")
    table.add_column("Failed", justify="right", style="red")
    table.add_column("Rate", justify="right")
    table.add_column("Avg Tokens", justify="right")
    table.add_column("Avg Latency", justify="right")
    
    by_format = defaultdict(list)
    for r in results:
        by_format[r.get("format", "unknown")].append(r)
    
    for fmt in ["sifr", "html_raw", "axtree", "screenshot"]:
        if fmt not in by_format:
            continue
        fmt_results = by_format[fmt]
        success = sum(1 for r in fmt_results if r.get("success"))
        failed = len(fmt_results) - success
        rate = f"{success/len(fmt_results)*100:.0f}%" if fmt_results else "—"
        avg_tokens = sum(r.get("tokens", 0) for r in fmt_results) // max(len(fmt_results), 1)
        avg_latency = sum(r.get("latency_ms", 0) for r in fmt_results) // max(len(fmt_results), 1)
        
        table.add_row(
            fmt,
            str(success),
            str(failed),
            rate,
            f"{avg_tokens:,}",
            f"{avg_latency:,}ms"
        )
    
    console.print(table)


def create_run_dir(base_path: str = "./benchmark_runs") -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = Path(base_path) / f"run_{timestamp}"
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
@click.option("--models", "-m", default="gpt-4o-mini", help="Models to test (comma-separated)")
@click.option("--formats", "-f", default=",".join(ALL_FORMATS), help="Formats to test")
@click.option("--run-dir", "-d", required=True, type=click.Path(exists=True), help="Run directory")
@click.option("--runs", "-r", default=1, type=int, help="Runs per test")
@click.option("--target-size", "-s", default=DEFAULT_TARGET_SIZE_KB, type=int, help="Budget in KB")
def run(models, formats, run_dir, runs, target_size):
    """Run benchmark on existing captures."""
    console.print(f"\n[bold blue]🚀 SiFR Benchmark v{__version__}[/bold blue]\n")
    run_path = Path(run_dir)
    model_list = [m.strip() for m in models.split(",")]
    format_list = [f.strip() for f in formats.split(",")]
    target_size_bytes = target_size * 1024
    
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
        base_dir=run_path,
        max_chars=target_size_bytes
    )
    
    with Progress(SpinnerColumn(), TextColumn("[progress.description]{task.description}"), console=console) as progress:
        task = progress.add_task("Running benchmark...", total=None)
        results = runner.run()
        progress.update(task, completed=True)
    
    if len(model_list) > 1:
        by_model = aggregate_by_model(results, runner)
        render_multi_model_results("All Sites", by_model)
    else:
        summary = runner.aggregate(results)
        render_benchmark_results("All Sites", summary, model_list[0])
    
    with open(run_path / "results" / "raw_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    console.print(f"\n[green]✅ Results saved to {run_path}/results/[/green]")


@main.command()
@click.argument("urls", nargs=-1, required=True)
@click.option("--extension", "-e", required=True, help="Path to E2LLM extension")
@click.option("--models", "-m", default="gpt-4o-mini", help="Models to test (comma-separated)")
@click.option("--runs", "-r", default=1, type=int, help="Runs per test")
@click.option("--base-dir", "-b", default="./benchmark_runs", help="Base directory for runs")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output")
@click.option("--target-size", "-s", default=DEFAULT_TARGET_SIZE_KB, type=int, help="Budget in KB for ALL formats")
@click.option("--execution", is_flag=True, help="Use execution-based verification (Playwright)")
def full_benchmark_e2llm(urls, extension, models, runs, base_dir, verbose, target_size, execution):
    """Full benchmark: capture → ground truth → test (isolated run)."""
    import asyncio
    try:
        from .capture_e2llm import capture_multiple
    except ImportError:
        console.print("[red]Error: playwright not installed[/red]")
        return
    
    run_dir = create_run_dir(base_dir)
    model_list = [m.strip() for m in models.split(",")]
    target_size_bytes = target_size * 1024
    multi_model = len(model_list) > 1
    
    console.print(f"[bold blue]🚀 Full Benchmark with E2LLM[/bold blue]")
    console.print(f"Run directory: [cyan]{run_dir}[/cyan]")
    console.print(f"URLs: {len(urls)}")
    console.print(f"Models: [yellow]{', '.join(model_list)}[/yellow]")
    console.print(f"Formats: {', '.join(ALL_FORMATS)}")
    console.print(f"Budget (all formats): [yellow]{target_size}KB[/yellow]")
    if execution:
        console.print(f"Mode: [green]Execution-based (Playwright verification)[/green]")
    
    # Step 1: Capture
    console.print("\n[bold]Step 1/3: Capturing with E2LLM...[/bold]")
    captures_dir = run_dir / "captures"
    results = asyncio.run(capture_multiple(
        urls=list(urls),
        extension_path=extension,
        output_dir=str(captures_dir),
        target_size=target_size_bytes
    ))
    
    captured_pages = []
    for url in urls:
        page_id = url.replace("https://", "").replace("http://", "")
        page_id = page_id.replace("/", "_").replace(".", "_").rstrip("_")
        captured_pages.append(page_id)
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
                render_ground_truth_summary(gt_output, verbose)
        except Exception as e:
            console.print(f"  ⚠️ {page_id}: {e}")
    
    # Step 3: Benchmark
    if execution:
        # Execution-based benchmark with Playwright verification
        console.print("\n[bold]Step 3/3: Running execution-based benchmark...[/bold]")
        bench_results = asyncio.run(run_execution_benchmark(
            run_dir=run_dir,
            urls=list(urls),
            captured_pages=captured_pages,
            model_list=model_list,
            extension=extension,
            target_size_bytes=target_size_bytes,
            verbose=verbose
        ))
        
        # Render execution results
        for page_id in captured_pages:
            page_results = [r for r in bench_results if r.get("page_id") == page_id]
            if page_results:
                site_name = page_id.replace("_", ".")
                render_execution_results(page_results, site_name)
    else:
        # Original scoring-based benchmark
        console.print("\n[bold]Step 3/3: Running benchmark...[/bold]")
        runner = BenchmarkRunner(
            models=model_list,
            formats=ALL_FORMATS,
            runs=runs,
            base_dir=run_dir,
            max_chars=target_size_bytes
        )
        bench_results = runner.run()
        
        if multi_model:
            by_page_model = aggregate_by_page_and_model(bench_results, runner)
            for page_id, models_data in by_page_model.items():
                site_name = page_id.replace("_", ".")
                console.print(f"\n[bold]{site_name}[/bold]")
                render_multi_model_results(site_name, models_data)
                console.print()
            if len(by_page_model) > 1:
                by_model = aggregate_by_model(bench_results, runner)
                render_multi_model_results(f"Combined ({len(by_page_model)} sites)", by_model)
        else:
            by_page = aggregate_by_page(bench_results, runner)
            for page_id, summary in by_page.items():
                site_name = page_id.replace("_", ".")
                page_results = [r for r in bench_results if r.get("page_id") == page_id]
                console.print(f"\n[bold]{site_name}[/bold]")
                for fmt in ALL_FORMATS:
                    render_errors(page_results, fmt, verbose=verbose)
                render_benchmark_results(site_name, summary, model_list[0])
                console.print()
            if len(by_page) > 1:
                combined = runner.aggregate(bench_results)
                render_benchmark_results(f"Combined ({len(by_page)} sites)", combined, model_list[0])
    
    # Save results
    with open(run_dir / "results" / "raw_results.json", "w") as f:
        json.dump(bench_results, f, indent=2, default=str)
    
    # Save metadata
    metadata = {
        "timestamp": datetime.now().isoformat(),
        "urls": list(urls),
        "models": model_list,
        "formats": ALL_FORMATS,
        "pages": captured_pages,
        "target_size_kb": target_size,
        "execution_mode": execution,
        "version": __version__,
    }
    with open(run_dir / "run_meta.json", "w") as f:
        json.dump(metadata, f, indent=2)
    
    console.print(f"\n[green]✅ Benchmark complete![/green]")
    console.print(f"[cyan]Results: {run_dir}[/cyan]")


async def run_execution_benchmark(
    run_dir: Path,
    urls: list,
    captured_pages: list,
    model_list: list,
    extension: str,
    target_size_bytes: int,
    verbose: bool = False
) -> list[dict]:
    """Run execution-based benchmark with Playwright verification."""
    from playwright.async_api import async_playwright
    from .verification import SiFRResolver, verify_response
    from .models import query_model
    from .formats import load_format
    
    results = []
    
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir="./e2llm-chrome-profile",
            headless=False,
            args=[
                f"--disable-extensions-except={extension}",
                f"--load-extension={extension}",
            ]
        )
        page = await context.new_page()
        
        for page_id, url in zip(captured_pages, urls):
            gt_path = run_dir / "ground-truth" / f"{page_id}.json"
            if not gt_path.exists():
                continue
            
            gt = json.loads(gt_path.read_text())
            tasks = gt.get("tasks", [])
            
            if not tasks:
                continue
            
            console.print(f"\n  [bold]{page_id}[/bold]")
            
            # Load page
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(2000)
            except Exception as e:
                console.print(f"    ❌ Failed to load: {e}")
                continue
            
            # Load SiFR resolver
            sifr_path = run_dir / "captures" / "sifr" / f"{page_id}.sifr"
            sifr_resolver = None
            if sifr_path.exists():
                sifr_resolver = SiFRResolver(sifr_path.read_text())
            
            for model in model_list:
                for fmt in ALL_FORMATS:
                    if fmt == "screenshot":
                        continue  # Skip screenshot for now
                    
                    # Load format
                    try:
                        context_str, meta = load_format(
                            page_id, fmt, run_dir,
                            return_meta=True, max_chars=target_size_bytes
                        )
                    except FileNotFoundError:
                        continue
                    
                    for task in tasks:
                        task_id = task.get("id", "?")
                        question = task.get("question", "")
                        task_type = task.get("type", "action_click")
                        target_selector = task.get("target", {}).get("selector")
                        
                        # Get prompt for this format
                        prompt = EXECUTION_PROMPTS.get(fmt, EXECUTION_PROMPTS["html_raw"])
                        full_prompt = prompt.format(context=context_str, task=question)
                        
                        # Query model
                        import time
                        start = time.time()
                        try:
                            response, tokens = query_model(model, full_prompt)
                            latency_ms = int((time.time() - start) * 1000)
                        except Exception as e:
                            results.append({
                                "page_id": page_id,
                                "model": model,
                                "format": fmt,
                                "task_id": task_id,
                                "success": False,
                                "error": str(e),
                                "tokens": 0,
                                "latency_ms": 0,
                            })
                            continue
                        
                        # Clean response
                        response_clean = response.strip().strip('"').strip("'")
                        
                        # Verify response using Playwright
                        success, resolved_selector, error = await verify_response(
                            page, response_clean, fmt, sifr_resolver
                        )
                        
                        result = {
                            "page_id": page_id,
                            "model": model,
                            "format": fmt,
                            "task_id": task_id,
                            "question": question,
                            "response": response_clean,
                            "resolved_selector": resolved_selector,
                            "success": success,
                            "error": error,
                            "tokens": tokens,
                            "latency_ms": latency_ms,
                        }
                        results.append(result)
                        
                        status = "✅" if success else "❌"
                        if verbose:
                            console.print(f"    {status} [{fmt}] {task_id}: {response_clean[:30]}...")
        
        await context.close()
    
    return results


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
    table.add_column("Models", style="yellow")
    table.add_column("Pages", style="blue")
    table.add_column("Best Format", style="green")
    table.add_column("Accuracy", style="magenta")
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
        models_str = ",".join(meta.get("models", ["?"]))
        if isinstance(summary, dict):
            first_model = list(summary.keys())[0]
            model_summary = summary[first_model]
        else:
            model_summary = summary
        if model_summary:
            valid = [s for s in model_summary if s.get("status", "success") == "success"]
            best = max(valid, key=lambda x: float(x["accuracy"].rstrip("%") or 0)) if valid else model_summary[0]
            table.add_row(run_path.name, meta.get("timestamp", "")[:10], models_str, str(len(meta.get("pages", []))), best["format"], best["accuracy"])
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
    table.add_column("Models", style="yellow")
    table.add_column("URLs", style="blue")
    table.add_column("Mode", style="green")
    table.add_column("Status", style="magenta")
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
        models_str = ",".join(meta.get("models", ["?"]))
        mode = "Exec" if meta.get("execution_mode") else "Score"
        table.add_row(
            run_dir.name,
            meta.get("timestamp", "")[:16].replace("T", " "),
            models_str,
            str(len(meta.get("urls", []))),
            mode,
            status
        )
    console.print(table)


@main.command()
def info():
    """Show benchmark information."""
    console.print(f"\n[bold blue]SiFR Benchmark v{__version__}[/bold blue]\n")
    console.print(f"""
[bold]Quick Start:[/bold]
  sifr-bench full-benchmark-e2llm https://example.com -e /path/to/extension

[bold]Execution-based benchmark (recommended):[/bold]
  sifr-bench full-benchmark-e2llm https://example.com -e /path/to/ext --execution

[bold]Multi-model comparison:[/bold]
  sifr-bench full-benchmark-e2llm https://example.com -e /path/to/ext -m gpt-4o-mini,claude-haiku

[bold]Formats tested:[/bold] {', '.join(ALL_FORMATS)}

[bold]Commands:[/bold]
  full-benchmark-e2llm  Full pipeline (capture → ground truth → test)
  run                   Run benchmark on existing captures
  list-runs             Show all benchmark runs
  compare               Compare multiple runs

[bold]Options:[/bold]
  -v, --verbose         Show detailed output
  -m, --models          Models to test (comma-separated, default: gpt-4o-mini)
  -r, --runs            Number of runs per test (default: 1)
  -s, --target-size     Budget in KB for ALL formats (default: {DEFAULT_TARGET_SIZE_KB})
  --execution           Use Playwright verification (objective)

[bold]Benchmark modes:[/bold]
  Score-based (default)  — Compare model response to expected text
  Execution-based        — Verify action via Playwright (--execution)

[bold]Output format:[/bold]
  ✅ — Success (accuracy >= 50% / action succeeded)
  ⚠️  — Warning (accuracy < 50%)
  ❌ — Failed (accuracy = 0% / action failed)
""")


if __name__ == "__main__":
    main()
