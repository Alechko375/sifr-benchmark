"""
Benchmark runner - executes agent tasks across models and formats.
"""

import json
import time
import re
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field
from enum import Enum

from .models import query_model, SUPPORTED_MODELS, supports_vision
from .scoring import score_response
from .formats import load_format, FormatMeta, DEFAULT_MAX_CHARS


class FailureReason(Enum):
    """Reasons why a format benchmark failed or has warnings."""
    TRUNCATED = "truncated"
    CONTEXT_EXCEEDED = "context_exceeded"
    NOT_CAPTURED = "not_captured"
    ID_MISMATCH = "id_mismatch"
    NO_VISION = "no_vision"


@dataclass
class FormatResult:
    """Aggregated result for a single format."""
    format_name: str
    accuracy: Optional[float] = None
    tokens: Optional[int] = None
    latency_ms: Optional[int] = None
    status: str = "success"  # "success", "warning", "failed", "skipped"
    failure_reason: Optional[FailureReason] = None
    failure_details: dict = field(default_factory=dict)


@dataclass
class TestResult:
    model: str
    format: str
    page_id: str
    task_id: str
    run: int
    response: str
    expected: str
    score: float
    confidence: int
    tokens: int
    latency_ms: int
    error: Optional[str] = None
    failure_reason: Optional[FailureReason] = None
    original_size: Optional[int] = None
    truncated_size: Optional[int] = None


# Agent-focused prompt template
AGENT_PROMPT = """You are a web automation agent. You need to identify which UI element to interact with.

The webpage is described below in {format_name} format:

{context}

TASK: {question}

Rules:
- Return ONLY the element ID (like btn001, lnk007, inp001)
- If multiple elements match, return the most relevant one
- If no element matches, respond with "none"

Respond in this exact format:
ANSWER: [element ID]
CONFIDENCE: [0-100]"""


# Vision prompt template (for screenshot)
VISION_PROMPT = """You are a web automation agent. Look at this screenshot of a webpage.

TASK: {question}

Rules:
- Identify the UI element you would interact with
- Return element ID if visible, otherwise describe the element briefly
- If no element matches, respond with "none"

Respond in this exact format:
ANSWER: [element ID or brief description]
CONFIDENCE: [0-100]"""

# All supported formats
ALL_FORMATS = ["sifr", "html_raw", "axtree", "screenshot"]

# Model context limits (tokens)
MODEL_CONTEXT_LIMITS = {
    "gpt-4o-mini": 128000,
    "gpt-4o": 128000,
    "claude-sonnet": 200000,
    "claude-haiku": 200000,
}


class BenchmarkRunner:
    """Main benchmark runner for agent tasks."""

    def __init__(
        self,
        models: list[str],
        formats: list[str],
        pages: Optional[list[str]] = None,
        runs: int = 1,
        base_dir: Optional[Path] = None,
        max_chars: int = DEFAULT_MAX_CHARS,
    ):
        self.models = models
        self.formats = formats
        self.pages = pages
        self.runs = runs
        self.base_dir = Path(base_dir) if base_dir else Path(".")
        self.max_chars = max_chars
        self._validate_config()

    def _validate_config(self):
        """Validate configuration."""
        for model in self.models:
            if model not in SUPPORTED_MODELS:
                raise ValueError(f"Unknown model: {model}. Supported: {list(SUPPORTED_MODELS.keys())}")

    def _load_ground_truth(self, page_id: str) -> dict:
        """Load ground truth for a page."""
        patterns = [
            self.base_dir / "ground-truth" / f"{page_id}.json",
            self.base_dir / "benchmark" / "ground-truth" / f"{page_id}.json",
        ]
        for path in patterns:
            if path.exists():
                with open(path, encoding="utf-8") as f:
                    return json.load(f)
        return {}

    def _get_tasks_from_ground_truth(self, ground_truth: dict) -> list[dict]:
        """Extract tasks from ground truth."""
        if "tasks" in ground_truth and isinstance(ground_truth["tasks"], list):
            return ground_truth["tasks"]
        
        legacy_tasks = []
        if ground_truth.get("title"):
            legacy_tasks.append({
                "id": "ext_01",
                "type": "action_locate",
                "question": "What element ID contains the page title?",
                "answer": ground_truth.get("title", "")
            })
        if ground_truth.get("primary_button", {}).get("text"):
            legacy_tasks.append({
                "id": "act_01",
                "type": "action_click",
                "question": f"What element ID should I click to {ground_truth['primary_button']['text']}?",
                "answer": ""
            })
        return legacy_tasks

    def _discover_pages(self) -> list[str]:
        """Discover available test pages."""
        if self.pages:
            return self.pages

        gt_path = self.base_dir / "ground-truth"
        if gt_path.exists():
            pages = [f.stem for f in gt_path.glob("*.json")]
            if pages:
                return pages
        
        sifr_path = self.base_dir / "captures" / "sifr"
        if sifr_path.exists():
            pages = [f.stem for f in sifr_path.glob("*.sifr")]
            if pages:
                return pages
        return []

    def _build_prompt(self, task: dict, context: str, format_name: str) -> str:
        """Build prompt for agent task."""
        return AGENT_PROMPT.format(
            format_name=format_name,
            context=context,
            question=task["question"]
        )

    def _parse_response(self, raw: str) -> dict:
        """Parse model response."""
        result = {"answer": "", "confidence": 50}
        for line in raw.split("\n"):
            line = line.strip()
            if line.upper().startswith("ANSWER:"):
                result["answer"] = line.split(":", 1)[1].strip()
            elif line.upper().startswith("CONFIDENCE:"):
                try:
                    result["confidence"] = int(line.split(":", 1)[1].strip())
                except ValueError:
                    pass

        if not result["answer"]:
            import re
            ids = re.findall(r'\b([a-z]{2,4}\d{2,4})\b', raw.lower())
            if ids:
                result["answer"] = ids[0]
            else:
                result["answer"] = raw.strip()[:100]
        return result

    def _check_format_availability(self, format_name: str, page_id: str, model: str) -> Optional[FormatResult]:
        """Check if format is available and return FormatResult if it's not runnable."""
        
        # Screenshot requires vision-capable model
        if format_name == "screenshot":
            if not supports_vision(model):
                return FormatResult(
                    format_name=format_name,
                    status="not_supported",
                    failure_reason=FailureReason.NO_VISION,
                    failure_details={"model": model}
                )
            # Check if screenshot file exists
            screenshot_path = self.base_dir / "captures" / "screenshots" / f"{page_id}.png"
            if not screenshot_path.exists():
                return FormatResult(
                    format_name=format_name,
                    status="skipped",
                    failure_reason=FailureReason.NOT_CAPTURED,
                    failure_details={"format": "screenshot"}
                )
        
        # AXTree has ID mismatch issue
        if format_name == "axtree":
            return None  # Let it run, but we'll mark it in results
        
        return None  # Format is available

    def run_single(
        self,
        model: str,
        format_name: str,
        page_id: str,
        task: dict,
        run_num: int,
    ) -> TestResult:
        """Run a single test."""
        
        # Handle screenshot format separately
        if format_name == "screenshot":
            return self._run_screenshot_test(model, page_id, task, run_num)
        
        try:
            result = load_format(
                page_id, 
                format_name, 
                self.base_dir, 
                return_meta=True,
                max_chars=self.max_chars
            )
            context, meta = result
        except FileNotFoundError as e:
            return TestResult(
                model=model,
                format=format_name,
                page_id=page_id,
                task_id=task["id"],
                run=run_num,
                response="",
                expected=task.get("answer", ""),
                score=0.0,
                confidence=0,
                tokens=0,
                latency_ms=0,
                error=f"Format file not found: {format_name}/{page_id}",
                failure_reason=FailureReason.NOT_CAPTURED,
            )

        # Check context size (use original size for limit check)
        original_tokens = meta.original_size // 4
        approx_tokens = len(context) // 4
        limit = MODEL_CONTEXT_LIMITS.get(model, 128000)
        
        if original_tokens > limit and not meta.was_truncated:
            return TestResult(
                model=model,
                format=format_name,
                page_id=page_id,
                task_id=task["id"],
                run=run_num,
                response="",
                expected=task.get("answer", ""),
                score=0.0,
                confidence=0,
                tokens=original_tokens,
                latency_ms=0,
                error=f"Context exceeds limit: {original_tokens} > {limit}",
                failure_reason=FailureReason.CONTEXT_EXCEEDED,
            )
        
        # Track truncation for warnings
        was_truncated = meta.was_truncated

        prompt = self._build_prompt(task, context, format_name)
        start = time.time()
        response_data = query_model(model, prompt)
        latency = int((time.time() - start) * 1000)

        if response_data.get("error"):
            return TestResult(
                model=model,
                format=format_name,
                page_id=page_id,
                task_id=task["id"],
                run=run_num,
                response="",
                expected=task.get("answer", ""),
                score=0.0,
                confidence=0,
                tokens=response_data.get("tokens", 0),
                latency_ms=latency,
                error=response_data["error"],
            )

        parsed = self._parse_response(response_data["response"])
        expected = task.get("answer", "")
        element_text = task.get("element_text", "")
        score = score_response(parsed["answer"], expected, task.get("type", "action"), element_text)

        # Determine failure reason for low scores
        failure_reason = None
        if score == 0 and format_name == "axtree":
            failure_reason = FailureReason.ID_MISMATCH
        elif was_truncated and score < 0.5:
            failure_reason = FailureReason.TRUNCATED

        return TestResult(
            model=model,
            format=format_name,
            page_id=page_id,
            task_id=task["id"],
            run=run_num,
            response=parsed["answer"],
            expected=expected,
            score=score,
            confidence=parsed["confidence"],
            tokens=response_data.get("tokens", 0),
            latency_ms=latency,
            failure_reason=failure_reason,
            original_size=meta.original_size if was_truncated else None,
            truncated_size=meta.truncated_size if was_truncated else None,
        )

    def _run_screenshot_test(
        self,
        model: str,
        page_id: str,
        task: dict,
        run_num: int,
    ) -> TestResult:
        """Run a screenshot (vision) test."""
        from .formats import load_screenshot
        
        try:
            screenshot_bytes, meta = load_screenshot(page_id, self.base_dir, return_meta=True)
        except FileNotFoundError:
            return TestResult(
                model=model,
                format="screenshot",
                page_id=page_id,
                task_id=task["id"],
                run=run_num,
                response="",
                expected=task.get("answer", ""),
                score=0.0,
                confidence=0,
                tokens=0,
                latency_ms=0,
                error="Screenshot not found",
                failure_reason=FailureReason.NOT_CAPTURED,
            )
        
        prompt = VISION_PROMPT.format(question=task["question"])
        
        start = time.time()
        response_data = query_model(model, prompt, image=screenshot_bytes)
        latency = int((time.time() - start) * 1000)
        
        if response_data.get("error"):
            return TestResult(
                model=model,
                format="screenshot",
                page_id=page_id,
                task_id=task["id"],
                run=run_num,
                response="",
                expected=task.get("answer", ""),
                score=0.0,
                confidence=0,
                tokens=response_data.get("tokens", 0),
                latency_ms=latency,
                error=response_data["error"],
            )
        
        parsed = self._parse_response(response_data["response"])
        expected = task.get("answer", "")
        element_text = task.get("element_text", "")
        
        # For vision, use element_text matching since model can't see IDs
        score = score_response(parsed["answer"], expected, task.get("type", "action"), element_text)
        
        return TestResult(
            model=model,
            format="screenshot",
            page_id=page_id,
            task_id=task["id"],
            run=run_num,
            response=parsed["answer"],
            expected=expected,
            score=score,
            confidence=parsed["confidence"],
            tokens=response_data.get("tokens", 0),
            latency_ms=latency,
        )

    def run(self) -> list[dict]:
        """Run full benchmark."""
        pages = self._discover_pages()
        results = []

        if not pages:
            print("No pages found for benchmark")
            return results

        for page_id in pages:
            ground_truth = self._load_ground_truth(page_id)
            tasks = self._get_tasks_from_ground_truth(ground_truth)
            
            if not tasks:
                print(f"  ⚠️ No tasks for {page_id}")
                continue

            for model in self.models:
                for format_name in self.formats:
                    # Check format availability
                    unavailable = self._check_format_availability(format_name, page_id, model)
                    if unavailable:
                        # Add placeholder result for skipped format
                        results.append({
                            "model": model,
                            "format": format_name,
                            "page_id": page_id,
                            "task_id": "all",
                            "run": 0,
                            "response": "",
                            "expected": "",
                            "score": 0.0,
                            "confidence": 0,
                            "tokens": 0,
                            "latency_ms": 0,
                            "error": f"Format unavailable: {unavailable.failure_reason.value}",
                            "failure_reason": unavailable.failure_reason.value,
                            "status": unavailable.status,
                        })
                        continue

                    for task in tasks:
                        for run_num in range(1, self.runs + 1):
                            result = self.run_single(
                                model=model,
                                format_name=format_name,
                                page_id=page_id,
                                task=task,
                                run_num=run_num,
                            )
                            result_dict = result.__dict__.copy()
                            if result.failure_reason:
                                result_dict["failure_reason"] = result.failure_reason.value
                            results.append(result_dict)
                            time.sleep(0.3)

        return results

    def aggregate(self, results: list[dict]) -> list[FormatResult]:
        """Aggregate results by format with failure tracking."""
        agg = {}

        for r in results:
            key = r["format"]
            if key not in agg:
                agg[key] = {
                    "format": r["format"],
                    "scores": [],
                    "tokens": [],
                    "latencies": [],
                    "errors": [],
                    "failure_reasons": [],
                    "status": r.get("status", "success"),
                    "original_sizes": [],
                    "truncated_sizes": [],
                }

            if r.get("error"):
                agg[key]["errors"].append(r["error"])
                if r.get("failure_reason"):
                    agg[key]["failure_reasons"].append(r["failure_reason"])
            else:
                agg[key]["scores"].append(r["score"])
                agg[key]["tokens"].append(r["tokens"])
                agg[key]["latencies"].append(r["latency_ms"])
            
            # Track truncation info
            if r.get("original_size"):
                agg[key]["original_sizes"].append(r["original_size"])
            if r.get("truncated_size"):
                agg[key]["truncated_sizes"].append(r["truncated_size"])

        summary = []
        for data in agg.values():
            scores = data["scores"]
            tokens = data["tokens"]
            latencies = data["latencies"]
            
            # Determine status and failure reason
            status = "success"
            failure_reason = None
            failure_details = {}
            
            # Check for truncation
            if data["original_sizes"] and data["truncated_sizes"]:
                avg_original = sum(data["original_sizes"]) // len(data["original_sizes"])
                avg_truncated = sum(data["truncated_sizes"]) // len(data["truncated_sizes"])
                failure_details["original_kb"] = avg_original // 1024
                failure_details["truncated_kb"] = avg_truncated // 1024
            
            if data.get("status") == "skipped":
                status = "skipped"
                if data["failure_reasons"]:
                    failure_reason = FailureReason(data["failure_reasons"][0])
                    failure_details["format"] = data["format"]
            elif data.get("status") == "not_supported":
                status = "not_supported"
                if data["failure_reasons"]:
                    failure_reason = FailureReason(data["failure_reasons"][0])
            elif data.get("status") == "failed":
                status = "failed"
                if data["failure_reasons"]:
                    failure_reason = FailureReason(data["failure_reasons"][0])
            elif not scores and data["errors"]:
                status = "failed"
                error_str = data["errors"][0] if data["errors"] else ""
                if "Context exceeds" in error_str:
                    failure_reason = FailureReason.CONTEXT_EXCEEDED
                    match = re.search(r'(\d+) > (\d+)', error_str)
                    if match:
                        failure_details = {"tokens": int(match.group(1)), "limit": int(match.group(2))}
                elif "not found" in error_str.lower():
                    failure_reason = FailureReason.NOT_CAPTURED
                    failure_details["format"] = data["format"]
                elif "vision" in error_str.lower() or "NO_VISION" in str(data["failure_reasons"]):
                    failure_reason = FailureReason.NO_VISION
            elif scores:
                avg_score = sum(scores) / len(scores)
                
                # Determine status based on accuracy
                if avg_score >= 0.5:
                    status = "success"
                elif avg_score > 0:
                    status = "warning"
                    # Check if it was truncated
                    if data["original_sizes"]:
                        failure_reason = FailureReason.TRUNCATED
                else:
                    # 0% accuracy
                    status = "failed"
                    if data["format"] == "axtree":
                        failure_reason = FailureReason.ID_MISMATCH
                    elif data["original_sizes"]:
                        failure_reason = FailureReason.TRUNCATED

            result = FormatResult(
                format_name=data["format"],
                accuracy=sum(scores) / len(scores) if scores else None,
                tokens=int(sum(tokens) / len(tokens)) if tokens else None,
                latency_ms=int(sum(latencies) / len(latencies)) if latencies else None,
                status=status,
                failure_reason=failure_reason,
                failure_details=failure_details,
            )
            summary.append(result)

        # Sort by accuracy (None values last)
        return sorted(summary, key=lambda x: (x.accuracy is None, -(x.accuracy or 0)))
