"""
Semantic scoring for compound tasks.
Verifies answers against actual page data, not exact text match.
"""

import re
import json
from pathlib import Path
from typing import Optional
from difflib import SequenceMatcher


def similarity(a: str, b: str) -> float:
    """Calculate string similarity 0-1."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def extract_page_elements(page_data: dict) -> list[dict]:
    """Extract all elements with text from page data."""
    elements = []
    details = page_data.get("details", page_data.get("====DETAILS====", {}))
    
    for level in ["high", "med", "low"]:
        level_data = details.get(level, {})
        for elem_type, elems in level_data.items():
            if not isinstance(elems, dict):
                continue
            for elem_id, elem in elems.items():
                if not isinstance(elem, dict):
                    continue
                text = elem.get("text", "")
                if text:
                    elements.append({
                        "id": elem_id,
                        "text": text,
                        "selector": elem.get("selector"),
                        "type": elem_type,
                        "level": level,
                    })
    return elements


def extract_numeric_values(page_data: dict) -> dict:
    """Extract elements with numeric values (prices, scores, counts)."""
    data = {
        "prices": [],      # {elem_id, text, value, ...}
        "discounts": [],   # {elem_id, text, value, original, ...}
        "scores": [],      # {elem_id, text, value, ...} - upvotes, ratings
        "counts": [],      # {elem_id, text, value, ...} - comments, reviews
    }
    
    details = page_data.get("details", page_data.get("====DETAILS====", {}))
    
    # Patterns
    price_pattern = re.compile(r'\$[\d,]+\.?\d*')
    discount_pattern = re.compile(r'\$(\d+)\s*off|\b(\d+)%\s*off|save\s*\$(\d+)', re.I)
    score_pattern = re.compile(r'(\d+)\s*(points?|upvotes?|votes?|stars?)', re.I)
    count_pattern = re.compile(r'(\d+)\s*(comments?|reviews?|replies)', re.I)
    
    for level in ["high", "med", "low"]:
        level_data = details.get(level, {})
        for elem_type, elems in level_data.items():
            if not isinstance(elems, dict):
                continue
            for elem_id, elem in elems.items():
                if not isinstance(elem, dict):
                    continue
                text = elem.get("text", "")
                selector = elem.get("selector")
                
                # Prices
                price_match = price_pattern.search(text)
                if price_match:
                    try:
                        value = float(price_match.group().replace("$", "").replace(",", ""))
                        data["prices"].append({
                            "id": elem_id, "text": text, "value": value,
                            "selector": selector, "level": level
                        })
                    except:
                        pass
                
                # Discounts
                discount_match = discount_pattern.search(text)
                if discount_match:
                    try:
                        # Get first non-None group
                        value = next(int(g) for g in discount_match.groups() if g)
                        data["discounts"].append({
                            "id": elem_id, "text": text, "value": value,
                            "selector": selector, "level": level
                        })
                    except:
                        pass
                
                # Scores (upvotes, points)
                score_match = score_pattern.search(text)
                if score_match:
                    try:
                        value = int(score_match.group(1))
                        data["scores"].append({
                            "id": elem_id, "text": text, "value": value,
                            "selector": selector, "level": level
                        })
                    except:
                        pass
                
                # Counts (comments, reviews)
                count_match = count_pattern.search(text)
                if count_match:
                    try:
                        value = int(count_match.group(1))
                        data["counts"].append({
                            "id": elem_id, "text": text, "value": value,
                            "selector": selector, "level": level
                        })
                    except:
                        pass
    
    return data


def clean_response(response: str) -> str:
    """Clean model response to extract key content."""
    response = response.lower().strip()
    
    # Remove common prefixes/patterns
    prefixes = [
        "answer:", "the answer is", "the product is", "the category is",
        "the product with", "the item with", "the element is",
        "i found", "based on", "looking at", "according to",
        "the", "a ", "an ", "\"", "'"
    ]
    for prefix in prefixes:
        if response.startswith(prefix):
            response = response[len(prefix):].strip()
    
    # Remove trailing punctuation
    response = response.rstrip(".,!?\"'")
    
    # Take first line/sentence if multiple
    if "\n" in response:
        response = response.split("\n")[0]
    if ". " in response and len(response) > 100:
        response = response.split(". ")[0]
    
    return response.strip()


def find_element_by_response(response: str, elements: list[dict], threshold: float = 0.3) -> Optional[dict]:
    """Find element that best matches response text."""
    response_clean = clean_response(response)
    
    best_match = None
    best_score = threshold
    
    for elem in elements:
        text = elem.get("text", "").lower().strip()
        if not text:
            continue
        
        # Exact match
        if response_clean == text:
            return elem
        
        # Substring match (either direction)
        if response_clean in text or text in response_clean:
            # Prefer longer matches
            match_len = min(len(response_clean), len(text))
            if match_len > best_score * 100:  # Convert to comparable scale
                best_match = elem
                best_score = match_len / 100
            continue
        
        # Key words from element found in response
        words = [w for w in text.split() if len(w) > 3]
        if words:
            matches = sum(1 for w in words if w in response_clean)
            word_score = matches / len(words)
            if word_score > best_score:
                best_score = word_score
                best_match = elem
        
        # Key words from response found in element
        resp_words = [w for w in response_clean.split() if len(w) > 3]
        if resp_words:
            matches = sum(1 for w in resp_words if w in text)
            word_score = matches / len(resp_words)
            if word_score > best_score:
                best_score = word_score
                best_match = elem
        
        # Similarity as fallback
        sim = similarity(response_clean, text)
        if sim > best_score:
            best_score = sim
            best_match = elem
    
    return best_match


def verify_aggregate_task(
    response: str,
    task_type: str,
    criteria: str,
    page_data: dict
) -> tuple[bool, str]:
    """
    Verify aggregate task answer against actual page data.
    
    Args:
        response: Model's answer
        task_type: "aggregate_click", "filter_click", etc.
        criteria: What we're looking for (the question)
        page_data: Page data with elements
        
    Returns:
        (is_correct, reason)
    """
    numeric_data = extract_numeric_values(page_data)
    elements = extract_page_elements(page_data)
    
    if not elements:
        return False, "No elements found in page data"
    
    # Find what element model mentioned
    mentioned = find_element_by_response(response, elements)
    
    criteria_lower = criteria.lower()
    response_clean = clean_response(response)
    
    # If model says "none found" or similar - check if that's correct
    if any(neg in response_clean for neg in ["no ", "none", "not found", "cannot find", "doesn't have"]):
        # This might be correct if there really are no matching items
        return False, "Model reported no matches found"
    
    # Category/section questions - looser matching
    if "category" in criteria_lower or "section" in criteria_lower:
        # Just verify the response mentions something that could be a category
        category_words = ["electronics", "grocery", "home", "clothing", "appliances", 
                         "furniture", "toys", "sports", "health", "beauty", "office",
                         "automotive", "garden", "food", "pharmacy", "optical"]
        for cat in category_words:
            if cat in response_clean:
                return True, f"Found category: {cat}"
        if mentioned:
            return True, f"Found element: {mentioned['text'][:30]}..."
        return False, "Could not identify category in response"
    
    # "Most" questions (most products, most items, etc.)
    if "most" in criteria_lower:
        if "discount" in criteria_lower or "off" in criteria_lower:
            items = numeric_data["discounts"]
        elif "comment" in criteria_lower:
            items = numeric_data["counts"]
        elif "upvote" in criteria_lower or "point" in criteria_lower:
            items = numeric_data["scores"]
        elif "expensive" in criteria_lower or "price" in criteria_lower:
            items = numeric_data["prices"]
        else:
            # Generic "most" - just check element exists
            if mentioned:
                return True, f"Found element: {mentioned['text'][:30]}..."
            return False, "Could not find mentioned element"
        
        if items:
            top_item = max(items, key=lambda x: x["value"])
            mentioned_in_items = find_element_by_response(response, items)
            if mentioned_in_items:
                sorted_items = sorted(items, key=lambda x: -x["value"])
                top_ids = [item["id"] for item in sorted_items[:3]]
                if mentioned_in_items["id"] in top_ids:
                    return True, f"Correctly identified top item (value: {mentioned_in_items['value']})"
    
    # Highest/top questions
    if "highest" in criteria_lower or "top" in criteria_lower or "best" in criteria_lower:
        if "discount" in criteria_lower or "off" in criteria_lower or "save" in criteria_lower:
            items = numeric_data["discounts"]
        elif "comment" in criteria_lower or "discussion" in criteria_lower:
            items = numeric_data["counts"]
        elif "upvote" in criteria_lower or "point" in criteria_lower or "score" in criteria_lower:
            items = numeric_data["scores"]
        elif "price" in criteria_lower or "expensive" in criteria_lower:
            items = numeric_data["prices"]
        elif "rating" in criteria_lower or "review" in criteria_lower:
            items = numeric_data["scores"]
        else:
            items = []
        
        if items:
            top_item = max(items, key=lambda x: x["value"])
            mentioned_in_items = find_element_by_response(response, items)
            if mentioned_in_items:
                sorted_items = sorted(items, key=lambda x: -x["value"])
                top_ids = [item["id"] for item in sorted_items[:3]]
                if mentioned_in_items["id"] in top_ids:
                    return True, f"Correctly identified top item (value: {mentioned_in_items['value']})"
            return False, f"Not the top item. Top is: {top_item['text'][:40]}..."
    
    # Lowest/cheapest questions
    if "lowest" in criteria_lower or "cheapest" in criteria_lower or "least" in criteria_lower:
        items = numeric_data["prices"] if numeric_data["prices"] else []
        if items:
            bottom_item = min(items, key=lambda x: x["value"])
            mentioned_in_items = find_element_by_response(response, items)
            if mentioned_in_items:
                sorted_items = sorted(items, key=lambda x: x["value"])
                bottom_ids = [item["id"] for item in sorted_items[:3]]
                if mentioned_in_items["id"] in bottom_ids:
                    return True, f"Correctly identified cheapest (${mentioned_in_items['value']})"
            return False, f"Not the cheapest. Cheapest is: {bottom_item['text'][:40]}..."
    
    # Under/below threshold questions
    if "under" in criteria_lower or "below" in criteria_lower or "less than" in criteria_lower:
        threshold_match = re.search(r'\$?(\d+)', criteria_lower)
        if threshold_match:
            threshold = float(threshold_match.group(1))
            items = [p for p in numeric_data["prices"] if p["value"] < threshold]
            if items:
                mentioned_in_items = find_element_by_response(response, items)
                if mentioned_in_items:
                    return True, f"Found item under ${threshold} (${mentioned_in_items['value']})"
            elif not items:
                return False, f"No items under ${threshold} on page"
        return False, "Could not verify price threshold"
    
    # Price questions
    if "price" in criteria_lower or "$" in response_clean:
        # Extract price from response
        price_match = re.search(r'\$?([\d,]+\.?\d*)', response_clean)
        if price_match:
            resp_price = float(price_match.group(1).replace(",", ""))
            # Check if this price exists on page
            for p in numeric_data["prices"]:
                if abs(p["value"] - resp_price) < 0.01:
                    return True, f"Price ${resp_price} found on page"
            return False, f"Price ${resp_price} not found on page"
    
    # Default: just check if mentioned element exists
    if mentioned:
        return True, f"Element found: {mentioned['text'][:40]}..."
    
    return False, "Could not find mentioned element in page"


def score_compound_task(
    understand_response: str,
    act_success: bool,
    task: dict,
    page_data: dict = None
) -> dict:
    """
    Score compound task with semantic verification.
    
    Returns:
        {
            "understand_correct": bool,
            "understand_reason": str,
            "act_success": bool,
            "combined_success": bool,
        }
    """
    understand = task.get("understand", {})
    expected_answer = understand.get("answer", "")
    task_type = task.get("type", "")
    
    # Extract criteria from question
    question = understand.get("question", "")
    
    # Try semantic verification if page_data available
    if page_data:
        is_correct, reason = verify_aggregate_task(
            understand_response, task_type, question, page_data
        )
        return {
            "understand_correct": is_correct,
            "understand_reason": reason,
            "act_success": act_success,
            "combined_success": is_correct and act_success,
        }
    
    # Fallback: fuzzy text matching
    understand_correct = False
    
    # Check exact match
    if expected_answer.lower() in understand_response.lower():
        understand_correct = True
    else:
        # Check similarity
        sim = similarity(expected_answer, understand_response)
        if sim > 0.6:
            understand_correct = True
    
    return {
        "understand_correct": understand_correct,
        "understand_reason": "text match" if understand_correct else "no match",
        "act_success": act_success,
        "combined_success": understand_correct and act_success,
    }


# Legacy scoring for simple tasks
def score_response(response: str, task: dict, format_name: str, verified: bool = None) -> float:
    """Score a simple task response."""
    if verified is not None:
        return 1.0 if verified else 0.0
    
    expected = task.get("target", {}).get("text") or task.get("answer", "")
    if not expected:
        return 0.0
    
    response_clean = response.lower().strip()
    expected_clean = expected.lower().strip()
    
    # Exact match
    if response_clean == expected_clean:
        return 1.0
    
    # Substring match
    if expected_clean in response_clean or response_clean in expected_clean:
        return 1.0
    
    # Similarity
    sim = similarity(response_clean, expected_clean)
    if sim > 0.8:
        return 1.0
    elif sim > 0.6:
        return 0.5
    
    return 0.0
