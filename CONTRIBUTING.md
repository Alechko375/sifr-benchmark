# Contributing to SiFR Benchmark

Thanks for your interest in improving the benchmark! Here's how to help.

## Ways to Contribute

### 1. Add Test Pages

We need diverse pages across domains. To add a page:

```bash
# 1. Capture page in all formats
./scripts/capture.sh https://example.com/page page_name

# 2. Create ground truth annotations
cp benchmark/ground-truth/template.json benchmark/ground-truth/page_name.json
# Edit to add correct answers for all tasks

# 3. Submit PR
git checkout -b add-page-name
git add datasets/ benchmark/ground-truth/
git commit -m "Add page_name test case"
```

**Page requirements:**
- Publicly accessible (no login required)
- Representative of its category
- Has interactive elements (buttons, forms, links)
- English language preferred (for v1)

### 2. Add New Tasks

Tasks live in `benchmark/tasks.json`. To add:

```json
{
  "id": "new_01",
  "category": "extraction|navigation|interaction|summarization|accessibility|comparison",
  "question": "Clear, specific question",
  "scoring": "element_id|text_match|numeric|precision_recall|semantic",
  "difficulty": "easy|medium|hard",
  "applicable_to": ["ecommerce", "news"]  // optional
}
```

**Task requirements:**
- Unambiguous question
- Objectively scoreable
- Applicable to multiple page types (unless domain-specific)

### 3. Run on New Models

We want results from more models. To contribute:

```bash
# Run benchmark with your model
node src/runner.js --models your-model --output results/your-model/

# Submit results
git checkout -b results-your-model
git add results/your-model/
git commit -m "Add benchmark results for your-model"
```

**Requirements:**
- Use default tasks and pages
- Run minimum 3 times per configuration
- Include raw results and summary

### 4. Improve the Runner

The benchmark runner (`src/runner.js`) can always be improved:

- Add new model providers
- Improve scoring functions
- Add analysis scripts
- Fix bugs

## Code Style

- JavaScript: Prettier with default config
- Markdown: 80 char line width
- JSON: 2-space indent
- YAML (SiFR files): 2-space indent

## Pull Request Process

1. Fork the repo
2. Create feature branch (`git checkout -b feature/thing`)
3. Make changes
4. Run validation (`npm run validate`)
5. Commit with clear message
6. Open PR with description of changes

## Ground Truth Annotation Guidelines

When annotating ground truth:

1. **Be specific**: Use element IDs when possible
2. **Handle edge cases**: Note when answer is "not_visible" or "not_applicable"
3. **Add notes**: Explain scoring nuances
4. **Test yourself**: Try answering from SiFR file alone

Example annotation:
```json
{
  "ext_02": {
    "question": "What is the price shown on this page?",
    "answer": "$149.99",
    "answer_element": "txt001",
    "notes": "Price includes currency symbol"
  }
}
```

## Questions?

Open an issue or start a discussion. We're happy to help!

## License

By contributing, you agree that your contributions will be licensed under MIT.
