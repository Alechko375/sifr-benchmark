"""
Ground truth generation for agent tasks using GPT-4o Vision.
Generates tasks from SCREENSHOT ONLY - no SiFR bias.
Answer is element TEXT, not ID - fair for all formats.
"""

import base64
import json
from pathlib import Path

# FAIR prompt - screenshot only, no SiFR!
AGENT_GROUND_TRUTH_PROMPT = """You are analyzing a webpage screenshot to generate agent automation tasks.

Your task: Look at the screenshot and identify interactive UI elements that an agent would need to use.

Generate these task types:

1. ACTION_CLICK (3-5 tasks): "Click the [element description]"
   - Login/signup buttons
   - Navigation links  
   - Submit buttons
   - Menu items

2. ACTION_INPUT (1-2 tasks): "Enter text in the [input description]"
   - Search fields
   - Text inputs
   - Form fields

3. ACTION_LOCATE (2-3 tasks): "Find the [content description]"
   - Main heading
   - Specific text or logo
   - Navigation sections

Rules:
- Look ONLY at the screenshot - describe what you SEE
- Answer must be the EXACT visible text on the element (e.g., "Sign In", "Search", "Add to Cart")
- If element has no text, describe it briefly (e.g., "search icon", "hamburger menu")
- Tasks should be clear and unambiguous
- Focus on common agent actions

Respond ONLY in this JSON format:
{
  "page_title": "detected page title from screenshot",
  "tasks": [
    {
      "id": "act_01",
      "type": "action_click",
      "question": "Click the Sign In button",
      "answer": "Sign In"
    },
    {
      "id": "act_02", 
      "type": "action_input",
      "question": "Enter a search query in the search box",
      "answer": "Search"
    },
    {
      "id": "act_03",
      "type": "action_locate",
      "question": "Find the main page heading",
      "answer": "Welcome to Example"
    }
  ]
}

Important: The "answer" field must contain the VISIBLE TEXT on the element, not any ID or code.
"""


def encode_image(image_path: Path) -> str:
    """Encode image to base64."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def extract_json(text: str) -> str:
    """
    Extract JSON object from text - handles various GPT response formats.
    """
    if "```json" in text:
        try:
            return text.split("```json")[1].split("```")[0].strip()
        except IndexError:
            pass
    
    if "```" in text:
        try:
            return text.split("```")[1].split("```")[0].strip()
        except IndexError:
            pass
    
    start = text.find("{")
    if start == -1:
        return None
    
    depth = 0
    for i, char in enumerate(text[start:], start):
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start:i+1]
    
    return None


def generate_ground_truth(
    screenshot_path: Path, 
    sifr_path: Path = None,  # Not used anymore, kept for compatibility
    output_path: Path = None
) -> dict:
    """
    Generate agent ground truth from screenshot ONLY.
    No SiFR bias - fair benchmark for all formats.
    
    Args:
        screenshot_path: Path to screenshot PNG
        sifr_path: IGNORED - kept for backward compatibility
        output_path: Optional path to save ground truth JSON
        
    Returns:
        Ground truth dict with agent tasks (answers are element TEXT, not IDs)
    """
    import os
    from openai import OpenAI
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {"error": "OPENAI_API_KEY not set"}
    
    client = OpenAI(api_key=api_key)
    
    # Load screenshot only
    base64_image = encode_image(screenshot_path)
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": AGENT_GROUND_TRUTH_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}",
                                "detail": "high"
                            }
                        }
                    ]
                }
            ],
            max_tokens=2000,
            temperature=0
        )
        
        content = response.choices[0].message.content
        
        json_str = extract_json(content)
        if not json_str:
            return {"error": f"Could not extract JSON from response: {content[:100]}..."}
        
        ground_truth = json.loads(json_str)
        
        # Add element_text field (same as answer for compatibility)
        for task in ground_truth.get("tasks", []):
            task["element_text"] = task.get("answer", "")
        
        ground_truth["_meta"] = {
            "screenshot": str(screenshot_path),
            "model": "gpt-4o",
            "tokens": response.usage.total_tokens,
            "mode": "agent_fair",  # Mark as fair mode
            "bias_free": True
        }
        
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(ground_truth, f, indent=2, ensure_ascii=False)
        
        return ground_truth
        
    except Exception as e:
        return {"error": str(e)}


def generate_ground_truth_for_page(page_name: str, base_dir: Path = None) -> dict:
    """
    Generate agent ground truth for a captured page.
    Uses screenshot ONLY - no SiFR bias.
    """
    if base_dir is None:
        base_dir = Path(".")
    
    # Try multiple screenshot locations
    screenshot_paths = [
        base_dir / "captures" / "screenshots" / f"{page_name}.png",
        base_dir / "datasets" / "formats" / "screenshots" / f"{page_name}.png",
    ]
    
    screenshot_path = None
    for path in screenshot_paths:
        if path.exists():
            screenshot_path = path
            break
    
    if not screenshot_path:
        return {"error": f"Screenshot not found in: {screenshot_paths}"}
    
    output_path = base_dir / "ground-truth" / f"{page_name}.json"
    
    return generate_ground_truth(screenshot_path, output_path=output_path)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        page_name = sys.argv[1]
        base_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(".")
        result = generate_ground_truth_for_page(page_name, base_dir)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("Usage: python ground_truth.py <page_name> [base_dir]")
