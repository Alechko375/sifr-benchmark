# SiFR Benchmark Protocol v1.0

## Overview

This benchmark evaluates how effectively LLMs understand and interact with web interfaces when given different representation formats.

## Hypothesis

**Pre-computed semantic structure beats raw data for LLM comprehension.**

SiFR embeds meaning (salience, relations, actions) directly into the format, reducing the cognitive load on LLMs and improving task accuracy.

## Formats Tested

| Format | Description | Tokens (typical) |
|--------|-------------|------------------|
| `sifr` | Structured semantic format with salience levels | 1-3K |
| `html_raw` | Complete HTML as-is | 8-15K |
| `html_clean` | HTML with scripts/styles removed | 4-8K |
| `axtree` | Accessibility tree dump | 3-6K |
| `screenshot` | PNG image (vision models) | N/A |

## Test Categories

### 1. Navigation Tasks
Find specific elements or sections on the page.

```
Example: "Where is the search button?"
Scoring: Correct selector/ID = 1, wrong = 0
```

### 2. Extraction Tasks
Extract specific information from the page.

```
Example: "What is the product price?"
Scoring: Exact match = 1, partial = 0.5, wrong = 0
```

### 3. Interaction Tasks
Identify clickable/interactive elements.

```
Example: "List all buttons on this page"
Scoring: Precision/Recall vs ground truth
```

### 4. Summarization Tasks
Describe page content or purpose.

```
Example: "What is this page about?"
Scoring: Key concepts coverage (0-1 scale)
```

### 5. Accessibility Tasks
Find accessibility issues or ARIA information.

```
Example: "Which images lack alt text?"
Scoring: Correct identification rate
```

### 6. Comparison Tasks
Compare elements or identify relationships.

```
Example: "Which product has the highest rating?"
Scoring: Correct ranking = 1, wrong = 0
```

## Test Pages

### Category: E-commerce
- Amazon product page
- Shopify checkout
- eBay listing

### Category: News
- CNN article
- BBC homepage
- Medium post

### Category: SaaS Dashboard
- GitHub repository
- Stripe dashboard (mock)
- Linear issue tracker (mock)

### Category: Forms
- Government form (mock)
- Job application
- Insurance quote

### Category: Social
- Twitter/X feed (mock)
- LinkedIn profile (mock)

## Execution Protocol

### Step 1: Page Collection
```bash
# Capture page in all formats
./capture.sh https://example.com/page

# Output:
# datasets/pages/example/page.html
# datasets/formats/sifr/example_page.sifr
# datasets/formats/html/example_page.html
# datasets/formats/axtree/example_page.json
# datasets/formats/screenshots/example_page.png
```

### Step 2: Ground Truth Annotation
Each page requires human-verified answers for all tasks.

```json
{
  "page_id": "amazon_product_001",
  "tasks": {
    "nav_1": {
      "question": "Where is Add to Cart button?",
      "answer": "btn015",
      "answer_text": "Add to Cart"
    },
    "ext_1": {
      "question": "What is the price?",
      "answer": "$29.99"
    }
  }
}
```

### Step 3: Test Execution
```bash
# Run benchmark
node src/runner.js \
  --models gpt-4o,claude-sonnet,gemini-2 \
  --formats sifr,html_raw,axtree \
  --pages datasets/pages/ecommerce/*.json \
  --output results/run_001/
```

### Step 4: Scoring
```python
def score_response(response, ground_truth, task_type):
    if task_type == "extraction":
        return fuzzy_match(response, ground_truth)
    elif task_type == "navigation":
        return 1.0 if response == ground_truth else 0.0
    elif task_type == "interaction":
        return f1_score(response_elements, truth_elements)
    # ...
```

## Metrics

### Primary Metrics

| Metric | Description |
|--------|-------------|
| **Accuracy** | % of correct answers |
| **Token Efficiency** | Tokens consumed per task |
| **Consistency** | Std deviation across runs |
| **Hallucination Rate** | % of invented elements |

### Composite Score
```
Score = (Accuracy × 0.35) + 
        (1/Tokens × 0.25) + 
        (1 - Hallucination × 0.25) + 
        (Consistency × 0.15)
```

## Statistical Validation

- Minimum 5 runs per model/format combination
- Report mean, std, 95% confidence interval
- Use paired t-test for format comparisons
- Significance threshold: p < 0.01

## Success Criteria

The benchmark validates SiFR if:

1. **Token Efficiency**: SiFR uses >50% fewer tokens than HTML (p<0.01)
2. **Accuracy**: SiFR shows >15% accuracy improvement (p<0.01)
3. **Consistency**: SiFR variance <50% of HTML variance
4. **Cross-Model**: Benefits hold for ≥4/5 models tested

## Anti-Gaming Provisions

1. **No format-specific training**: Test on models without SiFR fine-tuning
2. **Blind evaluation**: Scorers don't know which format produced the response
3. **Diverse pages**: Test across multiple domains and layouts
4. **Negative control**: Include pseudo-SiFR (randomized relations) to validate that structure matters

## Pseudo-SiFR Control

To prove that semantic structure (not just format cleanliness) drives improvements:

```python
def create_pseudo_sifr(real_sifr):
    """Randomize relations while keeping structure intact"""
    pseudo = copy.deepcopy(real_sifr)
    
    # Shuffle salience levels randomly
    all_elements = get_all_elements(pseudo)
    random.shuffle(all_elements)
    reassign_salience(pseudo, all_elements)
    
    # Randomize parent-child relations
    randomize_relations(pseudo)
    
    # Shuffle cluster assignments
    randomize_clusters(pseudo)
    
    return pseudo
```

**Expected result**: Pseudo-SiFR performs *worse* than raw HTML, proving that correct semantic structure is essential.

## Reproducibility

All test artifacts are versioned:
- Page snapshots: `datasets/pages/`
- Ground truth: `benchmark/ground-truth/`
- Model responses: `results/raw/`
- Analysis scripts: `src/analysis/`

Run hash verification:
```bash
./verify.sh results/run_001/
# ✓ All checksums match
```
