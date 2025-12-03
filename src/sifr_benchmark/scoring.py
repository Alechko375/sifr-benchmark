"""
Response scoring functions.
"""

import re
from difflib import SequenceMatcher


def normalize_text(text: str) -> str:
    """Normalize text for comparison."""
    if not text:
        return ""
    # Lowercase, remove extra whitespace, strip punctuation
    text = text.lower().strip()
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\w\s]', '', text)
    return text


def fuzzy_match(a: str, b: str, threshold: float = 0.8) -> float:
    """
    Fuzzy string matching.
    Returns 1.0 for exact match, 0.5 for partial, 0.0 for no match.
    """
    a_norm = normalize_text(a)
    b_norm = normalize_text(b)
    
    if not a_norm or not b_norm:
        return 0.0
    
    # Exact match
    if a_norm == b_norm:
        return 1.0
    
    # One contains the other
    if a_norm in b_norm or b_norm in a_norm:
        return 0.5
    
    # Sequence similarity
    ratio = SequenceMatcher(None, a_norm, b_norm).ratio()
    if ratio >= threshold:
        return 1.0
    elif ratio >= threshold * 0.7:
        return 0.5
    
    return 0.0


def score_element_id(response: str, expected: str) -> float:
    """Score element ID match."""
    resp_norm = normalize_text(response)
    exp_norm = normalize_text(expected)
    
    if not exp_norm:
        return 0.0
    
    # Check if expected ID appears in response
    if exp_norm in resp_norm:
        return 1.0
    
    # Check individual IDs
    expected_ids = set(re.findall(r'\b[a-z]+\d+\b', exp_norm))
    response_ids = set(re.findall(r'\b[a-z]+\d+\b', resp_norm))
    
    if expected_ids and expected_ids.issubset(response_ids):
        return 1.0
    
    if expected_ids & response_ids:
        return 0.5
    
    return 0.0


def score_numeric(response: str, expected: str) -> float:
    """Score numeric match."""
    # Extract numbers from both
    resp_nums = re.findall(r'[\d.]+', response)
    exp_nums = re.findall(r'[\d.]+', expected)
    
    if not exp_nums:
        return 0.0
    
    try:
        exp_val = float(exp_nums[0])
        for num in resp_nums:
            if float(num) == exp_val:
                return 1.0
    except ValueError:
        pass
    
    return 0.0


def score_precision_recall(response: str, expected: str) -> float:
    """
    Score as F1 of element sets.
    Expected format: "elem1, elem2, elem3"
    """
    # Parse comma-separated lists
    resp_items = set(normalize_text(item) for item in response.split(",") if item.strip())
    exp_items = set(normalize_text(item) for item in expected.split(",") if item.strip())
    
    if not exp_items:
        return 0.0
    
    if not resp_items:
        return 0.0
    
    # Calculate precision and recall
    intersection = resp_items & exp_items
    precision = len(intersection) / len(resp_items) if resp_items else 0
    recall = len(intersection) / len(exp_items) if exp_items else 0
    
    # F1 score
    if precision + recall == 0:
        return 0.0
    
    f1 = 2 * precision * recall / (precision + recall)
    return f1


def score_response(response: str, expected: str, scoring_type: str) -> float:
    """
    Score a response against expected answer.
    
    Args:
        response: Model's response
        expected: Expected answer
        scoring_type: One of: element_id, text_match, numeric, precision_recall, semantic
        
    Returns:
        Score from 0.0 to 1.0
    """
    if not expected or expected.lower() in ("not_applicable", "not_visible", "n/a"):
        # Skip tasks without ground truth
        return 0.0
    
    if scoring_type == "element_id":
        return score_element_id(response, expected)
    
    elif scoring_type == "text_match":
        return fuzzy_match(response, expected)
    
    elif scoring_type == "numeric":
        return score_numeric(response, expected)
    
    elif scoring_type == "precision_recall":
        return score_precision_recall(response, expected)
    
    elif scoring_type == "semantic":
        # For semantic scoring, use fuzzy match as fallback
        # Could integrate LLM-as-judge here
        return fuzzy_match(response, expected, threshold=0.6)
    
    else:
        # Default to fuzzy text match
        return fuzzy_match(response, expected)
