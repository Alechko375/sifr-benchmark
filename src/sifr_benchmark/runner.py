"""
Benchmark runner - executes agent tasks across models and formats.
"""

import json
import time
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from .models import query_model, SUPPORTED_MODELS
from .scoring import score_response
from .formats import load_format


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


class BenchmarkRunner:
    """Main benchmark runner for agent tasks."""

    def __init__(
        self,
        models: list[str],
        formats: list[str],
        pages: Optional[list[str]] = None,
        runs: int = 1,
        base_dir: Optional[Path] = None,
    ):
        self.models = models
        self.formats = formats
        self.pages = pages
        self.runs = runs
        self.base_dir = Path(base_dir) if base_dir else Path(".")

        self._validate_config()

    def _validate_config(self):
        """Validate configuration."""
        for model in self.models:
            if model not in SUPPORTED_MODELS:
                raise ValueError(f"Unknown model: {model}. Supported: {list(SUPPORTED_MODELS.keys())}")

    def _load_ground_truth(self, page_id: str) -> dict:
        """Load ground truth for a page."""
        patterns = [
            self.base_dir / "ground-truth" / f"{page_id}.json",  # New structure
            self.base_dir / "benchmark" / "ground-truth" / f"{page_id}.json",  # Legacy
        ]
        
        for path in patterns:
            if path.exists():
                with open(path, encoding="utf-8") as f:
                    return json.load(f)
        
        return {}

    def _get_tasks_from_ground_truth(self, ground_truth: dict) -> list[dict]:
        """Extract tasks from ground truth."""
        # New agent format: tasks array
        if "tasks" in ground_truth and isinstance(ground_truth["tasks"], list):
            return ground_truth["tasks"]
        
        # Legacy format: convert to tasks
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
                "answer": ""  # Unknown in legacy format
            })
        
        return legacy_tasks

    def _discover_pages(self) -> list[str]:
        """Discover available test pages."""
        if self.pages:
            return self.pages

        # New structure: base_dir/ground-truth/
        gt_path = self.base_dir / "ground-truth"
        if gt_path.exists():
            pages = [f.stem for f in gt_path.glob("*.json")]
            if pages:
                return pages
        
        # Fallback: look for SiFR files
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

        # Fallback: try to extract element ID from raw response
        if not result["answer"]:
            import re
            ids = re.findall(r'\b([a-z]{2,4}\d{2,4})\b', raw.lower())
            if ids:
                result["answer"] = ids[0]
            else:
                result["answer"] = raw.strip()[:100]

        return result

    def run_single(
        self,
        model: str,
        format_name: str,
        page_id: str,
        task: dict,
        run_num: int,
    ) -> TestResult:
        """Run a single test."""

        try:
            context = load_format(page_id, format_name, self.base_dir)
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
            )

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
        element_text = task.get("element_text", "")  # For HTML/AXTree fallback
        
        score = score_response(
            parsed["answer"],
            expected,
            task.get("type", "action"),
            element_text
        )

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
                    for task in tasks:
                        for run_num in range(1, self.runs + 1):
                            result = self.run_single(
                                model=model,
                                format_name=format_name,
                                page_id=page_id,
                                task=task,
                                run_num=run_num,
                            )
                            results.append(result.__dict__)
                            
                            # Rate limiting
                            time.sleep(0.3)

        return results

    def aggregate(self, results: list[dict]) -> list[dict]:
        """Aggregate results by format (across models)."""
        agg = {}

        for r in results:
            if r.get("error"):
                continue

            key = r["format"]
            if key not in agg:
                agg[key] = {
                    "format": r["format"],
                    "scores": [],
                    "tokens": [],
                    "latencies": [],
                }

            agg[key]["scores"].append(r["score"])
            agg[key]["tokens"].append(r["tokens"])
            agg[key]["latencies"].append(r["latency_ms"])

        summary = []
        for data in agg.values():
            scores = data["scores"]
            tokens = data["tokens"]
            latencies = data["latencies"]

            summary.append({
                "format": data["format"],
                "accuracy": f"{(sum(scores) / len(scores) * 100):.1f}%" if scores else "N/A",
                "avg_tokens": int(sum(tokens) / len(tokens)) if tokens else 0,
                "avg_latency": f"{int(sum(latencies) / len(latencies))}ms" if latencies else "N/A",
            })

        return sorted(summary, key=lambda x: float(x["accuracy"].rstrip("%") or 0), reverse=True)
