# SiFR Format Specification

**Version**: 2.0  
**Status**: Draft  
**Last Updated**: 2024-12

## 1. Overview

SiFR (Structured Interface Format for Representation) is a compact format for describing web UI to LLMs. It captures interactive elements, their relationships, and visual hierarchy in a token-efficient structure.

### Design Principles

1. **Semantic over syntactic**: Encode meaning, not markup
2. **Salience-first**: Prioritize what matters for interaction
3. **Relation-aware**: Preserve spatial and logical relationships
4. **Token-efficient**: Minimize tokens while maximizing utility

## 2. File Structure

A SiFR file contains four sections:

```
====METADATA====
(page info, stats)

====NODES====
(elements by salience)

====RELATIONS====
(spatial relationships)

====SUMMARY====
(page overview)
```

## 3. METADATA Section

```yaml
format: sifr-v2.0
url: https://example.com/page
title: Page Title
timestamp: 2024-12-01T10:00:00Z
viewport:
  width: 1920
  height: 1080
stats:
  total_nodes: 150
  high_salience: 8
  med_salience: 42
  low_salience: 100
  clusters: 12
```

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| format | string | Format version (sifr-v2.0) |
| url | string | Source page URL |
| timestamp | ISO8601 | Capture time |
| viewport | object | Browser viewport dimensions |

### Optional Fields

| Field | Type | Description |
|-------|------|-------------|
| title | string | Page title |
| stats | object | Element counts |
| language | string | Page language (en, he, etc.) |

## 4. NODES Section

Elements organized by salience level and type.

```yaml
nodes:
  high:
    button:
      btn001:
        text: "Add to Cart"
        position: [500, 300, 120, 40]
        state: enabled
        actions: [clickable]
        parent: div015
        cluster: cluster003
      btn002:
        text: "Buy Now"
        position: [500, 350, 120, 40]
        state: enabled
        actions: [clickable]
        parent: div015
        cluster: cluster003
    input:
      inp001:
        placeholder: "Search..."
        position: [200, 50, 400, 36]
        state: enabled
        actions: [fillable]
        cluster: cluster001
  med:
    link:
      lnk001:
        text: "View Details"
        href: "/product/123"
        position: [300, 400, 80, 20]
  low:
    text:
      txt001:
        content: "Free shipping on orders over $50"
        position: [100, 600, 300, 16]
```

### Element Structure

| Field | Required | Type | Description |
|-------|----------|------|-------------|
| text | no | string | Visible text content |
| position | no | array | [x, y, width, height] in pixels |
| state | no | enum | enabled, disabled, hidden, readonly |
| actions | no | array | clickable, fillable, scrollable, hoverable |
| parent | no | string | Parent element ID |
| cluster | no | string | Visual cluster ID |
| children | no | array | Child element IDs |

### Salience Levels

| Level | Description | Examples |
|-------|-------------|----------|
| **high** | Primary interactive elements | CTA buttons, main forms, key navigation |
| **med** | Secondary elements | Links, labels, secondary buttons |
| **low** | Supporting content | Static text, decorative elements |

### Element Types

```
button    - Clickable buttons
link      - Anchor links
input     - Text inputs, textareas
select    - Dropdowns, selects
checkbox  - Checkboxes
radio     - Radio buttons
image     - Images with semantic meaning
text      - Static text content
container - Grouping elements (divs, sections)
nav       - Navigation containers
form      - Form containers
```

## 5. RELATIONS Section

Spatial and logical relationships between elements.

```yaml
relations:
  groups:
    nav001:
      orientation: horizontal
      members: [lnk001, lnk002, lnk003, lnk004]
    form001:
      orientation: vertical
      members: [inp001, inp002, btn001]
  
  pairs:
    btn001:
      lbl001: "labeled-by"
      img001: "right-of(12px)"
    inp001:
      lbl002: "labeled-by"
      btn002: "above(8px)"
  
  clusters:
    cluster001:
      role: header
      grid_position: [0-12, 0-1]
      members: [logo001, nav001, inp001]
    cluster002:
      role: main-content
      grid_position: [2-10, 2-10]
      members: [card001, card002, card003]
```

### Relation Types

| Type | Format | Description |
|------|--------|-------------|
| above | above(Npx) | Element is N pixels above |
| below | below(Npx) | Element is N pixels below |
| left-of | left-of(Npx) | Element is N pixels to the left |
| right-of | right-of(Npx) | Element is N pixels to the right |
| inside | inside | Element is contained within |
| labeled-by | labeled-by | Element is labeled by another |
| controls | controls | Element controls another |

## 6. SUMMARY Section

High-level page overview for quick comprehension.

```yaml
summary:
  page:
    purpose: "E-commerce product page"
    primary_action: "Add to Cart"
    key_info: ["price: $29.99", "rating: 4.5/5", "in stock"]
  
  layout:
    grid: 12x12
    regions:
      - id: header
        position: [0-12, 0-1]
        contains: [logo, nav, search, cart]
      - id: main
        position: [0-9, 1-11]
        contains: [product-image, product-info, reviews]
      - id: sidebar
        position: [9-12, 1-11]
        contains: [related-products]
      - id: footer
        position: [0-12, 11-12]
        contains: [links, copyright]
  
  interactive:
    buttons: 5
    links: 23
    inputs: 2
    forms: 1
```

## 7. Detail Levels

SiFR supports three verbosity levels:

### Minimal (for token-constrained contexts)

```yaml
btn001: button "Add to Cart" [500,300,120,40] enabled
btn002: button "Buy Now" [500,350,120,40] enabled
inp001: input "Search..." [200,50,400,36]
```

### Standard (default)

```yaml
btn001:
  type: button
  text: "Add to Cart"
  position: [500, 300, 120, 40]
  state: enabled
  actions: [clickable]
```

### Full (for detailed analysis)

```yaml
btn001:
  type: button
  text: "Add to Cart"
  position: [500, 300, 120, 40]
  state: enabled
  actions: [clickable, hoverable]
  parent: product-card-007
  cluster: cluster003
  nearby: [price-label, qty-selector, wishlist-btn]
  styles:
    bg: "#ff9900"
    fg: "#ffffff"
    font_size: 14
    border_radius: 4
  aria:
    role: button
    label: "Add item to shopping cart"
```

## 8. File Extension

`.sifr`

## 9. MIME Type

`application/vnd.sifr+yaml`

## 10. Validation

A valid SiFR file must:

1. Have METADATA section with required fields
2. Have at least one element in NODES
3. Use valid element types
4. Have unique element IDs
5. Reference only existing elements in RELATIONS

## 11. Examples

See `/examples` directory:
- `product_page.sifr` - E-commerce product page
- `news_article.sifr` - News article page
- `dashboard.sifr` - SaaS dashboard
- `form.sifr` - Multi-step form

## 12. Changelog

### v2.0 (2024-12)
- Added RELATIONS section for spatial relationships
- Added SUMMARY section for quick overview
- Added cluster support for visual grouping
- Defined three detail levels

### v1.0 (2024-11)
- Initial specification
- Basic element structure
- Salience levels
