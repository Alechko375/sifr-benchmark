"""
Ground truth generation from screenshot + SiFR enrichment.
"""
 
import base64
import json
from pathlib import Path


PROMPT = """Analyze this webpage screenshot for agent automation tasks.

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


def find_in_sifr(sifr_data: dict, text: str) -> dict:
    """Find element by text, return {sifr_id, selector}."""
    text_lower = text.lower().strip()
    details = sifr_data.get("====DETAILS====", {})
    
    for level in ["high", "med", "low"]:
        for elem_type, elements in details.get(level, {}).items():
            if not isinstance(elements, dict):
                continue
            for elem_id, elem in elements.items():
                if not isinstance(elem, dict):
                    continue
                elem_text = elem.get("text", "").lower().strip()
                selector = elem.get("selector")
                if elem_text and selector:
                    if elem_text == text_lower or text_lower in elem_text:
                        return {"sifr_id": elem_id, "selector": selector}
    return {}


def enrich_with_sifr(ground_truth: dict, sifr_path: Path) -> dict:
    """Add SiFR IDs and selectors to tasks."""
    if not sifr_path.exists():
        return ground_truth
    
    try:
        sifr_data = json.loads(sifr_path.read_text(encoding="utf-8"))
    except:
        return ground_truth
    
    # Add URL
    url = sifr_data.get("====METADATA====", {}).get("url")
    if url:
        ground_truth.setdefault("_meta", {})["url"] = url
    
    # Enrich tasks
    for task in ground_truth.get("tasks", []):
        answer = task.get("answer", "")
        match = find_in_sifr(sifr_data, answer)
        task["target"] = {
            "text": answer,
            "sifr_id": match.get("sifr_id"),
            "selector": match.get("selector"),
        }
    
    ground_truth.setdefault("_meta", {})["enriched"] = True
    return ground_truth


def generate_ground_truth(
    screenshot_path: Path,
    sifr_path: Path = None,
    output_path: Path = None
) -> dict:
    """Generate ground truth from screenshot, enrich with SiFR."""
    import os
    from openai import OpenAI
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {"error": "OPENAI_API_KEY not set"}
    
    client = OpenAI(api_key=api_key)
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT},
                    {"type": "image_url", "image_url": {
                        "url": f"data:image/png;base64,{encode_image(screenshot_path)}",
                        "detail": "high"
                    }}
                ]
            }],
            max_tokens=2000,
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
        }
        
        # Enrich
        if sifr_path:
            ground_truth = enrich_with_sifr(ground_truth, sifr_path)
        
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(ground_truth, indent=2, ensure_ascii=False))
        
        return ground_truth
        
    except Exception as e:
        return {"error": str(e)}


def generate_ground_truth_for_page(page_name: str, base_dir: Path = None) -> dict:
    base_dir = Path(base_dir or ".")
    
    screenshot = base_dir / "captures" / "screenshots" / f"{page_name}.png"
    sifr = base_dir / "captures" / "sifr" / f"{page_name}.sifr"
    output = base_dir / "ground-truth" / f"{page_name}.json"
    
    if not screenshot.exists():
        return {"error": f"Screenshot not found: {screenshot}"}
    
    return generate_ground_truth(
        screenshot, 
        sifr if sifr.exists() else None, 
        output
    )
