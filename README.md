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
