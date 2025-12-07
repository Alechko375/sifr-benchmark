"""
Playwright-based verification of model responses.
"""

import re
import json
from typing import Optional, Tuple
from playwright.async_api import Page, Locator


class SiFRResolver:
    """Resolve SiFR element IDs to selectors."""
    
    def __init__(self, sifr_content: str):
        try:
            self.data = json.loads(sifr_content)
        except json.JSONDecodeError:
            self.data = {}
    
    def get_selector(self, element_id: str) -> Optional[str]:
        """Resolve element ID (a002) to CSS selector (#logout)."""
        details = self.data.get("====DETAILS====", {})
        
        for level in ["high", "med", "low"]:
            level_data = details.get(level, {})
            for elem_type, elements in level_data.items():
                if isinstance(elements, dict) and element_id in elements:
                    elem = elements[element_id]
                    if isinstance(elem, dict):
                        return elem.get("selector")
        return None
    
    def get_text(self, element_id: str) -> Optional[str]:
        """Get element text by ID."""
        details = self.data.get("====DETAILS====", {})
        
        for level in ["high", "med", "low"]:
            level_data = details.get(level, {})
            for elem_type, elements in level_data.items():
                if isinstance(elements, dict) and element_id in elements:
                    elem = elements[element_id]
                    if isinstance(elem, dict):
                        return elem.get("text")
        return None


def extract_sifr_id(response: str) -> Optional[str]:
    """Extract SiFR element ID from response."""
    response = response.strip().lower()
    if re.match(r'^[a-z]{1,4}\d{2,4}$', response):
        return response
    match = re.search(r'\b([a-z]{1,4}\d{2,4})\b', response)
    return match.group(1) if match else None


def extract_selector(response: str) -> Optional[str]:
    """Extract CSS selector from response."""
    response = response.strip()
    if response.startswith(("#", ".", "[")):
        match = re.match(r'^([#.\[][^\s,]+)', response)
        return match.group(1) if match else response.split()[0]
    match = re.search(r'(#[\w-]+|\.[\w-]+|\[[\w-]+(?:="[^"]*")?\])', response)
    return match.group(1) if match else None


def extract_role_name(response: str) -> Tuple[Optional[str], Optional[str]]:
    """Extract role and name from AXTree response."""
    response = response.strip()
    match = re.search(r'(\w+)\s+"([^"]+)"', response)
    if match:
        return match.group(1).lower(), match.group(2)
    match = re.search(r"(\w+)\s+'([^']+)'", response)
    if match:
        return match.group(1).lower(), match.group(2)
    return None, response


async def resolve_to_locator(
    page: Page,
    response: str,
    format_name: str,
    sifr_resolver: Optional[SiFRResolver] = None
) -> Tuple[Optional[Locator], Optional[str], Optional[str]]:
    """
    Resolve model response to Playwright locator.
    
    Returns: (locator, selector_used, error)
    """
    response = response.strip()
    if response.upper().startswith("ANSWER:"):
        response = response[7:].strip()
    
    if not response or response.lower() == "none":
        return None, None, "Empty response"
    
    if format_name == "sifr":
        elem_id = extract_sifr_id(response)
        if not elem_id:
            return None, None, f"No element ID in: {response[:30]}"
        if not sifr_resolver:
            return None, None, "No SiFR resolver"
        selector = sifr_resolver.get_selector(elem_id)
        if not selector:
            return None, None, f"Cannot resolve: {elem_id}"
        try:
            return page.locator(selector), selector, None
        except Exception as e:
            return None, selector, str(e)
    
    elif format_name == "html_raw" or format_name == "html":
        selector = extract_selector(response)
        if selector:
            try:
                return page.locator(selector), selector, None
            except:
                pass
        # Fallback to text
        try:
            return page.get_by_text(response, exact=False), f"text={response}", None
        except Exception as e:
            return None, None, str(e)
    
    elif format_name == "axtree":
        role, name = extract_role_name(response)
        valid_roles = ["button", "link", "textbox", "checkbox", "menuitem", "tab"]
        if role and role in valid_roles:
            try:
                return page.get_by_role(role, name=name), f"role={role}", None
            except:
                pass
        # Fallback
        try:
            return page.get_by_text(name or response, exact=False), f"text={name}", None
        except Exception as e:
            return None, None, str(e)
    
    return None, None, f"Unknown format: {format_name}"


async def verify_locator(locator: Locator, timeout: int = 3000) -> Tuple[bool, Optional[str]]:
    """
    Verify locator targets a clickable element.
    
    Returns: (success, error)
    """
    try:
        count = await locator.count()
        if count == 0:
            return False, "Not found"
        
        if count > 1:
            locator = locator.first
        
        visible = await locator.is_visible(timeout=timeout)
        if not visible:
            return False, "Not visible"
        
        # Trial click - doesn't actually click
        await locator.click(trial=True, timeout=timeout)
        return True, None
        
    except Exception as e:
        return False, str(e)


async def verify_response(
    page: Page,
    response: str,
    format_name: str,
    sifr_resolver: Optional[SiFRResolver] = None
) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Full verification: resolve + verify.
    
    Returns: (success, selector_used, error)
    """
    locator, selector, error = await resolve_to_locator(
        page, response, format_name, sifr_resolver
    )
    
    if error:
        return False, selector, error
    
    success, verify_error = await verify_locator(locator)
    return success, selector, verify_error
