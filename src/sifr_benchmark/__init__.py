"""
SiFR Benchmark - Evaluate LLM understanding of web UI across formats.

Usage:
    pip install sifr-benchmark
    sifr-bench --help
"""

__version__ = "0.1.14"
__author__ = "SiFR Contributors"

from .runner import BenchmarkRunner
from .scoring import score_response
from .formats import load_sifr, load_html, load_axtree

__all__ = [
    "BenchmarkRunner",
    "score_response", 
    "load_sifr",
    "load_html",
    "load_axtree",
]
