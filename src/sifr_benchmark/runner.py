"""
Benchmark runner - executes tests across models and formats.
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


class BenchmarkRunner:
    """Main benchmark runner."""
    
    def __init__(
        self,
        models: list[str],
        formats: list[str],
        pages: Optional[list[str]] = None,
        runs: int = 3,
        tasks_path: Optional[str] = None,
    ):
        self.models = models
        self.formats = formats
        self.pages = pages
        self.runs = runs
        self.tasks_path = tasks_path or "benchmark/tasks.json"
        
        self._validate_config()
    
    def _validate_config(self):
        """Validate configuration."""
        for model in self.models:
            if model not in SUPPORTED_MODELS:
                raise ValueError(f"Unknown model: {model}. Supported: {list(SUPPORTED_MODELS.keys())}")
    
    def _load_tasks(self) -> list[dict]:
        """Load task definitions."""
        path = Path(self.tasks_path)
        if not path.exists():
            # Return minimal default tasks
            return [
                {"id": "nav_01", "question": "Where is the main navigation?", "scoring": "element_id"},
                {"id": "ext_01", "question": "What is the page title?", "scoring": "text_match"},
                {"id": "int_01", "question": "List all buttons.", "scoring": "precision_recall"},
            ]
        
        with open(path) as f:
            data = json.load(f)
        return data.get("tasks", [])
    
    def _load_ground_truth(self, page_id: str) -> dict:
        """Load ground truth for a page."""
        path = Path(f"benchmark/ground-truth/{page_id}.json")
        if not path.exists():
            return {"tasks": {}}
        
        with open(path) as f:
            return json.load(f)
    
    def _discover_pages(self) -> list[str]:
        """Discover available test pages."""
        if self.pages:
            return self.pages
        
        # Look for ground truth files
        gt_path = Path("benchmark/ground-truth")
        if gt_path.exists():
            pages = [f.stem for f in gt_path.glob("*.json") if f.stem != "template"]
            if pages:
                return pages
        
        # Look for SiFR examples
        examples_path = Path("examples")
        if examples_path.exists():
            pages = [f.stem for f in examples_path.glob("*.sifr")]
            if pages:
                return pages
        
        return ["product_page"]  # Default
    
    def _build_prompt(self, task: dict, context: str, format_name: str) -> str:
        """Build prompt for a task."""
        return f"""You are analyzing a webpage represented in {format_name} format.

CONTEXT:
{context}

QUESTION: {task['question']}

Respond in this exact format:
ANSWER: [your answer]
CONFIDENCE: [0-100]
EVIDENCE: [element IDs or text supporting your answer]"""
    
    def _parse_response(self, raw: str) -> dict:
        """Parse model response."""
        result = {"answer": "", "confidence": 50, "evidence": ""}
        
        for line in raw.split("\n"):
            line = line.strip()
            if line.startswith("ANSWER:"):
                result["answer"] = line.replace("ANSWER:", "").strip()
            elif line.startswith("CONFIDENCE:"):
                try:
                    result["confidence"] = int(line.replace("CONFIDENCE:", "").strip())
                except ValueError:
                    pass
            elif line.startswith("EVIDENCE:"):
                result["evidence"] = line.replace("EVIDENCE:", "").strip()
        
        # If no structured response, use whole text as answer
        if not result["answer"] and raw:
            result["answer"] = raw.strip()[:500]
        
        return result
    
    def run_single(
        self,
        model: str,
        format_name: str,
        page_id: str,
        task: dict,
        ground_truth: dict,
        run_num: int,
    ) -> TestResult:
        """Run a single test."""
        
        # Load context
        try:
            context = load_format(page_id, format_name)
        except FileNotFoundError:
            return TestResult(
                model=model,
                format=format_name,
                page_id=page_id,
                task_id=task["id"],
                run=run_num,
                response="",
                expected="",
                score=0.0,
                confidence=0,
                tokens=0,
                latency_ms=0,
                error=f"Format file not found: {format_name}/{page_id}",
            )
        
        # Build prompt
        prompt = self._build_prompt(task, context, format_name)
        
        # Query model
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
                expected="",
                score=0.0,
                confidence=0,
                tokens=response_data.get("tokens", 0),
                latency_ms=latency,
                error=response_data["error"],
            )
        
        # Parse response
        parsed = self._parse_response(response_data["response"])
        
        # Score
        expected = ground_truth.get("tasks", {}).get(task["id"], {}).get("answer", "")
        score = score_response(
            parsed["answer"],
            expected,
            task.get("scoring", "text_match"),
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
        tasks = self._load_tasks()
        pages = self._discover_pages()
        results = []
        
        for page_id in pages:
            ground_truth = self._load_ground_truth(page_id)
            
            for model in self.models:
                for format_name in self.formats:
                    for task in tasks:
                        for run_num in range(1, self.runs + 1):
                            result = self.run_single(
                                model=model,
                                format_name=format_name,
                                page_id=page_id,
                                task=task,
                                ground_truth=ground_truth,
                                run_num=run_num,
                            )
                            results.append(result.__dict__)
                            
                            # Rate limiting
                            time.sleep(0.2)
        
        return results
    
    def aggregate(self, results: list[dict]) -> list[dict]:
        """Aggregate results by model and format."""
        agg = {}
        
        for r in results:
            if r.get("error"):
                continue
                
            key = f"{r['model']}|{r['format']}"
            if key not in agg:
                agg[key] = {
                    "model": r["model"],
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
                "model": data["model"],
                "format": data["format"],
                "accuracy": f"{(sum(scores) / len(scores) * 100):.1f}%" if scores else "N/A",
                "avg_tokens": int(sum(tokens) / len(tokens)) if tokens else 0,
                "avg_latency": f"{int(sum(latencies) / len(latencies))}ms" if latencies else "N/A",
            })
        
        return sorted(summary, key=lambda x: float(x["accuracy"].rstrip("%") or 0), reverse=True)
