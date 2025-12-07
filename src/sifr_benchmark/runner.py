"""
Benchmark runner with optional live verification.
"""

import json
import time
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from .models import query_model, SUPPORTED_MODELS
from .scoring import score_response
from .formats import load_format, load_sifr, DEFAULT_MAX_CHARS


# Token costs per 1M tokens
TOKEN_COSTS = {
    "gpt-4o": 2.50,
    "gpt-4o-mini": 0.15,
    "gpt-4-turbo": 2.50,
    "claude-sonnet": 3.00,
    "claude-haiku": 0.25,
    "claude-opus": 15.00,
}

# Format-specific prompts
PROMPTS = {
    "sifr": """Page in SiFR format:

{context}

TASK: {question}

Return ONLY the element ID (like a002, btn001). Nothing else.

ANSWER:""",

    "html_raw": """Page HTML:

{context}

TASK: {question}

Return a CSS selector (#id, .class) or exact visible text. Nothing else.

ANSWER:""",

    "axtree": """Accessibility tree:

{context}

TASK: {question}

Return: role "name" (e.g., button "Submit") or visible text. Nothing else.

ANSWER:""",
}

ALL_FORMATS = ["sifr", "html_raw", "axtree"]


@dataclass
class TestResult:
    model: str
    format: str
    page_id: str
    task_id: str
    question: str
    response: str
    selector: Optional[str]
    expected: str
    success: bool
    score: float
    tokens: int
    latency_ms: int
    cost_usd: float
    error: Optional[str] = None


@dataclass 
class FormatResult:
    format_name: str
    success_rate: float
    accuracy: float
    tokens: int
    latency_ms: int
    cost_usd: float
    total: int
    succeeded: int


class BenchmarkRunner:
    def __init__(
        self,
        models: list[str],
        formats: list[str] = None,
        base_dir: Path = None,
        max_chars: int = DEFAULT_MAX_CHARS,
        runs: int = 1,
        pages: list[str] = None,
    ):
        self.models = models
        self.formats = formats or ALL_FORMATS
        self.base_dir = Path(base_dir) if base_dir else Path(".")
        self.max_chars = max_chars
        self.runs = runs
        self.pages = pages
        self._sifr_cache = {}

    def _load_ground_truth(self, page_id: str) -> dict:
        path = self.base_dir / "ground-truth" / f"{page_id}.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return {}

    def _load_sifr_data(self, page_id: str) -> Optional[dict]:
        if page_id in self._sifr_cache:
            return self._sifr_cache[page_id]
        try:
            content = load_sifr(page_id, self.base_dir)
            data = json.loads(content)
            self._sifr_cache[page_id] = data
            return data
        except:
            self._sifr_cache[page_id] = None
            return None

    def _discover_pages(self) -> list[str]:
        if self.pages:
            return self.pages
        gt_path = self.base_dir / "ground-truth"
        if gt_path.exists():
            return [f.stem for f in gt_path.glob("*.json")]
        return []

    def _clean_response(self, raw: str) -> str:
        raw = raw.strip()
        if raw.upper().startswith("ANSWER:"):
            raw = raw[7:].strip()
        if "\n" in raw:
            raw = raw.split("\n")[0].strip()
        return raw

    def run_single(
        self,
        model: str,
        format_name: str,
        page_id: str,
        task: dict,
        verified: Optional[bool] = None,
        resolved_selector: Optional[str] = None,
    ) -> TestResult:
        """Run single test. If verified is provided, use it for scoring."""
        
        task_id = task.get("id", "?")
        question = task.get("question", "")
        target = task.get("target", {})
        expected = target.get("text") or task.get("answer", "")
        
        # Load format
        try:
            context, _ = load_format(
                page_id, format_name, self.base_dir,
                return_meta=True, max_chars=self.max_chars
            )
        except FileNotFoundError:
            return TestResult(
                model=model, format=format_name, page_id=page_id,
                task_id=task_id, question=question, response="",
                selector=None, expected=expected, success=False,
                score=0.0, tokens=0, latency_ms=0, cost_usd=0,
                error="Format not found"
            )

        # Build prompt
        prompt = PROMPTS.get(format_name, PROMPTS["html_raw"]).format(
            context=context, question=question
        )

        # Query model
        start = time.time()
        resp = query_model(model, prompt)
        latency = int((time.time() - start) * 1000)
        
        tokens = resp.get("tokens", 0)
        cost = (tokens / 1_000_000) * TOKEN_COSTS.get(model, 1.0)

        if resp.get("error"):
            return TestResult(
                model=model, format=format_name, page_id=page_id,
                task_id=task_id, question=question, response="",
                selector=None, expected=expected, success=False,
                score=0.0, tokens=tokens, latency_ms=latency, cost_usd=cost,
                error=resp["error"]
            )

        response = self._clean_response(resp.get("response", ""))
        
        # Score
        score = score_response(response, task, format_name, verified)
        success = score >= 1.0

        return TestResult(
            model=model, format=format_name, page_id=page_id,
            task_id=task_id, question=question, response=response,
            selector=resolved_selector, expected=expected, success=success,
            score=score, tokens=tokens, latency_ms=latency, cost_usd=cost
        )

    def run(self, progress_callback=None) -> list[dict]:
        """Run benchmark (without live verification)."""
        pages = self._discover_pages()
        results = []
        
        if not pages:
            return results

        total = sum(
            len(self._load_ground_truth(p).get("tasks", []))
            for p in pages
        ) * len(self.models) * len(self.formats) * self.runs
        
        completed = 0

        for page_id in pages:
            gt = self._load_ground_truth(page_id)
            tasks = gt.get("tasks", [])
            
            for model in self.models:
                for fmt in self.formats:
                    for task in tasks:
                        for _ in range(self.runs):
                            result = self.run_single(model, fmt, page_id, task)
                            results.append(result.__dict__)
                            
                            completed += 1
                            if progress_callback:
                                progress_callback(completed, total)
                            
                            time.sleep(1.5)  # Rate limit

        return results

    def aggregate(self, results: list[dict]) -> list[FormatResult]:
        """Aggregate results by format."""
        from collections import defaultdict
        
        agg = defaultdict(lambda: {
            "scores": [], "tokens": [], "latencies": [], 
            "costs": [], "successes": []
        })
        
        for r in results:
            if r.get("error"):
                continue
            key = r["format"]
            agg[key]["scores"].append(r["score"])
            agg[key]["tokens"].append(r["tokens"])
            agg[key]["latencies"].append(r["latency_ms"])
            agg[key]["costs"].append(r["cost_usd"])
            agg[key]["successes"].append(1 if r.get("success") else 0)

        summary = []
        for fmt, d in agg.items():
            n = len(d["scores"])
            summary.append(FormatResult(
                format_name=fmt,
                success_rate=sum(d["successes"]) / n if n else 0,
                accuracy=sum(d["scores"]) / n if n else 0,
                tokens=int(sum(d["tokens"]) / n) if n else 0,
                latency_ms=int(sum(d["latencies"]) / n) if n else 0,
                cost_usd=sum(d["costs"]),
                total=n,
                succeeded=sum(d["successes"]),
            ))

        return sorted(summary, key=lambda x: -x.success_rate)
