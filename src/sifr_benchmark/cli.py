"""
CLI interface for SiFR Benchmark.
Refactored: single page session (capture → query → verify without reload).
"""

import click
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
import json
import os
import time
import logging
from datetime import datetime
from collections import defaultdict
from typing import Optional

from . import __version__
from .runner import ALL_FORMATS
from .formats import DEFAULT_MAX_CHARS

console = Console()
logger = logging.getLogger("sifr.benchmark")

DEFAULT_TARGET_SIZE_KB = DEFAULT_MAX_CHARS // 1024

# ============================================================
# PROMPTS
# ============================================================

UNDERSTAND_PROMPTS = {
    "sifr": """Page structure as JSON. Each element has "id", "tag", "text", "bbox", "children".

{context}

QUESTION: {question}

Analyze the structure and answer specifically. Just the answer, nothing else.

ANSWER:""",

    "html_raw": """Page HTML:

{context}

QUESTION: {question}

Analyze the HTML and answer specifically. Just the answer, nothing else.

ANSWER:""",

    "axtree": """Accessibility tree:

{context}

QUESTION: {question}

Analyze the tree and answer specifically. Just the answer, nothing else.

ANSWER:""",

    "screenshot": """QUESTION: {question}

Analyze what you see and answer specifically. Just the answer, nothing else.

ANSWER:""",
}

ACTION_PROMPTS = {
    "sifr": """Page structure as JSON. Each element has "id" field (like "a001", "btn002").

{context}

Based on: {understand_answer}

TASK: {action_question}

Return ONLY the element "id" (e.g., a001, btn002). Nothing else.

ANSWER:""",

    "html_raw": """Page HTML:

{context}

Based on: {understand_answer}

TASK: {action_question}

Return a CSS selector or exact visible text. Nothing else.

ANSWER:""",

    "axtree": """Accessibility tree:

{context}

Based on: {understand_answer}

TASK: {action_question}

Return the exact element text/name. Nothing else.

ANSWER:""",

    "screenshot": """Based on: {understand_answer}

TASK: {action_question}

Return the exact visible text of the element. Nothing else.

ANSWER:""",
}


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


def url_to_page_id(url: str) -> str:
    """Convert URL to filesystem-safe page_id."""
    page_id = url.replace("https://", "").replace("http://", "")
    page_id = page_id.replace("/", "_").replace(".", "_").rstrip("_")
    return page_id


def render_compound_results(results: list[dict], site_name: str):
    """Render compound task results."""
    table = Table(title=f"Understanding + Action Results: {site_name}")
    table.add_column("Format", style="cyan")
    table.add_column("Understand", justify="right", style="yellow")
    table.add_column("Act", justify="right", style="blue")
    table.add_column("Combined", justify="right", style="green")
    table.add_column("Tokens", justify="right")
    
    by_format = defaultdict(list)
    for r in results:
        by_format[r.get("format", "unknown")].append(r)
    
    for fmt in ALL_FORMATS:
        if fmt not in by_format:
            continue
        fmt_results = by_format[fmt]
        
        understand_correct = sum(1 for r in fmt_results if r.get("understand_correct"))
        act_correct = sum(1 for r in fmt_results if r.get("act_success"))
        combined = sum(1 for r in fmt_results if r.get("understand_correct") and r.get("act_success"))
        total = len(fmt_results)
        
        u_rate = f"{understand_correct/total*100:.0f}%" if total else "—"
        a_rate = f"{act_correct/total*100:.0f}%" if total else "—"
        c_rate = f"{combined/total*100:.0f}%" if total else "—"
        avg_tokens = sum(r.get("tokens", 0) for r in fmt_results) // max(total, 1)
        
        table.add_row(fmt, u_rate, a_rate, c_rate, f"{avg_tokens:,}")
    
    console.print(table)


def render_verification_details(results: list[dict]):
    """Render detailed verification breakdown."""
    table = Table(title="Verification Details (Act Failures)")
    table.add_column("Task", style="cyan")
    table.add_column("Format", style="yellow")
    table.add_column("Response", style="dim")
    table.add_column("Stage", style="red")
    table.add_column("Error", style="red")
    
    for r in results:
        if r.get("act_success"):
            continue
        details = r.get("verification_details", {})
        if not details:
            continue
        
        table.add_row(
            r.get("task_id", "?"),
            r.get("format", "?"),
            (details.get("response_raw") or "")[:25] + "...",
            details.get("error_stage", "?"),
            (details.get("error") or "")[:40]
        )
    
    if table.row_count > 0:
        console.print(table)


@click.group()
@click.version_option(version=__version__)
def main():
    """SiFR Benchmark - Evaluate LLM understanding of web UI."""
    pass


@main.command()
@click.argument("urls", nargs=-1, required=True)
@click.option("--extension", "-e", required=True, help="Path to E2LLM extension")
@click.option("--models", "-m", default="gpt-4o-mini", help="Models to test (comma-separated)")
@click.option("--mode", type=click.Choice(["compound", "dev", "design", "combined"]), default="compound")
@click.option("--base-dir", "-b", default="./benchmark_runs", help="Base directory for runs")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output")
@click.option("--target-size", "-s", default=DEFAULT_TARGET_SIZE_KB, type=int, help="Budget in KB")
@click.option("--debug", is_flag=True, help="Enable debug logging for verification")
def full_benchmark_e2llm(urls, extension, models, mode, base_dir, verbose, target_size, debug):
    """Full benchmark: capture → ground truth → test (single page session)."""
    import asyncio
    
    if debug:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s [%(name)s] %(message)s",
            datefmt="%H:%M:%S"
        )
    
    run_dir = create_run_dir(base_dir)
    model_list = [m.strip() for m in models.split(",")]
    target_size_bytes = target_size * 1024
    
    console.print(f"[bold blue]🚀 Full Benchmark (Single Session)[/bold blue]")
    console.print(f"Run directory: [cyan]{run_dir}[/cyan]")
    console.print(f"URLs: {len(urls)}")
    console.print(f"Models: [yellow]{', '.join(model_list)}[/yellow]")
    console.print(f"Budget: [yellow]{target_size}KB[/yellow]")
    console.print(f"Mode: [green]{mode}[/green]")
    
    if mode == "compound":
        results = asyncio.run(run_compound_benchmark_live(
            run_dir=run_dir,
            urls=list(urls),
            models=model_list,
            extension_path=extension,
            target_size=target_size_bytes,
            verbose=verbose,
            debug=debug,
        ))
        
        # Group by page and render
        by_page = defaultdict(list)
        for r in results:
            by_page[r.get("page_id", "unknown")].append(r)
        
        for page_id, page_results in by_page.items():
            render_compound_results(page_results, page_id.replace("_", "."))
            if verbose:
                render_verification_details(page_results)
    else:
        console.print(f"[yellow]Mode '{mode}' not yet refactored for single session[/yellow]")
        return
    
    # Save results
    with open(run_dir / "results" / "raw_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    metadata = {
        "timestamp": datetime.now().isoformat(),
        "urls": list(urls),
        "models": model_list,
        "formats": ALL_FORMATS,
        "target_size_kb": target_size,
        "mode": mode,
        "version": __version__,
        "single_session": True,
    }
    with open(run_dir / "run_meta.json", "w") as f:
        json.dump(metadata, f, indent=2)
    
    console.print(f"\n[green]✅ Benchmark complete![/green]")
    console.print(f"[cyan]Results: {run_dir}[/cyan]")


async def run_compound_benchmark_live(
    run_dir: Path,
    urls: list[str],
    models: list[str],
    extension_path: str,
    target_size: int,
    verbose: bool = False,
    debug: bool = False,
) -> list[dict]:
    """
    Single-session benchmark: capture → query → verify on same page.
    No reload between capture and verification.
    """
    from playwright.async_api import async_playwright
    from .capture_e2llm import capture_with_e2llm
    from .verification import SiFRResolver, verify_response, setup_verbose_logging
    from .models import query_model
    from .scoring import score_compound_task
    from .ground_truth import generate_ground_truth_from_data
    
    if debug:
        setup_verbose_logging()
    
    results = []
    captures_dir = run_dir / "captures"
    
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir="./e2llm-chrome-profile",
            headless=False,
            args=[
                f"--disable-extensions-except={extension_path}",
                f"--load-extension={extension_path}",
            ]
        )
        page = await context.new_page()
        
        for url in urls:
            page_id = url_to_page_id(url)
            console.print(f"\n[bold]━━━ {url} ━━━[/bold]")
            
            # ════════════════════════════════════════════
            # STEP 1: Load page ONCE
            # ════════════════════════════════════════════
            console.print("  [dim]Loading page...[/dim]")
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                await page.wait_for_timeout(3000)
            except Exception as e:
                console.print(f"  [red]❌ Failed to load: {e}[/red]")
                continue
            
            # ════════════════════════════════════════════
            # STEP 2: Capture all formats (same page state)
            # ════════════════════════════════════════════
            console.print("  [dim]Capturing formats...[/dim]")
            
            # SiFR via extension
            try:
                sifr_result = await capture_with_e2llm(page, target_size=target_size)
                sifr_content = sifr_result.get("sifr", "")
                sifr_data = json.loads(sifr_content) if sifr_content else {}
            except Exception as e:
                console.print(f"  [yellow]⚠️ SiFR capture failed: {e}[/yellow]")
                sifr_content = ""
                sifr_data = {}
            
            # HTML
            html_content = await page.content()
            
            # AXTree
            axtree = await page.accessibility.snapshot() or {}
            
            # Screenshot
            screenshot_bytes = await page.screenshot(full_page=True)
            
            # Save captures
            (captures_dir / "sifr" / f"{page_id}.sifr").write_text(sifr_content, encoding="utf-8")
            (captures_dir / "html" / f"{page_id}.html").write_text(html_content, encoding="utf-8")
            (captures_dir / "axtree" / f"{page_id}.json").write_text(json.dumps(axtree, indent=2), encoding="utf-8")
            (captures_dir / "screenshots" / f"{page_id}.png").write_bytes(screenshot_bytes)
            
            sifr_kb = len(sifr_content) // 1024
            console.print(f"  [green]✓ Captured[/green] (SiFR: {sifr_kb}KB)")
            
            # ════════════════════════════════════════════
            # STEP 3: Generate ground truth
            # ════════════════════════════════════════════
            console.print("  [dim]Generating ground truth...[/dim]")
            
            screenshot_path = captures_dir / "screenshots" / f"{page_id}.png"
            gt_path = run_dir / "ground-truth" / f"{page_id}.json"
            
            try:
                gt_result = generate_ground_truth_from_data(
                    screenshot_bytes=screenshot_bytes,
                    sifr_data=sifr_data,
                    output_path=gt_path,
                    mode="compound"
                )
                if "error" in gt_result:
                    console.print(f"  [yellow]⚠️ Ground truth: {gt_result['error']}[/yellow]")
                    continue
                
                gt = json.loads(gt_path.read_text())
                compound_tasks = gt.get("compound_tasks", [])
                console.print(f"  [green]✓ {len(compound_tasks)} tasks[/green]")
            except Exception as e:
                console.print(f"  [yellow]⚠️ Ground truth failed: {e}[/yellow]")
                continue
            
            if not compound_tasks:
                console.print("  [yellow]No compound tasks generated[/yellow]")
                continue
            
            # ════════════════════════════════════════════
            # STEP 4: Prepare format contexts
            # ════════════════════════════════════════════
            sifr_resolver = SiFRResolver(sifr_content) if sifr_content else None
            
            # Truncate contexts to budget
            contexts = {
                "sifr": sifr_content[:target_size] if sifr_content else None,
                "html_raw": html_content[:target_size],
                "axtree": json.dumps(axtree, indent=2)[:target_size],
                "screenshot": screenshot_bytes,
            }
            
            # ════════════════════════════════════════════
            # STEP 5: Query models + Verify (SAME PAGE!)
            # ════════════════════════════════════════════
            console.print("  [dim]Running benchmark...[/dim]")
            
            for model in models:
                for fmt in ALL_FORMATS:
                    ctx = contexts.get(fmt)
                    if ctx is None:
                        continue
                    
                    for task in compound_tasks:
                        task_id = task.get("id", "?")
                        understand = task.get("understand", {})
                        act = task.get("act", {})
                        
                        total_tokens = 0
                        
                        # ──── UNDERSTAND ────
                        u_prompt = UNDERSTAND_PROMPTS.get(fmt)
                        if fmt == "screenshot":
                            u_full = u_prompt.format(question=understand["question"])
                            resp = query_model(model, u_full, image=ctx)
                        else:
                            u_full = u_prompt.format(context=ctx, question=understand["question"])
                            resp = query_model(model, u_full)
                        
                        if resp.get("error"):
                            if verbose:
                                console.print(f"    [red]✗[/red] {task_id} [{fmt}] understand error: {resp['error']}")
                            continue
                        
                        understand_response = resp.get("response", "").strip()
                        total_tokens += resp.get("tokens", 0)
                        
                        # Score understand
                        scoring = score_compound_task(understand_response, False, task, sifr_data)
                        understand_correct = scoring["understand_correct"]
                        
                        # ──── ACT ────
                        a_prompt = ACTION_PROMPTS.get(fmt)
                        if fmt == "screenshot":
                            a_full = a_prompt.format(
                                understand_answer=understand_response,
                                action_question=act["question"]
                            )
                            resp = query_model(model, a_full, image=ctx)
                        else:
                            a_full = a_prompt.format(
                                context=ctx,
                                understand_answer=understand_response,
                                action_question=act["question"]
                            )
                            resp = query_model(model, a_full)
                        
                        if resp.get("error"):
                            if verbose:
                                console.print(f"    [red]✗[/red] {task_id} [{fmt}] act error: {resp['error']}")
                            continue
                        
                        act_response = resp.get("response", "").strip().strip('"\'')
                        total_tokens += resp.get("tokens", 0)
                        
                        # ──── VERIFY ON SAME PAGE ────
                        act_success, selector, error, details = await verify_response(
                            page, act_response, fmt, sifr_resolver, verbose=debug
                        )
                        
                        result = {
                            "page_id": page_id,
                            "model": model,
                            "format": fmt,
                            "task_id": task_id,
                            "understand_correct": understand_correct,
                            "understand_response": understand_response,
                            "understand_reason": scoring.get("understand_reason", ""),
                            "act_success": act_success,
                            "act_response": act_response,
                            "act_selector": selector,
                            "act_error": error,
                            "verification_details": details.to_dict() if details else {},
                            "tokens": total_tokens,
                        }
                        results.append(result)
                        
                        if verbose:
                            u_icon = "✅" if understand_correct else "❌"
                            a_icon = "✅" if act_success else "❌"
                            console.print(
                                f"    {task_id} [{fmt}]: U{u_icon} A{a_icon} "
                                f"| {understand_response[:20]}... → {act_response[:15]}"
                            )
                            if not act_success and details:
                                console.print(f"      [dim]↳ {details.error_stage}: {details.error}[/dim]")
            
            # Small delay between pages
            await page.wait_for_timeout(500)
        
        await context.close()
    
    return results


@main.command()
def info():
    """Show benchmark information."""
    console.print(f"""
[bold blue]SiFR Benchmark v{__version__}[/bold blue]

[bold]Single Session Mode (Refactored):[/bold]
  - Page loaded ONCE per URL
  - Capture, query, verify on SAME page state
  - No reload between steps = accurate verification

[bold]Usage:[/bold]
  sifr-bench full-benchmark-e2llm https://amazon.com -e /path/to/ext -v

[bold]Options:[/bold]
  -v, --verbose   Show per-task results
  --debug         Enable verification logging

[bold]Example:[/bold]
  sifr-bench full-benchmark-e2llm https://amazon.com \\
    -e /path/to/element-to-llm \\
    -m gpt-4o-mini,claude-haiku \\
    -s 300 \\
    -v --debug
""")


@main.command()
@click.argument("path", type=click.Path(exists=True))
def validate(path):
    """Validate SiFR files."""
    from .formats import validate_sifr_file
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
    table.add_column("Mode", style="green")
    table.add_column("Session", style="blue")
    
    for run_dir in sorted(runs_dir.iterdir(), reverse=True):
        if not run_dir.is_dir():
            continue
        meta_path = run_dir / "run_meta.json"
        meta = {}
        if meta_path.exists():
            with open(meta_path) as f:
                meta = json.load(f)
        
        session = "single" if meta.get("single_session") else "multi"
        
        table.add_row(
            run_dir.name,
            meta.get("timestamp", "")[:16].replace("T", " "),
            ",".join(meta.get("models", ["?"])),
            meta.get("mode", "?"),
            session
        )
    
    console.print(table)


if __name__ == "__main__":
    main()
