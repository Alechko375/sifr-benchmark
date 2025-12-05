"""
Response scoring for agent tasks.
Focus: Element ID matching.
"""

import re


def extract_element_ids(text: str) -> set:
    """
    Extract element IDs from text.
    Matches patterns like: btn001, lnk007, inp001, txt042
    """
    if not text:
        return set()
    # Match word boundary + letters + digits
    ids = re.findall(r'\b([a-z]{2,4}\d{2,4})\b', text.lower())
    return set(ids)


def score_agent_task(response: str, expected: str) -> float:
    """
    Score agent task response.
    
    Simple rules:
    - Exact ID match → 1.0
    - Expected ID found in response → 1.0
    - Partial overlap (for multi-ID tasks) → proportional
    - No match → 0.0
    
    Args:
        response: Model's response (may contain explanation + ID)
        expected: Expected element ID (e.g., "btn001" or "btn001, btn002")
        
    Returns:
        Score from 0.0 to 1.0
    """
    if not expected:
        return 0.0
    
    # Extract IDs from both
    expected_ids = extract_element_ids(expected)
    response_ids = extract_element_ids(response)
    
    if not expected_ids:
        # Expected wasn't an ID - fallback to text match
        return 1.0 if expected.lower().strip() in response.lower() else 0.0
    
    if not response_ids:
        # Model didn't return any IDs
        return 0.0
    
    # Single expected ID - check if it's in response
    if len(expected_ids) == 1:
        expected_id = list(expected_ids)[0]
        if expected_id in response_ids:
            return 1.0
        return 0.0
    
    # Multiple expected IDs - calculate overlap
    intersection = expected_ids & response_ids
    if not intersection:
        return 0.0
    
    # F1-style score for multi-ID tasks
    precision = len(intersection) / len(response_ids)
    recall = len(intersection) / len(expected_ids)
    f1 = 2 * precision * recall / (precision + recall)
    
    return f1


def score_response(response: str, expected: str, task_type: str = "action") -> float:
    """
    Main scoring function.
    
    Args:
        response: Model's response
        expected: Expected answer
        task_type: Task type from ground truth
        
    Returns:
        Score from 0.0 to 1.0
    """
    if not expected or expected.lower() in ("n/a", "none", "not_applicable"):
        return 0.0
    
    # All agent tasks use ID matching
    if task_type.startswith("action"):
        return score_agent_task(response, expected)
    
    # Fallback for any other task type
    return score_agent_task(response, expected)


# Quick test
if __name__ == "__main__":
    tests = [
        # (response, expected, expected_score)
        ("btn001", "btn001", 1.0),
        ("Click on btn001 to login", "btn001", 1.0),
        ("The login button is btn001", "btn001", 1.0),
        ("I would click btn002", "btn001", 0.0),
        ("btn001, btn002, btn003", "btn001, btn002", 0.8),  # partial
        ("Click the login button", "btn001", 0.0),  # no ID in response
        ("lnk007", "lnk007", 1.0),
        ("Use inp001 for search", "inp001", 1.0),
    ]
    
    print("Scoring tests:")
    for resp, exp, expected_score in tests:
        score = score_agent_task(resp, exp)
        status = "✅" if abs(score - expected_score) < 0.1 else "❌"
        print(f"{status} '{resp}' vs '{exp}' → {score:.1f} (expected {expected_score})")
