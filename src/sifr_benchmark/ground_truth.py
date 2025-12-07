"""
Ground truth generation for FOMO benchmark.
Compound tasks: UNDERSTAND → ACT
"""
 
import base64
import json
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
