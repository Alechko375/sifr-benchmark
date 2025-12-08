# SiFR Benchmark

**How well do AI agents understand web UI?**

Benchmark comparing SiFR vs HTML vs AXTree vs Screenshots across complex websites.

> ⚠️ **This is an example run, not a definitive study.** The benchmark is fully reproducible — run it yourself on your sites, your models, your use cases.

## Results

Tested on Amazon with **300KB token budget**, compound tasks (understand → act).

| Format | Understand | Act | Combined | Tokens |
|--------|------------|-----|----------|--------|
| **SiFR** | **100%** | 25% | **25%** | 173K |
| HTML | 100% | 0% | 0% | 194K |
| AXTree | 100% | 25% | 25% | 27K |
| Screenshot | 75% | 0% | 0% | 51K |

**Key insight:** HTML understands perfectly but can't act. Screenshot sees the page but has no element IDs. **Only SiFR and AXTree can both understand AND act.**

### Budget Matters

| Budget | SiFR Combined | HTML Combined | Winner |
|--------|---------------|---------------|--------|
| 300KB | **25%** | 0% | **SiFR** |
| 100KB | 0% | **50%** | **HTML** |

- **Large pages (300KB+)**: SiFR wins — structure survives truncation
- **Small pages (100KB)**: HTML wins — less overhead, more content

## What is SiFR?

**Structured Interface Format for Representation** — JSON format optimized for LLM understanding of web UI.

```json
{
  "id": "a015",
  "tag": "a",
  "text": "Add to Cart",
  "bbox": [500, 300, 120, 40],
  "children": []
}
```

Key advantages:
- **Actionable IDs**: Every element gets a unique ID (`a015`, `btn003`)
- **Bounding boxes**: Pixel-perfect positions for design tasks
- **Structured JSON**: LLMs understand JSON natively
- **Hierarchical**: Parent-child relationships preserved

## Installation

```bash
pip install sifr-benchmark
```

### Prerequisites

1. **Element-to-LLM Chrome Extension** — captures pages in SiFR format
2. **API Keys**
   ```bash
   export OPENAI_API_KEY=sk-...
   export ANTHROPIC_API_KEY=sk-ant-...  # optional
   ```
3. **Playwright**
   ```bash
   playwright install chromium
   ```

## Quick Start

### Full Benchmark

```bash
sifr-bench full-benchmark-e2llm https://www.amazon.com \
  -e /path/to/element-to-llm-extension \
  -s 300 \
  --mode compound
```

## Benchmark Modes

### 🤖 Compound Tasks (AI Agents)
Understanding → Action pairs for autonomous agents.

```bash
sifr-bench full-benchmark-e2llm https://amazon.com -e /path/to/ext --mode compound
```

Tasks:
- "Which product has the highest rating?" → "Click on it"
- "Find items under $50" → "Add to cart"
- "What's the top news story?" → "Open comments"

### 👨‍💻 Dev Tasks (Frontend Developers)
Selectors, accessibility, structure analysis.

```bash
sifr-bench full-benchmark-e2llm https://stripe.com -e /path/to/ext --mode dev
```

Tasks:
- "What's a stable selector for the login button?" → `btn042`
- "Which images are missing alt text?" → `3 images`
- "List all form inputs on the page" → `email, password, submit`
- "Find buttons without aria-labels" → `btn005, btn012`

**Why SiFR wins for devs:**
- Stable IDs vs fragile CSS selectors
- Element inventory built-in
- No DOM parsing needed

### 🎨 Design Tasks (UI/UX Designers)
Spacing, typography, consistency checks.

```bash
sifr-bench full-benchmark-e2llm https://stripe.com -e /path/to/ext --mode design
```

Tasks:
- "What's the height of the hero section?" → `~500px`
- "Are all cards the same width?" → `Yes, 4 columns`
- "How many button variants exist?" → `3 styles`
- "What's the gap between nav items?" → `24px`

**Why SiFR wins for designers:**
- `bbox` provides exact pixel measurements
- Can calculate spacing mathematically
- No visual estimation needed

### 🔄 Combined Mode
Run all task types at once.

```bash
sifr-bench full-benchmark-e2llm https://stripe.com -e /path/to/ext --mode combined -v
```

## Options

| Option | Description | Default |
|--------|-------------|---------|
| `-e, --extension` | Path to E2LLM extension | required |
| `-s, --target-size` | Token budget in KB | 400 |
| `-m, --models` | Models to test | gpt-4o-mini |
| `--mode` | Task type: compound/dev/design/combined | compound |
| `-v, --verbose` | Show detailed output | false |

## Multi-Model Comparison

```bash
sifr-bench full-benchmark-e2llm https://amazon.com \
  -e /path/to/ext \
  -s 300 \
  -m gpt-4o-mini,gpt-4o,claude-haiku
```

## Supported Models

| Model | Alias | Vision |
|-------|-------|--------|
| GPT-4o | `gpt-4o` | ✅ |
| GPT-4o Mini | `gpt-4o-mini` | ✅ |
| GPT-4 Turbo | `gpt-4-turbo` | ✅ |
| Claude Sonnet 4 | `claude-sonnet` | ✅ |
| Claude Haiku 4.5 | `claude-haiku` | ✅ |
| Claude Opus 4 | `claude-opus` | ✅ |

## Output Examples

### Compound Tasks
```
Understanding + Action Results: amazon.com
┏━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━┳━━━━━━━━━━┳━━━━━━━━━┓
┃ Format     ┃ Understand ┃ Act ┃ Combined ┃  Tokens ┃
┡━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━╇━━━━━━━━━━╇━━━━━━━━━┩
│ sifr       │       100% │ 25% │      25% │ 172,794 │
│ html_raw   │       100% │  0% │       0% │ 194,367 │
│ axtree     │       100% │ 25% │      25% │  27,223 │
│ screenshot │        75% │  0% │       0% │  51,162 │
└────────────┴────────────┴─────┴──────────┴─────────┘
```

### Dev Tasks
```
Developer Tasks: stripe.com
┏━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━┓
┃ Format     ┃ Selector ┃ A11y ┃ Structure ┃ Overall ┃
┡━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━┩
│ sifr       │      80% │  60% │      100% │     75% │
│ html_raw   │      40% │  80% │       60% │     55% │
│ axtree     │      20% │ 100% │       80% │     60% │
│ screenshot │       0% │  40% │       40% │     25% │
└────────────┴──────────┴──────┴───────────┴─────────┘
```

### Design Tasks
```
Design Tasks: stripe.com
┏━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━┓
┃ Format     ┃ Spacing ┃ Typography ┃ Consistency ┃ Overall ┃
┡━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━┩
│ sifr       │     90% │        60% │         70% │     75% │
│ screenshot │     70% │        80% │         60% │     70% │
│ html_raw   │     20% │        40% │         50% │     35% │
│ axtree     │     10% │        30% │         40% │     25% │
└────────────┴─────────┴────────────┴─────────────┴─────────┘
```

## Other Commands

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

## Run Directory Structure

```
benchmark_runs/run_20251208_093517/
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

## Why Each Format Fails

| Format | Understand | Act | Why |
|--------|------------|-----|-----|
| **SiFR** | ✅ JSON structure | ✅ Has IDs | Best of both worlds |
| **HTML** | ✅ Full content | ❌ No stable IDs | Can read, can't click |
| **AXTree** | ✅ Semantic | ⚠️ Own IDs | IDs don't match page |
| **Screenshot** | ✅ Visual | ❌ No IDs at all | Sees but can't act |

## Use Cases

### For AI Agent Developers
- Test agent accuracy before deployment
- Compare different LLM backends
- Benchmark against baselines

### For Frontend Developers
- Generate stable test selectors
- Audit accessibility issues
- Analyze component structure

### For UI/UX Designers
- Verify design system consistency
- Check spacing and typography
- Audit visual hierarchy

## Contributing

- **Add test sites**: Run benchmark on more URLs
- **Improve ground truth**: Manual verification
- **New models**: Add support in `models.py`
- **Bug reports**: Open an issue

## License

MIT
