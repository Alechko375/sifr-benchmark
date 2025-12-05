"""
Ground truth generation for agent tasks using GPT-4o Vision.
Generates tasks with element IDs as answers.
"""

import base64
import json
from pathlib import Path

AGENT_GROUND_TRUTH_PROMPT = """You are analyzing a webpage screenshot alongside its SiFR representation.

SiFR is a compact format describing UI elements. Each element has an ID like btn001, lnk003, inp001.

Your task: Generate agent tasks where the answer is an element ID from the SiFR.

Look at the screenshot to understand WHAT each element does.
Look at the SiFR to find the correct element ID.

Generate these task types:

1. ACTION_CLICK (3-5 tasks): "What element ID should I click to [action]?"
   - Login/signup buttons
   - Navigation links
   - Submit buttons
   - Menu items

2. ACTION_INPUT (1-2 tasks): "What element ID should I use to [input action]?"
   - Search fields
   - Text inputs

3. ACTION_LOCATE (2-3 tasks): "What element ID contains [content]?"
   - Main heading
   - Specific text or logo

Rules:
- ONLY use element IDs that exist in the SiFR below
- Each answer must be a single element ID (e.g., "btn001", "lnk007", "inp001")
- Tasks should be clear and unambiguous
- Focus on common agent actions: login, search, navigate, submit

Respond ONLY in this JSON format:
{
  "page_title": "detected page title",
  "tasks": [
    {
      "id": "act_01",
      "type": "action_click",
      "question": "What element ID should I click to login?",
      "answer": "lnk007",
      "element_text": "login"
    },
    {
      "id": "act_02", 
      "type": "action_input",
      "question": "What element ID should I use to enter a search query?",
      "answer": "inp001",
      "element_text": "Search"
    }
  ]
}

SiFR content:
```
{sifr_content}
```
"""


def encode_image(image_path: Path) -> str:
    """Encode image to base64."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def load_sifr(sifr_path: Path) -> str:
    """Load SiFR file content."""
    with open(sifr_path, "r", encoding="utf-8") as f:
        return f.read()


def extract_json(text: str) -> str:
    """
    Extract JSON object from text - handles various GPT response formats.
    """
    # Try markdown code blocks first
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
    
    # Find JSON object by matching braces
    start = text.find("{")
    if start == -1:
        return None
    
    # Find matching closing brace
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
    sifr_path: Path,
    output_path: Path = None
) -> dict:
    """
    Generate agent ground truth from screenshot + SiFR.
    
    Args:
        screenshot_path: Path to screenshot PNG
        sifr_path: Path to SiFR file
        output_path: Optional path to save ground truth JSON
        
    Returns:
        Ground truth dict with agent tasks
    """
    import os
    from openai import OpenAI
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {"error": "OPENAI_API_KEY not set"}
    
    client = OpenAI(api_key=api_key)
    
    # Load inputs
    base64_image = encode_image(screenshot_path)
    sifr_content = load_sifr(sifr_path)
    
    # Check if SiFR is empty
    if not sifr_content or len(sifr_content.strip()) < 10:
        return {"error": f"SiFR file is empty or too small: {sifr_path}"}
    
    # Build prompt with SiFR
    prompt = AGENT_GROUND_TRUTH_PROMPT.format(sifr_content=sifr_content)
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
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
        
        # Parse response
        content = response.choices[0].message.content
        
        # Extract JSON from response - robust parsing
        json_str = extract_json(content)
        if not json_str:
            return {"error": f"Could not extract JSON from response: {content[:100]}..."}
        
        ground_truth = json.loads(json_str)
        ground_truth["_meta"] = {
            "screenshot": str(screenshot_path),
            "sifr": str(sifr_path),
            "model": "gpt-4o",
            "tokens": response.usage.total_tokens,
            "mode": "agent"
        }
        
        # Save if output path provided
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
    
    Args:
        page_name: Name of the page (e.g., "news_ycombinator_com")
        base_dir: Base directory with datasets/formats structure
        
    Returns:
        Ground truth dict with agent tasks
    """
    if base_dir is None:
        base_dir = Path(".")
    
    screenshot_path = base_dir / "datasets" / "formats" / "screenshots" / f"{page_name}.png"
    sifr_path = base_dir / "datasets" / "formats" / "sifr" / f"{page_name}.sifr"
    output_path = base_dir / "benchmark" / "ground-truth" / f"{page_name}.json"
    
    if not screenshot_path.exists():
        return {"error": f"Screenshot not found: {screenshot_path}"}
    
    if not sifr_path.exists():
        return {"error": f"SiFR not found: {sifr_path}"}
    
    return generate_ground_truth(screenshot_path, sifr_path, output_path)


# CLI support
if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        page_name = sys.argv[1]
        base_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(".")
        result = generate_ground_truth_for_page(page_name, base_dir)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("Usage: python ground_truth.py <page_name> [base_dir]")
