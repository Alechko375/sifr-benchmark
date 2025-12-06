# SiFR Benchmark

**How well do AI agents understand web UI?**

Benchmark comparing SiFR vs HTML vs AXTree vs Screenshots across complex websites.

> ⚠️ **This is an example run, not a definitive study.** The benchmark is fully reproducible — run it yourself on your sites, your models, your use cases. We show our results; you verify on yours.

## Results

Tested on 10 high-complexity sites: Amazon, YouTube, Reddit, eBay, Walmart, Airbnb, Yelp, IMDB, ESPN, GitHub.

All formats tested with **equal 400KB token budget** for fair comparison.

| Format | Accuracy | Tokens (avg) | 
|--------|----------|--------------|
| **SiFR** | **71.7%** | 102K |
| Screenshot | 27.0% | 38K |
| Raw HTML | 11.4% | 122K |
| AXTree | 1.5% | 6K |

**SiFR is 2.7x more accurate than screenshots and 6.3x more accurate than raw HTML.**

### Per-Site Breakdown

| Site | SiFR | Screenshot | HTML | AXTree |
|------|------|------------|------|--------|
| GitHub | 🏆 **100%** | 0% | — | 0% |
| YouTube | 🏆 **100%** | 64% | 0% | 0% |
| Amazon | 🏆 **85.7%** | 22.9% | — | 0% |
| Walmart | 🏆 **85.7%** | 13.3% | 11.4% | 0% |
| Reddit | 🏆 **83.3%** | 36% | — | 0% |
| Yelp | 🏆 **62.5%** | 57.1% | — | 0% |
| ESPN | 🏆 **57.1%** | 11.4% | 22.9% | 0% |
| IMDB | 🏆 **50%** | 16% | — | 16.7% |
| eBay | 🏆 **28.6%** | 26.7% | 11.4% | 0% |

SiFR wins on **9 out of 9 sites** where it ran successfully.

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
- **Actionable IDs**: Every element gets a unique ID (`a015`, `btn003`)
- **Salience scoring**: High/medium/low importance ranking
- **Structured for LLMs**: Optimized for "find element → take action" tasks
- **Model-agnostic**: Works with any LLM that can read text

## Installation

```bash
pip install sifr-benchmark
```

### Prerequisites

1. **Element-to-LLM Chrome Extension** — captures pages in SiFR format
   - Load unpacked from `element-to-llm-chrome/`

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

### Full Benchmark

Capture → Generate Ground Truth → Test — all in one command:

```bash
sifr-bench full-benchmark-e2llm https://www.amazon.com https://www.youtube.com \
  -e /path/to/element-to-llm-extension \
  -s 400
```

Options:
- `-e, --extension` — Path to E2LLM extension (required)
- `-s, --target-size` — Token budget in KB for ALL formats (default: 400)
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

### 1. Capture

The extension captures 4 formats simultaneously:
- **SiFR** — Structured format with salience scoring
- **HTML** — Raw rendered DOM (`outerHTML`)
- **AXTree** — Playwright accessibility tree
- **Screenshot** — Full-page PNG

### 2. Ground Truth Generation

GPT-4o Vision analyzes screenshot + SiFR to generate agent tasks:
- **Click**: "Click the Sign In button" → `a003`
- **Input**: "Enter search query" → `input001`
- **Locate**: "Find the main heading" → `h1001`

### 3. Benchmark

Each format tested with same token budget, same model, same prompts:

```
Task: "Click on the shopping cart icon"
Expected: a015

SiFR response: a015 ✓
HTML response: none ✗
Screenshot response: cart icon (no ID) ✗
```

## Methodology Notes

> **Run it yourself.** This benchmark exists so you can test on your own sites and models. Our results are one data point — your results on your use case matter more.

- **Equal token budget**: All formats truncated to same size (400KB default). Fair comparison.
  
- **Ground truth is auto-generated**: GPT-4o Vision creates tasks. For production, consider human verification.

- **AXTree 0% is a real finding**: Many agent frameworks use accessibility trees. This shows why that's problematic.

- **7 tasks per site**: Practical, not academic. When did you last need 2000 clicks on one page?

## Why Raw HTML Fails

```
Amazon HTML: 909KB original
After truncation: 400KB (loses 56% of content)
Result: 0% accuracy — critical elements gone

Amazon SiFR: 613KB original  
After truncation: 400KB (loses 35% of content)
Result: 85.7% accuracy — structure survives
```

HTML is verbose. When you truncate it, you lose random chunks. SiFR is pre-compressed with salience scoring — important elements survive truncation.

## Output Format

```
        Benchmark Results: Combined (10 sites)
┏━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━┓
┃ Format     ┃ Accuracy ┃  Tokens ┃  Latency ┃ Status ┃
┡━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━┩
│ sifr       │    71.7% │ 101,683 │ 30,221ms │   ✅   │
│ screenshot │    27.0% │  38,074 │  7,942ms │   ⚠️   │
│ html_raw   │    11.4% │ 122,190 │ 35,901ms │   ⚠️   │
│ axtree     │     1.5% │   6,044 │  2,034ms │   ⚠️   │
└────────────┴──────────┴─────────┴──────────┴────────┘
```

Status:
- ✅ Success (accuracy ≥ 50%)
- ⚠️ Warning (accuracy < 50%)
- ❌ Failed (accuracy = 0%)

## Run Directory Structure

Each benchmark creates an isolated run:

```
benchmark_runs/run_20251206_210357/
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

## Tested Models

Default: gpt-4o-mini

The benchmark supports any OpenAI or Anthropic model. Run with different models:

```bash
sifr-bench full-benchmark-e2llm ... -m gpt-4o
sifr-bench full-benchmark-e2llm ... -m claude-sonnet
```

## Contributing

- **Add test sites**: Run benchmark on more URLs
- **Improve ground truth**: Manual verification of tasks
- **New models**: Add support in `models.py`
- **Bug reports**: Open an issue

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
