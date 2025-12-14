"""
Ground truth generation for SiFR Benchmark.
"""

import base64
import json
from pathlib import Path
from typing import Optional, Union


COMPOUND_PROMPT = """Analyze this webpage screenshot. Generate COMPOUND tasks that require UNDERSTANDING first, then ACTION.

Each compound task has 2 parts:
- UNDERSTAND: Question requiring analysis/comprehension of page content
- ACT: Action based on the understanding

## Task Types:

1. AGGREGATE → CLICK (2-3 tasks)
   Examples:
   - "Which item has the highest price?" → "Click on it"
   - "Which news story has the most upvotes?" → "Click to open it"

2. FILTER → CLICK (1-2 tasks)
   Examples:
   - "Find a product under $50" → "Click to view details"

3. RELATE → CLICK (1-2 tasks)
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
        "answer": "Example Story Title",
        "reasoning": "Compared all visible vote counts"
      },
      "act": {
        "question": "Click on that story",
        "target_text": "Example Story Title"
      }
    }
  ],
  "simple_tasks": [
    {"id": "act_01", "type": "action_click", "question": "Click login", "answer": "login"}
  ]
}

Generate 4-6 compound tasks and 2-3 simple tasks.
"""


DEV_PROMPT = """Analyze this webpage screenshot. Generate tasks for FRONTEND DEVELOPERS.

## Task Types:

1. SELECTOR (2-3 tasks)
   - "What's a stable selector for the main CTA button?"
   - "Generate a selector for the search input"

2. ACCESSIBILITY (2-3 tasks)
   - "Which buttons are missing aria-labels?"
   - "Find images without alt text"

3. STRUCTURE (1-2 tasks)
   - "What elements are inside the navigation?"
   - "How many form fields are on the page?"

4. TESTING (1-2 tasks)
   - "Find all buttons that submit forms"
   - "List all links in the footer"

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
    }
  ]
}

Generate 6-8 dev tasks covering all types.
"""


DESIGN_PROMPT = """Analyze this webpage screenshot. Generate tasks for UI/UX DESIGNERS.

## Task Types:

1. SPACING (2-3 tasks)
   - "What's the approximate height of the hero section?"
   - "Are all cards the same height?"

2. TYPOGRAPHY (1-2 tasks)
   - "How many different font sizes are visible?"
   - "What's the largest heading on the page?"

3. CONSISTENCY (2-3 tasks)
   - "Are all primary buttons the same style?"
   - "How many button variants exist?"

4. HIERARCHY (1-2 tasks)
   - "What's the main CTA on the page?"
   - "What elements compete for attention?"

5. COLOR (1-2 tasks)
   - "What's the primary brand color used?"
   - "Are all CTAs the same color?"

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
    }
  ]
}

Generate 6-8 design tasks covering all types.
"""


COMBINED_PROMPT = """Analyze this webpage screenshot. Generate tasks for THREE audiences:

1. COMPOUND TASKS (for AI agents) - Understanding + Action pairs
2. DEV TASKS (for frontend developers) - Selectors, accessibility, structure
3. DESIGN TASKS (for UI/UX designers) - Spacing, typography, consistency

## COMPOUND TASKS (4-5 tasks):
Types: aggregate_click, filter_click, relate_click

## DEV TASKS (4-5 tasks):
Types: selector, accessibility, structure, testing

## DESIGN TASKS (4-5 tasks):
Types: spacing, typography, consistency, hierarchy, color

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


def encode_image(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode("utf-8")


def encode_image_bytes(data: bytes) -> str:
    return base64.b64encode(data).decode("utf-8")


def find_in_page_data(page_data: dict, text: str) -> dict:
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


def enrich_ground_truth(ground_truth: dict, page_data: dict) -> dict:
    """Enrich ground truth with element IDs from page data (in-memory version)."""
    if not page_data:
        return ground_truth
    
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
    
    # Enrich design tasks
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
    
    # Add inventory
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


def enrich_with_page_data(ground_truth: dict, page_data_path: Path) -> dict:
    """Enrich ground truth with element IDs from page data (file-based version)."""
    if not page_data_path.exists():
        return ground_truth
    
    try:
        page_data = json.loads(page_data_path.read_text(encoding="utf-8"))
    except:
        return ground_truth
    
    return enrich_ground_truth(ground_truth, page_data)


def parse_json_response(content: str) -> dict:
    """Extract JSON from LLM response."""
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
    
    return json.loads(content)


def generate_ground_truth_from_data(
    screenshot_bytes: bytes,
    sifr_data: Optional[dict] = None,
    output_path: Optional[Path] = None,
    mode: str = "compound"
) -> dict:
    """
    Generate ground truth from in-memory data.
    Used by single-session benchmark to avoid file I/O.
    
    Args:
        screenshot_bytes: PNG screenshot as bytes
        sifr_data: Parsed SiFR data (dict), optional
        output_path: Where to save result (optional)
        mode: Task generation mode
    
    Returns:
        Ground truth dict
    """
    import os
    from openai import OpenAI
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {"error": "OPENAI_API_KEY not set"}
    
    client = OpenAI(api_key=api_key)
    
    prompts = {
        "compound": COMPOUND_PROMPT,
        "dev": DEV_PROMPT,
        "design": DESIGN_PROMPT,
        "combined": COMBINED_PROMPT,
    }
    prompt = prompts.get(mode, COMPOUND_PROMPT)
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {
                        "url": f"data:image/png;base64,{encode_image_bytes(screenshot_bytes)}",
                        "detail": "high"
                    }}
                ]
            }],
            max_tokens=4000,
            temperature=0
        )
        
        content = response.choices[0].message.content
        ground_truth = parse_json_response(content)
        
        ground_truth["_meta"] = {
            "model": "gpt-4o",
            "tokens": response.usage.total_tokens,
            "mode": mode,
        }
        
        # Enrich with SiFR data if available
        if sifr_data:
            ground_truth = enrich_ground_truth(ground_truth, sifr_data)
        
        # Save if path provided
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(ground_truth, indent=2, ensure_ascii=False))
        
        return ground_truth
        
    except json.JSONDecodeError as e:
        return {"error": f"Failed to parse JSON: {e}"}
    except Exception as e:
        return {"error": str(e)}


def generate_ground_truth(
    screenshot_path: Path,
    page_data_path: Path = None,
    output_path: Path = None,
    mode: str = "combined"
) -> dict:
    """Generate ground truth from file paths (original interface)."""
    import os
    from openai import OpenAI
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {"error": "OPENAI_API_KEY not set"}
    
    # Read screenshot and delegate to in-memory version
    screenshot_bytes = screenshot_path.read_bytes()
    
    sifr_data = None
    if page_data_path and page_data_path.exists():
        try:
            sifr_data = json.loads(page_data_path.read_text(encoding="utf-8"))
        except:
            pass
    
    result = generate_ground_truth_from_data(
        screenshot_bytes=screenshot_bytes,
        sifr_data=sifr_data,
        output_path=output_path,
        mode=mode
    )
    
    # Add screenshot path to meta
    if "_meta" in result:
        result["_meta"]["screenshot"] = str(screenshot_path)
    
    return result


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
