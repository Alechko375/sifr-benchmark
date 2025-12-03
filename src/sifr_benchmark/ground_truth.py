"""
Ground truth generation using GPT-4o Vision.
"""

import base64
import json
import time
from pathlib import Path

GROUND_TRUTH_PROMPT = """Look at this screenshot of a webpage.

Answer these questions about what you SEE in the image.
Be specific and descriptive. Do NOT use technical terms like CSS selectors or element IDs.
Describe locations as: top-left, top-center, top-right, center, bottom-left, etc.

Questions:

1. TITLE: What is the main heading or title shown on this page?

2. NAVIGATION: Where is the main navigation? Describe its location and what links it contains.

3. SEARCH: Is there a search input? Describe its location and placeholder text.

4. PRIMARY_BUTTON: What is the main action button? Describe its text and location.

5. BUTTONS_LIST: List all visible buttons with their text.

Respond ONLY in this JSON format:
{
  "title": "exact title text",
  "navigation": {
    "location": "top-right",
    "items": ["link1", "link2"]
  },
  "search": {
    "exists": true,
    "location": "center",
    "placeholder": "placeholder text"
  },
  "primary_button": {
    "text": "button text",
    "location": "center"
  },
  "buttons_list": ["button1", "button2"]
}
"""


def encode_image(image_path: Path) -> str:
    """Encode image to base64."""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def generate_ground_truth(screenshot_path: Path, output_path: Path = None) -> dict:
    """
    Generate ground truth from screenshot using GPT-4o Vision.
    
    Args:
        screenshot_path: Path to screenshot PNG
        output_path: Optional path to save ground truth JSON
        
    Returns:
        Ground truth dict
    """
    import os
    from openai import OpenAI
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {"error": "OPENAI_API_KEY not set"}
    
    client = OpenAI(api_key=api_key)
    
    # Encode image
    base64_image = encode_image(screenshot_path)
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": GROUND_TRUTH_PROMPT},
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
            max_tokens=1000,
            temperature=0
        )
        
        # Parse response
        content = response.choices[0].message.content
        
        # Extract JSON from response
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        
        ground_truth = json.loads(content.strip())
        ground_truth["_meta"] = {
            "source": str(screenshot_path),
            "model": "gpt-4o",
            "tokens": response.usage.total_tokens
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
    Generate ground truth for a captured page.
    
    Args:
        page_name: Name of the page (e.g., "google")
        base_dir: Base directory with datasets/formats structure
        
    Returns:
        Ground truth dict
    """
    if base_dir is None:
        base_dir = Path(".")
    
    screenshot_path = base_dir / "datasets" / "formats" / "screenshots" / f"{page_name}.png"
    output_path = base_dir / "benchmark" / "ground-truth" / f"{page_name}.json"
    
    if not screenshot_path.exists():
        return {"error": f"Screenshot not found: {screenshot_path}"}
    
    return generate_ground_truth(screenshot_path, output_path)
