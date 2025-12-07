"""
Response scoring for agent tasks.
Simple: action succeeded or not.
"""

import re
from typing import Optional


def normalize(text: str) -> str:
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text.lower().strip())


def extract_sifr_id(response: str) -> Optional[str]:
    response = response.strip().lower()
    if re.match(r'^[a-z]{1,4}\d{2,4}$', response):
        return response
    match = re.search(r'\b([a-z]{1,4}\d{2,4})\b', response)
    return match.group(1) if match else None


def extract_selector(response: str) -> Optional[str]:
    response = response.strip()
    if response.startswith(("#", ".", "[")):
        return response.split()[0]
    match = re.search(r'(#[\w-]+)', response)
    return match.group(1) if match else None


def score_response(
    response: str,
    task: dict,
    format_name: str,
    verified: Optional[bool] = None
) -> float:
    """
    Score model response.
    
    If verified is provided (from Playwright), use that directly.
    Otherwise, fall back to target matching.
    
    Returns:
        1.0 = verified success or exact match
        0.5 = partial match (text matches, not verified)
        0.0 = fail
    """
    # If we have Playwright verification result, use it
    if verified is not None:
        return 1.0 if verified else 0.0
    
    # Fallback: match against target
    response = response.strip()
    if response.upper().startswith("ANSWER:"):
        response = response[7:].strip()
    
    if not response or response.lower() == "none":
        return 0.0
    
    target = task.get("target", {})
    target_id = target.get("sifr_id")
    target_selector = target.get("selector")
    target_text = target.get("text") or task.get("answer", "")
    
    # SiFR: match ID
    if format_name == "sifr":
        resp_id = extract_sifr_id(response)
        if resp_id and target_id and resp_id == target_id:
            return 1.0
    
    # HTML: match selector
    elif format_name == "html_raw":
        resp_sel = extract_selector(response)
        if resp_sel and target_selector:
            # Normalize and compare
            if resp_sel.lower() == target_selector.lower():
                return 1.0
            # ID match
            resp_id = re.search(r'#([\w-]+)', resp_sel)
            tgt_id = re.search(r'#([\w-]+)', target_selector)
            if resp_id and tgt_id and resp_id.group(1) == tgt_id.group(1):
                return 1.0
    
    # AXTree: match text
    elif format_name == "axtree":
        if normalize(response) == normalize(target_text):
            return 1.0
        if normalize(target_text) in normalize(response):
            return 0.8
    
    # Text fallback
    if normalize(response) == normalize(target_text):
        return 0.5
    
    return 0.0
