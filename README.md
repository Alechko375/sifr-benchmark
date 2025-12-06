# SiFR Benchmark

**How well do AI agents understand web UI?**

Benchmark comparing SiFR vs HTML vs AXTree vs Screenshots across 10 complex websites.

## Results

Tested on 10 high-complexity sites: Amazon, YouTube, Reddit, eBay, Walmart, Airbnb, Yelp, IMDB, ESPN, GitHub.

| Format | Accuracy | Tokens (avg) | Latency | 
|--------|----------|--------------|---------|
| **SiFR** | **64.6%** | 25,512 | 7.5s |
| Screenshot | 21.5% | 37,765 | 8.0s |
| Raw HTML | 4.7% | 32,879 | 8.3s |
| AXTree | 3.0% | 5,289 | 1.9s |

**SiFR is 3x more accurate than screenshots and 14x more accurate than raw HTML.**

### Per-Site Breakdown

| Site | SiFR | Screenshot | HTML | AXTree |
|------|------|------------|------|--------|
| GitHub | 🏆 **100%** | 0% | 0% | 0% |
| YouTube | 🏆 **100%** | 53.3% | 0% | 0% |
| Walmart | 🏆 **85.7%** | 30% | 11.4% | 0% |
| Reddit | 🏆 **83.3%** | 0% | 0% | 0% |
| eBay | 🏆 **71.4%** | 13.3% | 0% | 14.3% |
| Amazon | 🏆 **66.7%** | 25.7% | 0% | 0% |
| Airbnb | 🏆 **57.1%** | 0% | 34.3% | 0% |
| Yelp | 🤝 50% | 50% | 0% | 12.5% |
| ESPN | 🏆 **42.9%** | 0% | 0% | 0% |
| IMDB | 0% | 🏆 **45%** | 0% | 0% |

SiFR wins on **9 out of 10 sites**.

## What is SiFR?

**Structured Interface Format for Representation** — a compact format optimized for LLM understanding of web UI.

```yaml
a015:
  tag: a
  text: "Add to Cart"
  box: [500, 300, 120, 40]
  attrs: {href: "/cart/add", class: "btn-primary"}
  salience: high
```

Key advantages:
- **Compact**: 10-20x smaller than raw HTML
- **Actionable IDs**: Every element has a unique ID (`a015`, `btn003`)
- **Salience scoring**: High/medium/low importance ranking
- **LLM-native**: Structured for AI comprehension

## Installation

```bash
pip install sifr-benchmark
```

### Prerequisites

1. **Element-to-LLM Chrome Extension** — captures pages in SiFR format
   - [Chrome Web Store](https://chromewebstore.google.com/detail/element-to-llm-dom-captur/oofdfeinchhgnhlikkfdfcldbpcjcgnj)
   - Or load unpacked from `element-to-llm-chrome/`

2. **API Keys**
   ```bash
   export OPENAI_API_KEY=sk-...
   export ANTHROPIC_API_KEY=sk-ant-...  # optional
   ```

3. **Playwright** (for automated capture)
   ```bash
   playwright install chromium
   ```

## Quick Start

### Full Benchmark (Recommended)

Capture → Generate Ground Truth → Test — all in one command:

```bash
sifr-bench full-benchmark-e2llm https://www.amazon.com https://www.youtube.com \
  -e /path/to/element-to-llm-extension \
  -s 400
```

Options:
- `-e, --extension` — Path to E2LLM extension (required)
- `-s, --target-size` — SiFR budget in KB (default: 100, max: 380)
- `-m, --models` — Models to test (default: gpt-4o-mini)
- `-v, --verbose` — Show detailed output

### Other Commands

```bash
# List all benchmark runs
sifr-bench list-runs

# Compare multiple runs
sifr-bench compare benchmark_runs/run_1 benchmark_runs/run_2

# Validate SiFR files
sifr-bench validate examples/

# Show help
sifr-bench info
```

## How It Works

### 1. Capture (E2LLM Extension)

The extension captures 4 formats simultaneously:
- **SiFR** — Structured format with salience scoring
- **HTML** — Raw rendered DOM (`outerHTML`)
- **AXTree** — Playwright accessibility tree
- **Screenshot** — Full-page PNG

### 2. Ground Truth Generation

GPT-4o Vision analyzes the screenshot + SiFR to generate tasks:
- **Click tasks**: "Click the Sign In button" → `a003`
- **Input tasks**: "Enter search query" → `input001`
- **Locate tasks**: "Find the main heading" → `h1001`

### 3. Benchmark

Each format is tested against the same ground truth:
```
Question: "Click on the shopping cart icon"
Expected: a015
SiFR response: a015 ✓
HTML response: none ✗
```

## Output Format

```
        Benchmark Results: Combined (10 sites)
┏━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━┳━━━━━━━━┓
┃ Format     ┃ Accuracy ┃ Tokens ┃ Latency ┃ Status ┃
┡━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━╇━━━━━━━━┩
│ sifr       │    64.6% │ 25,512 │  7,511ms│   ✅   │
│ screenshot │    21.5% │ 37,765 │  8,039ms│   ⚠️   │
│ html_raw   │     4.7% │ 32,879 │  8,332ms│   ⚠️   │
│ axtree     │     3.0% │  5,289 │  1,876ms│   ⚠️   │
└────────────┴──────────┴────────┴─────────┴────────┘
```

Status icons:
- ✅ Success (accuracy ≥ 50%)
- ⚠️ Warning (accuracy < 50%)
- ❌ Failed (accuracy = 0%)

## Run Directory Structure

Each benchmark creates an isolated run:

```
benchmark_runs/run_20251206_182941/
├── captures/
│   ├── sifr/*.sifr
│   ├── html/*.html
│   ├── axtree/*.json
│   └── screenshots/*.png
├── ground-truth/*.json
├── results/
│   ├── raw_results.json
│   └── summary.json
└── run_meta.json
```

## Key Findings

1. **SiFR dominates complex sites** — 100% on GitHub/YouTube, 85%+ on Walmart/Reddit
2. **Screenshots struggle with dense UI** — Can't reliably identify elements
3. **Raw HTML is unusable** — Too large, no semantic structure for LLMs
4. **AXTree IDs don't match** — Own ID scheme incompatible with ground truth

### Why IMDB Failed?

IMDB has the largest DOM (706KB SiFR, 2171KB HTML). Truncation to 97KB removes critical elements. This highlights the need for smarter budgeting in the E2LLM extension.

## Tested Models

- GPT-4o-mini (default)
- GPT-4o
- Claude 3.5 Sonnet
- Claude 3 Haiku

## Contributing

- **Add test sites**: Run benchmark on more URLs
- **Improve ground truth**: Manual verification of tasks
- **New models**: Add support in `models.py`

## Citation

```bibtex
@misc{sifr2025,
  title={SiFR: Structured Interface Format for AI Web Agents},
  author={SiFR Contributors},
  year={2025},
  url={https://github.com/Alechko375/sifr-benchmark}
}
```

## License

MIT
