# SiFR Spec

Structured representation of web UI for AI agents.

## What is SiFR

A format that describes interactive elements on a web page: type, text, position, relationships.

Designed for LLM consumption. Not for humans, not for browsers.

## Example
```yaml
btn015:
  type: button
  text: "Add to Cart"
  position: [500, 300, 120, 40]
```

## Detail Levels

| Level | Contents |
|-------|----------|
| Minimal | id, type, text |
| Standard | + position, style, state |
| Full | + relationships, context |

## Spec

→ [SPEC.md](./SPEC.md)

## Benchmark

→ [sifr-benchmark](link)

## License

MIT
