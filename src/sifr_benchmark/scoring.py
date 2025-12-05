"""
Response scoring for agent tasks.
Supports both element ID matching and text matching.
"""
import re


def extract_element_ids(text: str) -> set:
    """
    Extract element IDs from text.
    Matches patterns like: btn001, lnk007, inp001, a010
    """
    if not text:
        return set()
    # Match word boundary + letters + digits (including short IDs like a010)
    ids = re.findall(r'\b([a-z]{1,4}\d{2,4})\b', text.lower())
    return set(ids)


def score_agent_task(response: str, expected: str, element_text: str = "") -> float:
    """
    Score agent task response.
    
    Rules:
    - Exact ID match → 1.0
    - Expected ID found in response → 1.0
    - element_text found in response → 1.0 (for HTML/AXTree)
    - Partial overlap (for multi-ID tasks) → proportional
    - No match → 0.0
    
    Args:
        response: Model's response (may contain explanation + ID)
        expected: Expected element ID (e.g., "a010")
        element_text: Expected element text (e.g., "login") for fallback matching
        
    Returns:
        Score from 0.0 to 1.0
    """
    if not expected:
        return 0.0
    
    response_lower = response.lower().strip()
    
    # Extract IDs from both
    expected_ids = extract_element_ids(expected)
    response_ids = extract_element_ids(response)
    
    # Check ID match first
    if expected_ids and response_ids:
        if len(expected_ids) == 1:
            if list(expected_ids)[0] in response_ids:
                return 1.0
        else:
            # Multiple expected IDs - calculate overlap
            intersection = expected_ids & response_ids
            if intersection:
                precision = len(intersection) / len(response_ids)
                recall = len(intersection) / len(expected_ids)
                return 2 * precision * recall / (precision + recall)
    
    # Fallback: check element_text match (for HTML/AXTree)
    if element_text:
        element_text_lower = element_text.lower().strip()
        # Exact match or response contains the text
        if response_lower == element_text_lower:
            return 1.0
        if element_text_lower in response_lower:
            return 0.8  # Partial credit for containing the text
    
    # Last fallback: expected wasn't an ID, try text match
    if not expected_ids:
        if expected.lower().strip() in response_lower:
            return 1.0
    
    return 0.0


def score_response(response: str, expected: str, task_type: str = "action", element_text: str = "") -> float:
    """
    Main scoring function.
    
    Args:
        response: Model's response
        expected: Expected answer
        task_type: Task type from ground truth
        element_text: Expected element text for fallback matching
        
    Returns:
        Score from 0.0 to 1.0
    """
    if not expected or expected.lower() in ("n/a", "none", "not_applicable"):
        return 0.0
    
    # All agent tasks use ID + text matching
    return score_agent_task(response, expected, element_text)


# Quick test
if __name__ == "__main__":
    tests = [
        # (response, expected, element_text, expected_score)
        ("a010", "a010", "login", 1.0),
        ("Click on a010 to login", "a010", "login", 1.0),
        ("login", "a010", "login", 1.0),  # HTML returns text, should match!
        ("Login", "a010", "login", 1.0),  # Case insensitive
        ("The login button", "a010", "login", 0.8),  # Contains text
        ("submit", "a010", "login", 0.0),  # Wrong text
        ("none", "a010", "login", 0.0),  # No match
        ("btn001", "btn001", "", 1.0),
        ("a001, a002, a003", "a001, a002", "", 0.8),  # Partial overlap
    ]
    
    print("Scoring tests:")
    for resp, exp, elem_text, expected_score in tests:
        score = score_agent_task(resp, exp, elem_text)
        status = "✅" if abs(score - expected_score) < 0.15 else "❌"
        print(f"{status} '{resp}' vs '{exp}' (text='{elem_text}') → {score:.1f} (expected {expected_score})")
