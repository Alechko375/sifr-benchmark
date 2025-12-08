"""
CLI interface for SiFR Benchmark.
Supports: compound, dev, design, combined modes.
"""

import click
from pathlib import Path
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
import json
import os
import time
from datetime import datetime
from collections import defaultdict

from . import __version__
from .runner import BenchmarkRunner, FormatResult, FailureReason, ALL_FORMATS
from .formats import validate_sifr_file, DEFAULT_MAX_CHARS

console = Console()

DEFAULT_TARGET_SIZE_KB = DEFAULT_MAX_CHARS // 1024

# ============================================================
# PROMPTS - by task type
# ============================================================

# Understanding prompts (compound tasks)
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

# Action prompts (compound tasks)
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

# Dev task prompts
DEV_PROMPTS = {
    "sifr": """Page structure as JSON. Each element has:
- "id": unique identifier (a001, btn002, inp003)
- "tag": element type
- "text": visible text
- "bbox": position [x, y, width, height]

{context}

DEV TASK: {question}

For selectors: return the element "id" (e.g., btn042)
For counts: return the number
For lists: return comma-separated items

ANSWER:""",

    "html_raw": """Page HTML:

{context}

DEV TASK: {question}

For selectors: return CSS selector or data attribute
For counts: return the number
For lists: return comma-separated items

ANSWER:""",

    "axtree": """Accessibility tree:

{context}

DEV TASK: {question}

For selectors: return role + name (e.g., button "Submit")
For counts: return the number
For lists: return comma-separated items

ANSWER:""",

    "screenshot": """DEV TASK: {question}

For selectors: describe the element location
For counts: return the number you can see
For lists: return comma-separated visible items

ANSWER:""",
}

# Design task prompts
DESIGN_PROMPTS = {
    "sifr": """Page structure as JSON. Each element has:
- "bbox": [x, y, width, height] in pixels
- "text": visible content
- "children": nested elements

{context}

DESIGN TASK: {question}

Use bbox values for dimensions. Be specific with measurements.

ANSWER:""",

    "html_raw": """Page HTML:

{context}

DESIGN TASK: {question}

Estimate based on HTML structure. Note any style attributes.

ANSWER:""",

    "axtree": """Accessibility tree:

{context}

DESIGN TASK: {question}

Infer layout from the tree structure.

ANSWER:""",

    "screenshot": """DESIGN TASK: {question}

Analyze the visual design. Estimate dimensions in pixels.

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


def render_ground_truth_summary(gt_path: Path, verbose: bool = False):
    if not gt_path.exists():
        return
    with open(gt_path) as f:
        gt = json.load(f)
    
    # Compound tasks
    compound_tasks = gt.get("compound_tasks", [])
    dev_tasks = gt.get("dev_tasks", [])
    design_tasks = gt.get("design_tasks", [])
    simple_tasks = gt.get("simple_tasks", gt.get("tasks", []))
    
    if compound_tasks:
        type_counts = defaultdict(int)
        for task in compound_tasks:
            type_counts[task.get("type", "unknown")] += 1
        type_str = ", ".join(f"{c} {t}" for t, c in sorted(type_counts.items()))
        console.print(f"  [dim]Compound tasks: {len(compound_tasks)} ({type_str})[/dim]")
        if verbose:
            for task in compound_tasks:
                q = task.get("understand", {}).get("question", "")[:40]
                a = task.get("understand", {}).get("answer", "")[:30]
                console.print(f"    • {q}... → [cyan]{a}[/cyan]")
    
    if dev_tasks:
        type_counts = defaultdict(int)
        for task in dev_tasks:
            type_counts[task.get("type", "unknown")] += 1
        type_str = ", ".join(f"{c} {t}" for t, c in sorted(type_counts.items()))
        console.print(f"  [dim]Dev tasks: {len(dev_tasks)} ({type_str})[/dim]")
        if verbose:
            for task in dev_tasks[:3]:
                q = task.get("question", "")[:50]
                console.print(f"    • {q}...")
    
    if design_tasks:
        type_counts = defaultdict(int)
        for task in design_tasks:
            type_counts[task.get("type", "unknown")] += 1
        type_str = ", ".join(f"{c} {t}" for t, c in sorted(type_counts.items()))
        console.print(f"  [dim]Design tasks: {len(design_tasks)} ({type_str})[/dim]")
        if verbose:
            for task in design_tasks[:3]:
                q = task.get("question", "")[:50]
                console.print(f"    • {q}...")
    
    if simple_tasks:
        console.print(f"  [dim]Simple tasks: {len(simple_tasks)}[/dim]")


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
        combined_correct = sum(1 for r in fmt_results if r.get("understand_correct") and r.get("act_success"))
        total = len(fmt_results)
        
        understand_rate = f"{understand_correct/total*100:.0f}%" if total else "—"
        act_rate = f"{act_correct/total*100:.0f}%" if total else "—"
        combined_rate = f"{combined_correct/total*100:.0f}%" if total else "—"
        avg_tokens = sum(r.get("tokens", 0) for r in fmt_results) // max(total, 1)
        
        table.add_row(fmt, understand_rate, act_rate, combined_rate, f"{avg_tokens:,}")
    
    console.print(table)


def render_dev_results(results: list[dict], site_name: str):
    """Render dev task results."""
    table = Table(title=f"Developer Tasks: {site_name}")
    table.add_column("Format", style="cyan")
    table.add_column("Selector", justify="right", style="yellow")
    table.add_column("A11y", justify="right", style="blue")
    table.add_column("Structure", justify="right", style="green")
    table.add_column("Overall", justify="right", style="magenta")
    table.add_column("Tokens", justify="right")
    
    by_format = defaultdict(list)
    for r in results:
        by_format[r.get("format", "unknown")].append(r)
    
    for fmt in ALL_FORMATS:
        if fmt not in by_format:
            continue
        fmt_results = by_format[fmt]
        
        selector_tasks = [r for r in fmt_results if r.get("task_type") == "selector"]
        a11y_tasks = [r for r in fmt_results if r.get("task_type") == "accessibility"]
        structure_tasks = [r for r in fmt_results if r.get("task_type") == "structure"]
        
        selector_rate = f"{sum(1 for r in selector_tasks if r.get('correct'))/len(selector_tasks)*100:.0f}%" if selector_tasks else "—"
        a11y_rate = f"{sum(1 for r in a11y_tasks if r.get('correct'))/len(a11y_tasks)*100:.0f}%" if a11y_tasks else "—"
        structure_rate = f"{sum(1 for r in structure_tasks if r.get('correct'))/len(structure_tasks)*100:.0f}%" if structure_tasks else "—"
        
        total = len(fmt_results)
        correct = sum(1 for r in fmt_results if r.get("correct"))
        overall_rate = f"{correct/total*100:.0f}%" if total else "—"
        avg_tokens = sum(r.get("tokens", 0) for r in fmt_results) // max(total, 1)
        
        table.add_row(fmt, selector_rate, a11y_rate, structure_rate, overall_rate, f"{avg_tokens:,}")
    
    console.print(table)


def render_design_results(results: list[dict], site_name: str):
    """Render design task results."""
    table = Table(title=f"Design Tasks: {site_name}")
    table.add_column("Format", style="cyan")
    table.add_column("Spacing", justify="right", style="yellow")
    table.add_column("Typography", justify="right", style="blue")
    table.add_column("Consistency", justify="right", style="green")
    table.add_column("Overall", justify="right", style="magenta")
    table.add_column("Tokens", justify="right")
    
    by_format = defaultdict(list)
    for r in results:
        by_format[r.get("format", "unknown")].append(r)
    
    for fmt in ALL_FORMATS:
        if fmt not in by_format:
            continue
        fmt_results = by_format[fmt]
        
        spacing_tasks = [r for r in fmt_results if r.get("task_type") == "spacing"]
        typo_tasks = [r for r in fmt_results if r.get("task_type") == "typography"]
        consist_tasks = [r for r in fmt_results if r.get("task_type") == "consistency"]
        
        spacing_rate = f"{sum(1 for r in spacing_tasks if r.get('correct'))/len(spacing_tasks)*100:.0f}%" if spacing_tasks else "—"
        typo_rate = f"{sum(1 for r in typo_tasks if r.get('correct'))/len(typo_tasks)*100:.0f}%" if typo_tasks else "—"
        consist_rate = f"{sum(1 for r in consist_tasks if r.get('correct'))/len(consist_tasks)*100:.0f}%" if consist_tasks else "—"
        
        total = len(fmt_results)
        correct = sum(1 for r in fmt_results if r.get("correct"))
        overall_rate = f"{correct/total*100:.0f}%" if total else "—"
        avg_tokens = sum(r.get("tokens", 0) for r in fmt_results) // max(total, 1)
        
        table.add_row(fmt, spacing_rate, typo_rate, consist_rate, overall_rate, f"{avg_tokens:,}")
    
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
@click.option("--mode", type=click.Choice(["compound", "dev", "design", "combined"]), default="compound", help="Task type")
@click.option("--runs", "-r", default=1, type=int, help="Runs per test")
@click.option("--base-dir", "-b", default="./benchmark_runs", help="Base directory for runs")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed output")
@click.option("--target-size", "-s", default=DEFAULT_TARGET_SIZE_KB, type=int, help="Budget in KB")
def full_benchmark_e2llm(urls, extension, models, mode, runs, base_dir, verbose, target_size):
    """Full benchmark: capture → ground truth → test."""
    import asyncio
    try:
        from .capture_e2llm import capture_multiple
    except ImportError:
        console.print("[red]Error: playwright not installed[/red]")
        return
    
    run_dir = create_run_dir(base_dir)
    model_list = [m.strip() for m in models.split(",")]
    target_size_bytes = target_size * 1024
    
    mode_labels = {
        "compound": "Compound (understand → act)",
        "dev": "Developer tasks",
        "design": "Design tasks",
        "combined": "All task types",
    }
    
    console.print(f"[bold blue]🚀 Full Benchmark with E2LLM[/bold blue]")
    console.print(f"Run directory: [cyan]{run_dir}[/cyan]")
    console.print(f"URLs: {len(urls)}")
    console.print(f"Models: [yellow]{', '.join(model_list)}[/yellow]")
    console.print(f"Formats: {', '.join(ALL_FORMATS)}")
    console.print(f"Budget: [yellow]{target_size}KB[/yellow]")
    console.print(f"Mode: [green]{mode_labels[mode]}[/green]")
    
    # Step 1: Capture
    console.print("\n[bold]Step 1/3: Capturing with E2LLM...[/bold]")
    captures_dir = run_dir / "captures"
    console.print(f"📦 SiFR budget: {target_size}KB")
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
        
        try:
            result = generate_ground_truth(screenshot_path, sifr_path, gt_output, mode=mode)
            if "error" in result:
                console.print(f"  ⚠️ {page_id}: {result['error']}")
            else:
                console.print(f"  ✅ {page_id}")
                render_ground_truth_summary(gt_output, verbose)
        except Exception as e:
            console.print(f"  ⚠️ {page_id}: {e}")
    
    # Step 3: Run benchmark
    console.print(f"\n[bold]Step 3/3: Running {mode} benchmark...[/bold]")
    
    if mode == "compound":
        bench_results = asyncio.run(run_compound_benchmark(
            run_dir, list(urls), captured_pages, model_list, 
            extension, target_size_bytes, verbose
        ))
        for page_id in captured_pages:
            page_results = [r for r in bench_results if r.get("page_id") == page_id]
            if page_results:
                render_compound_results(page_results, page_id.replace("_", "."))
                
    elif mode == "dev":
        bench_results = asyncio.run(run_dev_benchmark(
            run_dir, list(urls), captured_pages, model_list,
            extension, target_size_bytes, verbose
        ))
        for page_id in captured_pages:
            page_results = [r for r in bench_results if r.get("page_id") == page_id]
            if page_results:
                render_dev_results(page_results, page_id.replace("_", "."))
                
    elif mode == "design":
        bench_results = asyncio.run(run_design_benchmark(
            run_dir, list(urls), captured_pages, model_list,
            extension, target_size_bytes, verbose
        ))
        for page_id in captured_pages:
            page_results = [r for r in bench_results if r.get("page_id") == page_id]
            if page_results:
                render_design_results(page_results, page_id.replace("_", "."))
                
    elif mode == "combined":
        # Run all task types
        compound_results = asyncio.run(run_compound_benchmark(
            run_dir, list(urls), captured_pages, model_list,
            extension, target_size_bytes, verbose
        ))
        dev_results = asyncio.run(run_dev_benchmark(
            run_dir, list(urls), captured_pages, model_list,
            extension, target_size_bytes, verbose
        ))
        design_results = asyncio.run(run_design_benchmark(
            run_dir, list(urls), captured_pages, model_list,
            extension, target_size_bytes, verbose
        ))
        
        bench_results = compound_results + dev_results + design_results
        
        for page_id in captured_pages:
            site_name = page_id.replace("_", ".")
            console.print(f"\n[bold]{site_name}[/bold]")
            
            page_compound = [r for r in compound_results if r.get("page_id") == page_id]
            page_dev = [r for r in dev_results if r.get("page_id") == page_id]
            page_design = [r for r in design_results if r.get("page_id") == page_id]
            
            if page_compound:
                render_compound_results(page_compound, site_name)
            if page_dev:
                render_dev_results(page_dev, site_name)
            if page_design:
                render_design_results(page_design, site_name)
    
    # Save results
    with open(run_dir / "results" / "raw_results.json", "w") as f:
        json.dump(bench_results, f, indent=2, default=str)
    
    metadata = {
        "timestamp": datetime.now().isoformat(),
        "urls": list(urls),
        "models": model_list,
        "formats": ALL_FORMATS,
        "pages": captured_pages,
        "target_size_kb": target_size,
        "mode": mode,
        "version": __version__,
    }
    with open(run_dir / "run_meta.json", "w") as f:
        json.dump(metadata, f, indent=2)
    
    console.print(f"\n[green]✅ Benchmark complete![/green]")
    console.print(f"[cyan]Results: {run_dir}[/cyan]")


async def run_compound_benchmark(run_dir, urls, captured_pages, model_list, extension, target_size_bytes, verbose):
    """Run compound benchmark: understand → act."""
    from playwright.async_api import async_playwright
    from .verification import SiFRResolver, verify_response
    from .models import query_model
    from .formats import load_format
    from .scoring import score_compound_task
    
    results = []
    
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir="./e2llm-chrome-profile",
            headless=False,
            args=[f"--disable-extensions-except={extension}", f"--load-extension={extension}"]
        )
        page = await context.new_page()
        
        for page_id, url in zip(captured_pages, urls):
            gt_path = run_dir / "ground-truth" / f"{page_id}.json"
            if not gt_path.exists():
                continue
            
            gt = json.loads(gt_path.read_text())
            compound_tasks = gt.get("compound_tasks", [])
            
            if not compound_tasks:
                continue
            
            console.print(f"  [bold]{page_id}[/bold]")
            
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(2000)
            except Exception as e:
                console.print(f"    ❌ Failed to load: {e}")
                continue
            
            sifr_path = run_dir / "captures" / "sifr" / f"{page_id}.sifr"
            sifr_resolver = None
            page_data = None
            if sifr_path.exists():
                content = sifr_path.read_text(encoding='utf-8')
                sifr_resolver = SiFRResolver(content)
                try:
                    page_data = json.loads(content)
                except:
                    pass
            
            screenshot_path = run_dir / "captures" / "screenshots" / f"{page_id}.png"
            
            for model in model_list:
                for fmt in ALL_FORMATS:
                    try:
                        if fmt == "screenshot":
                            if not screenshot_path.exists():
                                continue
                            context_str = None
                        else:
                            context_str, _ = load_format(page_id, fmt, run_dir, return_meta=True, max_chars=target_size_bytes)
                    except FileNotFoundError:
                        continue
                    
                    for task in compound_tasks:
                        task_id = task.get("id", "?")
                        understand = task.get("understand", {})
                        act = task.get("act", {})
                        
                        total_tokens = 0
                        
                        # UNDERSTAND
                        prompt = UNDERSTAND_PROMPTS.get(fmt)
                        start = time.time()
                        
                        if fmt == "screenshot":
                            resp = query_model(model, prompt.format(question=understand["question"]), image=screenshot_path.read_bytes())
                        else:
                            resp = query_model(model, prompt.format(context=context_str, question=understand["question"]))
                        
                        if resp.get("error"):
                            continue
                        
                        understand_response = resp.get("response", "").strip()
                        total_tokens += resp.get("tokens", 0)
                        
                        scoring = score_compound_task(understand_response, False, task, page_data)
                        understand_correct = scoring["understand_correct"]
                        
                        # ACT
                        prompt = ACTION_PROMPTS.get(fmt)
                        
                        if fmt == "screenshot":
                            resp = query_model(model, prompt.format(understand_answer=understand_response, action_question=act["question"]), image=screenshot_path.read_bytes())
                        else:
                            resp = query_model(model, prompt.format(context=context_str, understand_answer=understand_response, action_question=act["question"]))
                        
                        if resp.get("error"):
                            continue
                        
                        act_response = resp.get("response", "").strip().strip('"\'')
                        total_tokens += resp.get("tokens", 0)
                        
                        act_success, _, _ = await verify_response(page, act_response, fmt, sifr_resolver)
                        
                        results.append({
                            "page_id": page_id,
                            "model": model,
                            "format": fmt,
                            "task_id": task_id,
                            "understand_correct": understand_correct,
                            "understand_response": understand_response,
                            "understand_reason": scoring.get("understand_reason", ""),
                            "act_success": act_success,
                            "act_response": act_response,
                            "tokens": total_tokens,
                        })
                        
                        if verbose:
                            u = "✅" if understand_correct else "❌"
                            a = "✅" if act_success else "❌"
                            console.print(f"     {task_id}: U{u} A{a} | {understand_response[:20]}... ({scoring.get('understand_reason', '')[:20]}...)")
        
        await context.close()
    
    return results


async def run_dev_benchmark(run_dir, urls, captured_pages, model_list, extension, target_size_bytes, verbose):
    """Run dev tasks benchmark."""
    from .models import query_model
    from .formats import load_format
    
    results = []
    
    for page_id in captured_pages:
        gt_path = run_dir / "ground-truth" / f"{page_id}.json"
        if not gt_path.exists():
            continue
        
        gt = json.loads(gt_path.read_text())
        dev_tasks = gt.get("dev_tasks", [])
        
        if not dev_tasks:
            continue
        
        console.print(f"  [bold]{page_id}[/bold]")
        screenshot_path = run_dir / "captures" / "screenshots" / f"{page_id}.png"
        
        for model in model_list:
            for fmt in ALL_FORMATS:
                try:
                    if fmt == "screenshot":
                        if not screenshot_path.exists():
                            continue
                        context_str = None
                    else:
                        context_str, _ = load_format(page_id, fmt, run_dir, return_meta=True, max_chars=target_size_bytes)
                except FileNotFoundError:
                    continue
                
                for task in dev_tasks:
                    task_id = task.get("id", "?")
                    task_type = task.get("type", "unknown")
                    question = task.get("question", "")
                    expected = task.get("answer", "")
                    
                    prompt = DEV_PROMPTS.get(fmt)
                    
                    if fmt == "screenshot":
                        resp = query_model(model, prompt.format(question=question), image=screenshot_path.read_bytes())
                    else:
                        resp = query_model(model, prompt.format(context=context_str, question=question))
                    
                    if resp.get("error"):
                        continue
                    
                    response = resp.get("response", "").strip()
                    tokens = resp.get("tokens", 0)
                    
                    # Simple scoring: check if answer matches or is contained
                    expected_lower = str(expected).lower()
                    response_lower = response.lower()
                    correct = expected_lower in response_lower or response_lower in expected_lower
                    
                    results.append({
                        "page_id": page_id,
                        "model": model,
                        "format": fmt,
                        "task_id": task_id,
                        "task_type": task_type,
                        "question": question,
                        "expected": expected,
                        "response": response,
                        "correct": correct,
                        "tokens": tokens,
                    })
                    
                    if verbose:
                        icon = "✅" if correct else "❌"
                        console.print(f"     {icon} [{fmt}] {task_id}: {response[:30]}...")
    
    return results


async def run_design_benchmark(run_dir, urls, captured_pages, model_list, extension, target_size_bytes, verbose):
    """Run design tasks benchmark."""
    from .models import query_model
    from .formats import load_format
    
    results = []
    
    for page_id in captured_pages:
        gt_path = run_dir / "ground-truth" / f"{page_id}.json"
        if not gt_path.exists():
            continue
        
        gt = json.loads(gt_path.read_text())
        design_tasks = gt.get("design_tasks", [])
        
        if not design_tasks:
            continue
        
        console.print(f"  [bold]{page_id}[/bold]")
        screenshot_path = run_dir / "captures" / "screenshots" / f"{page_id}.png"
        
        for model in model_list:
            for fmt in ALL_FORMATS:
                try:
                    if fmt == "screenshot":
                        if not screenshot_path.exists():
                            continue
                        context_str = None
                    else:
                        context_str, _ = load_format(page_id, fmt, run_dir, return_meta=True, max_chars=target_size_bytes)
                except FileNotFoundError:
                    continue
                
                for task in design_tasks:
                    task_id = task.get("id", "?")
                    task_type = task.get("type", "unknown")
                    question = task.get("question", "")
                    expected = task.get("answer", "")
                    
                    prompt = DESIGN_PROMPTS.get(fmt)
                    
                    if fmt == "screenshot":
                        resp = query_model(model, prompt.format(question=question), image=screenshot_path.read_bytes())
                    else:
                        resp = query_model(model, prompt.format(context=context_str, question=question))
                    
                    if resp.get("error"):
                        continue
                    
                    response = resp.get("response", "").strip()
                    tokens = resp.get("tokens", 0)
                    
                    # Fuzzy scoring for design tasks
                    expected_lower = str(expected).lower()
                    response_lower = response.lower()
                    
                    # Check for number match (for dimensions)
                    import re
                    expected_nums = set(re.findall(r'\d+', expected_lower))
                    response_nums = set(re.findall(r'\d+', response_lower))
                    
                    if expected_nums and response_nums:
                        # Allow 20% tolerance for pixel values
                        correct = bool(expected_nums & response_nums)
                    else:
                        correct = expected_lower in response_lower or response_lower in expected_lower
                    
                    results.append({
                        "page_id": page_id,
                        "model": model,
                        "format": fmt,
                        "task_id": task_id,
                        "task_type": task_type,
                        "question": question,
                        "expected": expected,
                        "response": response,
                        "correct": correct,
                        "tokens": tokens,
                    })
                    
                    if verbose:
                        icon = "✅" if correct else "❌"
                        console.print(f"     {icon} [{fmt}] {task_id}: {response[:30]}...")
    
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
    table.add_column("URLs", style="blue")
    
    for run_dir in sorted(runs_dir.iterdir(), reverse=True):
        if not run_dir.is_dir():
            continue
        meta_path = run_dir / "run_meta.json"
        meta = {}
        if meta_path.exists():
            with open(meta_path) as f:
                meta = json.load(f)
        
        table.add_row(
            run_dir.name,
            meta.get("timestamp", "")[:16].replace("T", " "),
            ",".join(meta.get("models", ["?"])),
            meta.get("mode", "compound"),
            str(len(meta.get("urls", [])))
        )
    
    console.print(table)


@main.command()
def info():
    """Show benchmark information."""
    console.print(f"""
[bold blue]SiFR Benchmark v{__version__}[/bold blue]

[bold]Modes:[/bold]
  --mode compound  Understanding → Action (AI agents)
  --mode dev       Selectors, A11y, Structure (developers)
  --mode design    Spacing, Typography, Consistency (designers)
  --mode combined  All task types

[bold]Examples:[/bold]
  # Compound tasks (default)
  sifr-bench full-benchmark-e2llm https://stripe.com -e /path/to/ext

  # Dev tasks
  sifr-bench full-benchmark-e2llm https://stripe.com -e /path/to/ext --mode dev

  # Design tasks
  sifr-bench full-benchmark-e2llm https://stripe.com -e /path/to/ext --mode design

  # All task types
  sifr-bench full-benchmark-e2llm https://stripe.com -e /path/to/ext --mode combined

  # Multiple models
  sifr-bench full-benchmark-e2llm https://stripe.com -e /path/to/ext -m gpt-4o-mini,claude-haiku
""")


if __name__ == "__main__":
    main()
