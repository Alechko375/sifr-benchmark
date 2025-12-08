"""
Ground truth generation for FOMO benchmark.
Compound tasks: UNDERSTAND → ACT
"""
 
import base64
import json"""
Ground truth generation for FOMO benchmark.
Supports: Compound tasks, Dev tasks, Design tasks
"""
 
import base64
import json
from pathlib import Path


# =============================================================================
# COMPOUND TASKS: Understanding + Action (original)
# =============================================================================

COMPOUND_PROMPT = """Analyze this webpage screenshot. Generate COMPOUND tasks that require UNDERSTANDING first, then ACTION.

Each compound task has 2 parts:
- UNDERSTAND: Question requiring analysis/comprehension of page content
- ACT: Action based on the understanding

## Task Types:

1. AGGREGATE → CLICK (2-3 tasks)
   Understanding requires comparing/aggregating data across elements.
   Examples:
   - "Which item has the highest price?" → "Click on it"
   - "Which news story has the most upvotes?" → "Click to open it"

2. FILTER → CLICK (1-2 tasks)
   Understanding requires filtering by criteria.
   Examples:
   - "Find a product under $50" → "Click to view details"

3. RELATE → CLICK (1-2 tasks)
   Understanding requires connecting related elements.
   Examples:
   - "What category is the cheapest item in?" → "Click that category"

## Rules:
- UNDERSTAND answer must be SPECIFIC (exact text, number, name)
- ACT target must be an actual clickable element
- Only generate tasks where answer is VISIBLE on page

## JSON Format:
{
  "page_title": "...",
  "page_type": "news/ecommerce/portal/other",
  "compound_tasks": [
    {
      "id": "cmp_01",
      "type": "aggregate_click",
      "understand": {
        "question": "Which news story has the most upvotes?",
        "answer": "Show HN: SiFR Format",
        "reasoning": "Compared all visible vote counts"
      },
      "act": {
        "question": "Click on that story",
        "target_text": "Show HN: SiFR Format"
      }
    }
  ],
  "simple_tasks": [
    {"id": "act_01", "type": "action_click", "question": "Click login", "answer": "login"}
  ]
}

Generate 4-6 compound tasks and 2-3 simple tasks.
"""


# =============================================================================
# DEV TASKS: For frontend developers
# =============================================================================

DEV_PROMPT = """Analyze this webpage screenshot. Generate tasks that a FRONTEND DEVELOPER would need for automation, testing, and debugging.

## Task Types:

1. SELECTOR (2-3 tasks)
   Find stable, unique selectors for elements.
   Examples:
   - "What's a stable selector for the main CTA button?"
   - "Generate a selector for the search input"
   - "Find the submit button in the form"

2. ACCESSIBILITY (2-3 tasks)
   Identify accessibility issues or audit elements.
   Examples:
   - "Which buttons are missing aria-labels?"
   - "Find images without alt text"
   - "Are all form inputs properly labeled?"

3. STRUCTURE (1-2 tasks)
   Analyze DOM/component structure.
   Examples:
   - "What elements are inside the navigation?"
   - "List all interactive elements in the header"
   - "How many form fields are on the page?"

4. TESTING (1-2 tasks)
   Tasks useful for E2E testing.
   Examples:
   - "Find all buttons that submit forms"
   - "What's the login flow sequence?"
   - "List all links in the footer"

## Rules:
- Answers must be SPECIFIC and VERIFIABLE
- For selectors: prefer IDs, data-attributes, or unique text
- For accessibility: reference actual visible elements
- For structure: count or list actual elements

## JSON Format:
{
  "page_title": "...",
  "page_type": "...",
  "dev_tasks": [
    {
      "id": "dev_01",
      "type": "selector",
      "question": "What's a stable selector for the login button?",
      "answer": "Sign In",
      "target_element": "button with text 'Sign In' in header"
    },
    {
      "id": "dev_02",
      "type": "accessibility",
      "question": "Which images are missing alt text?",
      "answer": "3 images",
      "details": ["hero banner", "product thumbnail", "avatar"]
    },
    {
      "id": "dev_03",
      "type": "structure",
      "question": "How many navigation links are in the header?",
      "answer": "7",
      "details": ["Home", "Products", "Pricing", "About", "Blog", "Support", "Contact"]
    }
  ]
}

Generate 6-8 dev tasks covering all types.
"""


# =============================================================================
# DESIGN TASKS: For UI/UX designers
# =============================================================================

DESIGN_PROMPT = """Analyze this webpage screenshot. Generate tasks that a UI/UX DESIGNER would need for design audits and consistency checks.

## Task Types:

1. SPACING (2-3 tasks)
   Measure spacing, padding, margins between elements.
   Examples:
   - "What's the approximate height of the hero section?"
   - "Are all cards the same height?"
   - "What's the gap between navigation items?"

2. TYPOGRAPHY (1-2 tasks)
   Analyze font usage and text hierarchy.
   Examples:
   - "How many different font sizes are visible?"
   - "What's the largest heading on the page?"
   - "Is body text consistently sized?"

3. CONSISTENCY (2-3 tasks)
   Check design system consistency.
   Examples:
   - "Are all primary buttons the same style?"
   - "How many button variants exist?"
   - "Are icons consistently sized?"

4. HIERARCHY (1-2 tasks)
   Analyze visual hierarchy and layout.
   Examples:
   - "What's the main CTA on the page?"
   - "What elements compete for attention?"
   - "Is the visual flow clear?"

5. COLOR (1-2 tasks)
   Check color usage and contrast.
   Examples:
   - "What's the primary brand color used?"
   - "Are all CTAs the same color?"
   - "Is there sufficient contrast on text?"

## Rules:
- Answers should be SPECIFIC and MEASURABLE where possible
- Use approximate pixel values for dimensions
- Reference actual visible elements
- Note inconsistencies when found

## JSON Format:
{
  "page_title": "...",
  "page_type": "...",
  "design_tasks": [
    {
      "id": "des_01",
      "type": "spacing",
      "question": "What's the approximate height of the hero section?",
      "answer": "~500px",
      "reasoning": "Based on viewport proportion"
    },
    {
      "id": "des_02",
      "type": "consistency",
      "question": "Are all product cards the same width?",
      "answer": "Yes, 4 equal columns",
      "details": "Grid layout with consistent card sizing"
    },
    {
      "id": "des_03",
      "type": "typography",
      "question": "How many heading levels are visible?",
      "answer": "3",
      "details": ["Main hero title", "Section headings", "Card titles"]
    }
  ]
}

Generate 6-8 design tasks covering all types.
"""


# =============================================================================
# COMBINED PROMPT: All task types
# =============================================================================

COMBINED_PROMPT = """Analyze this webpage screenshot. Generate tasks for THREE audiences:

1. COMPOUND TASKS (for AI agents) - Understanding + Action pairs
2. DEV TASKS (for frontend developers) - Selectors, accessibility, structure
3. DESIGN TASKS (for UI/UX designers) - Spacing, typography, consistency

## COMPOUND TASKS (4-5 tasks):
Types: aggregate_click, filter_click, relate_click
Example: "Which product has best rating?" → "Click to view it"

## DEV TASKS (4-5 tasks):
Types: selector, accessibility, structure, testing
Example: "What's a stable selector for the checkout button?"

## DESIGN TASKS (4-5 tasks):
Types: spacing, typography, consistency, hierarchy, color
Example: "Are all primary buttons the same size?"

## Rules:
- All answers must be SPECIFIC and VERIFIABLE
- Reference actual visible elements
- For dimensions: use approximate pixel values
- For counts: be exact

## JSON Format:
{
  "page_title": "...",
  "page_type": "news/ecommerce/saas/portal/other",
  
  "compound_tasks": [
    {
      "id": "cmp_01",
      "type": "aggregate_click",
      "understand": {"question": "...", "answer": "..."},
      "act": {"question": "...", "target_text": "..."}
    }
  ],
  
  "dev_tasks": [
    {
      "id": "dev_01",
      "type": "selector|accessibility|structure|testing",
      "question": "...",
      "answer": "...",
      "details": "..." 
    }
  ],
  
  "design_tasks": [
    {
      "id": "des_01",
      "type": "spacing|typography|consistency|hierarchy|color",
      "question": "...",
      "answer": "...",
      "reasoning": "..."
    }
  ],
  
  "simple_tasks": [
    {"id": "act_01", "type": "action_click", "question": "...", "answer": "..."}
  ]
}

Generate comprehensive tasks for all three audiences.
"""


# =============================================================================
# Helper functions
# =============================================================================

def encode_image(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("utf-8")


def find_in_page_data(page_data: dict, text: str) -> dict:
    """Find element by text in page data, return {elem_id, selector, bbox}."""
    if not text:
        return {}
    text_lower = text.lower().strip()
    
    details = page_data.get("details", page_data.get("====DETAILS====", {}))
    
    for level in ["high", "med", "low"]:
        level_data = details.get(level, {})
        for elem_type, elements in level_data.items():
            if not isinstance(elements, dict):
                continue
            for elem_id, elem in elements.items():
                if not isinstance(elem, dict):
                    continue
                elem_text = elem.get("text", "").lower().strip()
                selector = elem.get("selector")
                bbox = elem.get("bbox")
                if elem_text and (elem_text == text_lower or text_lower in elem_text):
                    return {
                        "elem_id": elem_id, 
                        "selector": selector,
                        "bbox": bbox
                    }
    return {}


def extract_elements_by_type(page_data: dict, elem_types: list) -> list:
    """Extract all elements of given types with their bbox."""
    elements = []
    details = page_data.get("details", page_data.get("====DETAILS====", {}))
    
    for level in ["high", "med", "low"]:
        level_data = details.get(level, {})
        for elem_type, elems in level_data.items():
            if elem_type not in elem_types:
                continue
            if not isinstance(elems, dict):
                continue
            for elem_id, elem in elems.items():
                if isinstance(elem, dict):
                    elements.append({
                        "id": elem_id,
                        "type": elem_type,
                        "text": elem.get("text", ""),
                        "bbox": elem.get("bbox"),
                        "selector": elem.get("selector")
                    })
    return elements


def enrich_with_page_data(ground_truth: dict, page_data_path: Path) -> dict:
    """Enrich all task types with element IDs, selectors, and bbox from page data."""
    if not page_data_path.exists():
        return ground_truth
    
    try:
        page_data = json.loads(page_data_path.read_text(encoding="utf-8"))
    except:
        return ground_truth
    
    # Add URL from metadata
    metadata = page_data.get("metadata", page_data.get("====METADATA====", {}))
    url = metadata.get("url")
    if url:
        ground_truth.setdefault("_meta", {})["url"] = url
    
    # Enrich compound tasks
    for task in ground_truth.get("compound_tasks", []):
        target_text = task.get("act", {}).get("target_text", "")
        match = find_in_page_data(page_data, target_text)
        task["act"]["target"] = {
            "text": target_text,
            "elem_id": match.get("elem_id"),
            "selector": match.get("selector"),
            "bbox": match.get("bbox"),
        }
        
        answer = task.get("understand", {}).get("answer", "")
        answer_match = find_in_page_data(page_data, str(answer))
        task["understand"]["target"] = {
            "text": answer,
            "elem_id": answer_match.get("elem_id"),
            "selector": answer_match.get("selector"),
            "bbox": answer_match.get("bbox"),
        }
    
    # Enrich dev tasks
    for task in ground_truth.get("dev_tasks", []):
        answer = task.get("answer", "")
        if isinstance(answer, str):
            match = find_in_page_data(page_data, answer)
            task["target"] = {
                "text": answer,
                "elem_id": match.get("elem_id"),
                "selector": match.get("selector"),
                "bbox": match.get("bbox"),
            }
    
    # Enrich design tasks (add bbox data for dimension questions)
    for task in ground_truth.get("design_tasks", []):
        answer = task.get("answer", "")
        if isinstance(answer, str):
            match = find_in_page_data(page_data, answer)
            if match:
                task["target"] = {
                    "text": answer,
                    "elem_id": match.get("elem_id"),
                    "bbox": match.get("bbox"),
                }
    
    # Enrich simple tasks
    for task in ground_truth.get("simple_tasks", []):
        answer = task.get("answer", "")
        match = find_in_page_data(page_data, answer)
        task["target"] = {
            "text": answer,
            "elem_id": match.get("elem_id"),
            "selector": match.get("selector"),
            "bbox": match.get("bbox"),
        }
    
    # Add element inventory for dev/design reference
    buttons = extract_elements_by_type(page_data, ["button", "btn"])
    links = extract_elements_by_type(page_data, ["a", "link"])
    inputs = extract_elements_by_type(page_data, ["input", "textarea"])
    images = extract_elements_by_type(page_data, ["img", "image"])
    
    ground_truth.setdefault("_meta", {})["inventory"] = {
        "buttons": len(buttons),
        "links": len(links),
        "inputs": len(inputs),
        "images": len(images),
    }
    
    ground_truth["_meta"]["enriched"] = True
    return ground_truth


# =============================================================================
# Main generation function
# =============================================================================

def generate_ground_truth(
    screenshot_path: Path,
    page_data_path: Path = None,
    output_path: Path = None,
    mode: str = "combined"  # "compound", "dev", "design", "combined"
) -> dict:
    """Generate ground truth from screenshot, enrich with page data."""
    import os
    from openai import OpenAI
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {"error": "OPENAI_API_KEY not set"}
    
    client = OpenAI(api_key=api_key)
    
    # Select prompt based on mode
    prompts = {
        "compound": COMPOUND_PROMPT,
        "dev": DEV_PROMPT,
        "design": DESIGN_PROMPT,
        "combined": COMBINED_PROMPT,
    }
    prompt = prompts.get(mode, COMBINED_PROMPT)
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {
                        "url": f"data:image/png;base64,{encode_image(screenshot_path)}",
                        "detail": "high"
                    }}
                ]
            }],
            max_tokens=4000,
            temperature=0
        )
        
        content = response.choices[0].message.content
        
        # Extract JSON
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        
        start = content.find("{")
        if start >= 0:
            depth = 0
            for i, c in enumerate(content[start:], start):
                depth += (c == "{") - (c == "}")
                if depth == 0:
                    content = content[start:i+1]
                    break
        
        ground_truth = json.loads(content)
        ground_truth["_meta"] = {
            "screenshot": str(screenshot_path),
            "model": "gpt-4o",
            "tokens": response.usage.total_tokens,
            "mode": mode,
        }
        
        # Enrich with page data
        if page_data_path:
            ground_truth = enrich_with_page_data(ground_truth, page_data_path)
        
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(ground_truth, indent=2, ensure_ascii=False))
        
        return ground_truth
        
    except Exception as e:
        return {"error": str(e)}


def generate_ground_truth_for_page(
    page_name: str, 
    base_dir: Path = None,
    mode: str = "combined"
) -> dict:
    base_dir = Path(base_dir or ".")
    
    screenshot = base_dir / "captures" / "screenshots" / f"{page_name}.png"
    page_data = base_dir / "captures" / "sifr" / f"{page_name}.sifr"
    output = base_dir / "ground-truth" / f"{page_name}.json"
    
    if not screenshot.exists():
        return {"error": f"Screenshot not found: {screenshot}"}
    
    return generate_ground_truth(
        screenshot, 
        page_data if page_data.exists() else None, 
        output,
        mode=mode
    )
from pathlib import Path


# =============================================================================
# Compound tasks: Understanding + Action
# =============================================================================

COMPOUND_PROMPT = """Analyze this webpage screenshot. Generate COMPOUND tasks that require UNDERSTANDING first, then ACTION.

Each compound task has 2 parts:
- UNDERSTAND: Question requiring analysis/comprehension of page content
- ACT: Action based on the understanding

## Task Types:

1. AGGREGATE → CLICK (2-3 tasks)
   Understanding requires comparing/aggregating data across elements.
   Examples:
   - "Which item has the highest price?" → "Click on it"
   - "Which news story has the most upvotes?" → "Click to open it"
   - "Which product has the best rating?" → "Add it to cart"

2. FILTER → CLICK (1-2 tasks)
   Understanding requires filtering by criteria.
   Examples:
   - "Find a news story about AI" → "Click to read it"
   - "Find a product under $50" → "Click to view details"

3. RELATE → CLICK (1-2 tasks)
   Understanding requires connecting related elements.
   Examples:
   - "Find the comments count for the top story" → "Click comments"
   - "What category is the cheapest item in?" → "Click that category"

## Rules:
- UNDERSTAND answer must be SPECIFIC (exact text, number, name)
- UNDERSTAND must require REASONING, not just finding
- ACT must depend on UNDERSTAND result
- ACT target must be an actual clickable element
- Only generate tasks where answer is VISIBLE and VERIFIABLE on page

## JSON Format:
{
  "page_title": "...",
  "page_type": "news/ecommerce/portal/other",
  "compound_tasks": [
    {
      "id": "cmp_01",
      "type": "aggregate_click",
      "understand": {
        "question": "Which news story has the most upvotes?",
        "answer": "Show HN: SiFR Format",
        "answer_value": 342,
        "reasoning": "Compared all visible vote counts, 342 is highest"
      },
      "act": {
        "question": "Click on that story to open it",
        "target_text": "Show HN: SiFR Format"
      }
    }
  ],
  "simple_tasks": [
    {"id": "act_01", "type": "action_click", "question": "Click login", "answer": "login"}
  ]
}

Generate 4-6 compound tasks and 2-3 simple tasks.
Compound tasks are the PRIMARY focus - they test understanding.
"""


# =============================================================================
# Legacy prompt for backwards compatibility
# =============================================================================

SIMPLE_PROMPT = """Analyze this webpage screenshot for agent automation tasks.

Generate:
1. ACTION_CLICK (3-5): "Click the [element]" - buttons, links, menu items
2. ACTION_INPUT (1-2): "Enter text in [field]" - search, forms  
3. ACTION_LOCATE (2-3): "Find the [content]" - headings, logos

Rules:
- Answer = EXACT visible text on element
- If no text, describe briefly ("search icon")
- Clear, unambiguous tasks only

JSON format:
{
  "page_title": "...",
  "tasks": [
    {"id": "act_01", "type": "action_click", "question": "Click the Sign In button", "answer": "Sign In"}
  ]
}
"""


def encode_image(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("utf-8")


def find_in_page_data(page_data: dict, text: str) -> dict:
    """Find element by text in page data, return {elem_id, selector}."""
    text_lower = text.lower().strip()
    
    # Try different possible structures
    details = page_data.get("details", page_data.get("====DETAILS====", {}))
    
    for level in ["high", "med", "low"]:
        level_data = details.get(level, {})
        for elem_type, elements in level_data.items():
            if not isinstance(elements, dict):
                continue
            for elem_id, elem in elements.items():
                if not isinstance(elem, dict):
                    continue
                elem_text = elem.get("text", "").lower().strip()
                selector = elem.get("selector")
                if elem_text and selector:
                    if elem_text == text_lower or text_lower in elem_text:
                        return {"elem_id": elem_id, "selector": selector}
    return {}


def extract_aggregatable_data(page_data: dict) -> dict:
    """Extract data that can be aggregated (scores, prices, ratings, etc.)."""
    data = {
        "scores": [],      # {text, value, elem_id, selector}
        "prices": [],
        "ratings": [],
        "counts": [],
    }
    
    details = page_data.get("details", page_data.get("====DETAILS====", {}))
    
    import re
    price_pattern = re.compile(r'\$[\d,]+\.?\d*')
    score_pattern = re.compile(r'(\d+)\s*(points?|upvotes?|votes?|score)', re.I)
    rating_pattern = re.compile(r'(\d+\.?\d*)\s*(stars?|rating|\/\s*5)', re.I)
    
    for level in ["high", "med", "low"]:
        level_data = details.get(level, {})
        for elem_type, elements in level_data.items():
            if not isinstance(elements, dict):
                continue
            for elem_id, elem in elements.items():
                if not isinstance(elem, dict):
                    continue
                text = elem.get("text", "")
                selector = elem.get("selector")
                
                # Check for prices
                price_match = price_pattern.search(text)
                if price_match:
                    try:
                        value = float(price_match.group().replace("$", "").replace(",", ""))
                        data["prices"].append({
                            "text": text, "value": value,
                            "elem_id": elem_id, "selector": selector
                        })
                    except:
                        pass
                
                # Check for scores
                score_match = score_pattern.search(text)
                if score_match:
                    try:
                        value = int(score_match.group(1))
                        data["scores"].append({
                            "text": text, "value": value,
                            "elem_id": elem_id, "selector": selector
                        })
                    except:
                        pass
                        
    return data


def enrich_with_page_data(ground_truth: dict, page_data_path: Path) -> dict:
    """Enrich compound tasks with element IDs and selectors from page data."""
    if not page_data_path.exists():
        return ground_truth
    
    try:
        page_data = json.loads(page_data_path.read_text(encoding="utf-8"))
    except:
        return ground_truth
    
    # Add URL from metadata
    metadata = page_data.get("metadata", page_data.get("====METADATA====", {}))
    url = metadata.get("url")
    if url:
        ground_truth.setdefault("_meta", {})["url"] = url
    
    # Extract aggregatable data for verification
    agg_data = extract_aggregatable_data(page_data)
    ground_truth.setdefault("_meta", {})["aggregatable"] = {
        k: len(v) for k, v in agg_data.items()
    }
    
    # Enrich compound tasks
    for task in ground_truth.get("compound_tasks", []):
        # Find target for ACT
        target_text = task.get("act", {}).get("target_text", "")
        match = find_in_page_data(page_data, target_text)
        task["act"]["target"] = {
            "text": target_text,
            "elem_id": match.get("elem_id"),
            "selector": match.get("selector"),
        }
        
        # Store verification data
        understand = task.get("understand", {})
        answer = understand.get("answer", "")
        answer_match = find_in_page_data(page_data, answer)
        task["understand"]["target"] = {
            "text": answer,
            "elem_id": answer_match.get("elem_id"),
            "selector": answer_match.get("selector"),
        }
    
    # Enrich simple tasks (legacy)
    for task in ground_truth.get("simple_tasks", []):
        answer = task.get("answer", "")
        match = find_in_page_data(page_data, answer)
        task["target"] = {
            "text": answer,
            "elem_id": match.get("elem_id"),
            "selector": match.get("selector"),
        }
    
    # Also enrich legacy "tasks" if present
    for task in ground_truth.get("tasks", []):
        answer = task.get("answer", "")
        match = find_in_page_data(page_data, answer)
        task["target"] = {
            "text": answer,
            "elem_id": match.get("elem_id"),
            "selector": match.get("selector"),
        }
    
    ground_truth.setdefault("_meta", {})["enriched"] = True
    return ground_truth


def generate_ground_truth(
    screenshot_path: Path,
    page_data_path: Path = None,
    output_path: Path = None,
    mode: str = "compound"  # "compound" or "simple"
) -> dict:
    """Generate ground truth from screenshot, enrich with page data."""
    import os
    from openai import OpenAI
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {"error": "OPENAI_API_KEY not set"}
    
    client = OpenAI(api_key=api_key)
    prompt = COMPOUND_PROMPT if mode == "compound" else SIMPLE_PROMPT
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {
                        "url": f"data:image/png;base64,{encode_image(screenshot_path)}",
                        "detail": "high"
                    }}
                ]
            }],
            max_tokens=3000,
            temperature=0
        )
        
        content = response.choices[0].message.content
        
        # Extract JSON
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        
        start = content.find("{")
        if start >= 0:
            depth = 0
            for i, c in enumerate(content[start:], start):
                depth += (c == "{") - (c == "}")
                if depth == 0:
                    content = content[start:i+1]
                    break
        
        ground_truth = json.loads(content)
        ground_truth["_meta"] = {
            "screenshot": str(screenshot_path),
            "model": "gpt-4o",
            "tokens": response.usage.total_tokens,
            "mode": mode,
        }
        
        # Enrich with page data
        if page_data_path:
            ground_truth = enrich_with_page_data(ground_truth, page_data_path)
        
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(ground_truth, indent=2, ensure_ascii=False))
        
        return ground_truth
        
    except Exception as e:
        return {"error": str(e)}


def generate_ground_truth_for_page(
    page_name: str, 
    base_dir: Path = None,
    mode: str = "compound"
) -> dict:
    base_dir = Path(base_dir or ".")
    
    screenshot = base_dir / "captures" / "screenshots" / f"{page_name}.png"
    page_data = base_dir / "captures" / "sifr" / f"{page_name}.sifr"
    output = base_dir / "ground-truth" / f"{page_name}.json"
    
    if not screenshot.exists():
        return {"error": f"Screenshot not found: {screenshot}"}
    
    return generate_ground_truth(
        screenshot, 
        page_data if page_data.exists() else None, 
        output,
        mode=mode
    )
