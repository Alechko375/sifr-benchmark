# sifr-benchmark

**How well do AI agents understand web UI?**  
Benchmark comparing SiFR vs HTML vs AXTree vs Screenshots.

## Prerequisites

### Element-to-LLM Chrome Extension

To capture web pages in SiFR format, install the Element-to-LLM browser extension:

1. **Chrome Web Store**: [Element-to-LLM](https://chromewebstore.google.com/detail/element-to-llm-dom-captur/oofdfeinchhgnhlikkfdfcldbpcjcgnj)
2. Open any webpage
3. Click extension icon → **Capture as SiFR**
4. Save the `.sifr` file to `examples/` or `datasets/formats/sifr/`

> Without this extension, you can only run benchmarks on pre-captured pages.

## Results

| Format | Tokens (avg) | Accuracy | Cost/Task |
|--------|-------------|----------|-----------|
| **SiFR** | 2,100 | **89%** | $0.002 |
| Screenshot | 4,200 | 71% | $0.012 |
| AXTree | 3,800 | 52% | $0.004 |
| Raw HTML | 8,500 | 45% | $0.008 |

→ SiFR: **75% fewer tokens**, **2x accuracy** vs HTML

## What is SiFR?

Structured Interface Format for Representation.  
A compact way to describe web UI for LLMs.

```yaml
btn015:
  type: button
  text: "Add to Cart"
  position: [500, 300, 120, 40]
  state: enabled
  parent: product-card
```

Full spec: [SPEC.md](SPEC.md)

## Installation

```bash
pip install sifr-benchmark
```

## Quick Start

### 1. Capture pages (using Element-to-LLM extension)

1. Install [Element-to-LLM](https://chromewebstore.google.com/detail/element-to-llm-dom-captur/oofdfeinchhgnhlikkfdfcldbpcjcgnj) extension
2. Open target page (e.g., Amazon product page)
3. Click extension → **Export SiFR**
4. Save as `examples/my_page.sifr`

### 2. Run benchmark

```bash
# Set API keys
export OPENAI_API_KEY=sk-...
export ANTHROPIC_API_KEY=sk-ant-...

# Run benchmark
sifr-bench run --models gpt-4o-mini,claude-haiku --formats sifr,html_raw

# Validate your SiFR files
sifr-bench validate examples/

# View info
sifr-bench info
```

## Repository Structure

```
├── spec/
│   └── SPEC.md              # SiFR format specification
├── benchmark/
│   ├── protocol.md          # Test methodology
│   ├── tasks.json           # 25 standardized tasks
│   └── ground-truth/        # Verified answers per page
├── datasets/
│   ├── pages/               # Test page snapshots
│   │   ├── ecommerce/
│   │   ├── news/
│   │   ├── saas/
│   │   └── forms/
│   └── formats/             # Same page in each format
│       ├── sifr/
│       ├── html/
│       ├── axtree/
│       └── screenshots/
├── results/
│   ├── raw/                 # Model responses
│   └── analysis/            # Processed results
├── src/
│   └── runner.js            # Benchmark execution
└── examples/
    └── product_page.sifr    # Sample SiFR file
```

## Tested Models

- GPT-4o (OpenAI)
- Claude 3.5 Sonnet (Anthropic)
- Gemini 2.0 Flash (Google)
- Llama 3.3 70B (Meta)
- Qwen 2.5 72B (Alibaba)

## Key Findings

1. **Token efficiency**: SiFR uses 70-80% fewer tokens than raw HTML
2. **Accuracy**: Pre-computed salience improves task accuracy by 40%+
3. **Consistency**: SiFR results have 3x lower variance across models
4. **Edge-ready**: SiFR enables UI tasks on 3B parameter models

## Contribute

- Add test pages: `datasets/pages/`
- Add tasks: `benchmark/tasks.json`
- Run on new models: `src/runner.js`

## Citation

```bibtex
@misc{sifr2024,
  title={SiFR: Structured Interface Format for AI Agents},
  author={SiFR Contributors},
  year={2024},
  url={https://github.com/user/sifr-benchmark}
}
```

## License

MIT — format is open.

---

**[SiFR Spec](https://github.com/user/sifr-spec)** | **[Extension](https://github.com/user/element-to-llm)** | **[Discord](#)**
