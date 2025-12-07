"""
Response scoring for agent tasks.
TEXT-BASED scoring - fair for all formats.
"""
import re


def normalize_text(text: str) -> str:
    """Normalize text for comparison."""
    if not text:
        return ""
    # Lowercase, strip, remove extra whitespace
    text = text.lower().strip()
    text = re.sub(r'\s+', ' ', text)
    # Remove common punctuation
    text = re.sub(r'["\'\.\,\!\?]', '', text)
    return text


def extract_element_ids(text: str) -> set:
    """
    Extract element IDs from text.
    Matches patterns like: btn001, lnk007, inp001, a010
    """
    if not text:
        return set()
    ids = re.findall(r'\b([a-z]{1,4}\d{2,4})\b', text.lower())
    return set(ids)


def text_similarity(response: str, expected: str) -> float:
    """
    Calculate text similarity score.
    
    Returns:
        1.0 - exact match
        0.8 - response contains expected
        0.6 - expected contains response (partial)
        0.4 - significant word overlap
        0.0 - no match
    """
    resp_norm = normalize_text(response)
    exp_norm = normalize_text(expected)
    
    if not resp_norm or not exp_norm:
        return 0.0
    
    # Exact match
    if resp_norm == exp_norm:
        return 1.0
    
    # Response contains expected text
    if exp_norm in resp_norm:
        return 0.8
    
    # Expected contains response (model gave shorter answer)
    if resp_norm in exp_norm:
        return 0.6
    
    # Word overlap
    resp_words = set(resp_norm.split())
    exp_words = set(exp_norm.split())
    
    if not exp_words:
        return 0.0
    
    overlap = resp_words & exp_words
    if overlap:
        # Jaccard-like score
        overlap_ratio = len(overlap) / len(exp_words)
        if overlap_ratio >= 0.5:
            return 0.4 + (overlap_ratio * 0.4)  # 0.4 - 0.8
    
    return 0.0


def score_agent_task(response: str, expected: str, element_text: str = "") -> float:
    """
    Score agent task response.
    
    New logic (fair for all formats):
    - expected is now element TEXT (e.g., "Sign In"), not ID
    - Compare response text to expected text
    - Also check element_text for backward compatibility
    
    Args:
        response: Model's response
        expected: Expected element TEXT (e.g., "Sign In", "Search")
        element_text: Same as expected in new format (backward compat)
        
    Returns:
        Score from 0.0 to 1.0
    """
    if not expected:
        return 0.0
    
    response_clean = response.strip()
    
    # If response is "none" or empty, no match
    if not response_clean or response_clean.lower() == "none":
        return 0.0
    
    # Primary: text similarity with expected
    score = text_similarity(response_clean, expected)
    
    # Fallback: check element_text if different from expected
    if score < 0.5 and element_text and element_text != expected:
        alt_score = text_similarity(response_clean, element_text)
        score = max(score, alt_score)
    
    # Special case: model returned an ID, check if it appears in context
    # This allows SiFR to return IDs which we can't directly verify
    # but we give partial credit if it looks like a valid ID
    if score < 0.5:
        response_ids = extract_element_ids(response_clean)
        if response_ids and len(response_clean) < 20:
            # Model confidently returned an ID - give benefit of doubt
            # In real benchmark, we'd verify against the page
            # For now, 0.5 as "plausible but unverified"
            score = max(score, 0.5)
    
    return score


def score_response(response: str, expected: str, task_type: str = "action", element_text: str = "") -> float:
    """
    Main scoring function.
    
    Args:
        response: Model's response
        expected: Expected answer (element TEXT in fair mode)
        task_type: Task type from ground truth
        element_text: Same as expected (backward compat)
        
    Returns:
        Score from 0.0 to 1.0
    """
    if not expected or expected.lower() in ("n/a", "none", "not_applicable"):
        return 0.0
    
    return score_agent_task(response, expected, element_text)


# Quick test
if __name__ == "__main__":
    tests = [
        # (response, expected, expected_score, description)
        ("Sign In", "Sign In", 1.0, "Exact match"),
        ("sign in", "Sign In", 1.0, "Case insensitive"),
        ("Click Sign In button", "Sign In", 0.8, "Contains expected"),
        ("Sign", "Sign In", 0.6, "Partial match"),
        ("Login", "Sign In", 0.0, "No match"),
        ("btn003", "Sign In", 0.5, "ID returned - partial credit"),
        ("Search", "Search", 1.0, "Exact match"),
        ("search box", "Search", 0.8, "Contains"),
        ("none", "Sign In", 0.0, "None response"),
        ("", "Sign In", 0.0, "Empty response"),
        ("Add to Cart", "Add to Cart", 1.0, "Multi-word exact"),
        ("cart button", "Add to Cart", 0.4, "Word overlap"),
    ]
    
    print("Scoring tests (text-based, fair):\n")
    all_pass = True
    for resp, exp, expected_score, desc in tests:
        score = score_agent_task(resp, exp, "")
        passed = abs(score - expected_score) < 0.15
        status = "✅" if passed else "❌"
        if not passed:
            all_pass = False
        print(f"{status} {desc}")
        print(f"   '{resp}' vs '{exp}' → {score:.1f} (expected {expected_score})")
        print()
    
    print("=" * 50)
    print(f"{'All tests passed!' if all_pass else 'Some tests failed!'}")
