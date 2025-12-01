# sifr-benchmark
Benchmark: how AI agents understand web UI. SiFR vs HTML vs AXTree vs Screenshots. Run it yourself.

# SiFR Spec

Structured format for AI agents to understand web UI.

10-30x smaller than HTML. Higher accuracy. Adjustable detail.

## Why

AI agents need to understand web pages. Current options:
- **HTML**: bloated, noisy, expensive tokens
- **Screenshots**: vision models, slow, expensive
- **AXTree**: incomplete, no visual context

SiFR: clean structure, only actionable elements, works.

## Example
```yaml
btn015:
  type: button
  text: "Add to Cart"
  position: [500, 300, 120, 40]
  state: enabled
```

## Benchmark

See [sifr-benchmark](link) — tested against Tranco Top 500.

SiFR: 78% accuracy
HTML: 45% accuracy
AXTree: 52% accuracy

## Spec

→ [SPEC.md](./SPEC.md)

## License

MIT — format is open.

# SiFR Format Specification

Version: 0.1

## Overview

SiFR (Structured Interface Representation) describes interactive elements on a web page in a format optimized for LLM processing.

## Element Structure

Each element contains:

| Field | Required | Description |
|-------|----------|-------------|
| id | yes | Unique identifier (e.g., btn015) |
| type | yes | Element type |
| text | no | Visible text content |
| position | no | [x, y, width, height] |
| state | no | enabled, disabled, hidden |
| parent | no | Parent element id |
| nearby | no | Related element ids |

## Element Types

- `button`
- `link`
- `input`
- `select`
- `checkbox`
- `radio`
- `text`
- `image`
- `container`

## Detail Levels

### Minimal
```yaml
btn015: button "Add to Cart"
```

### Standard
```yaml
btn015:
  type: button
  text: "Add to Cart"
  position: [500, 300, 120, 40]
  state: enabled
```

### Full
```yaml
btn015:
  type: button
  text: "Add to Cart"
  position: [500, 300, 120, 40]
  state: enabled
  parent: product-card-007
  nearby: [price-label, qty-selector]
```

## File Extension

`.sifr`
