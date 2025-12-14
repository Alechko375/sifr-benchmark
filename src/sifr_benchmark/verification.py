"""
Playwright-based verification of model responses.
With detailed logging for debugging act_success failures.
"""

import re
import json
import logging
from typing import Optional, Tuple
from playwright.async_api import Page, Locator

# Setup logger
logger = logging.getLogger("sifr.verification")


class VerificationResult:
    """Detailed verification result for analysis."""
    
    def __init__(self):
        self.success = False
        self.response_raw = ""
        self.element_id = None
        self.selector = None
        self.selector_source = None  # "sifr", "css", "text", "role"
        self.element_found = False
        self.element_count = 0
        self.element_visible = False
        self.element_clickable = False
        self.error = None
        self.error_stage = None  # "parse", "resolve", "find", "visible", "click"
    
    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "response_raw": self.response_raw,
            "element_id": self.element_id,
            "selector": self.selector,
            "selector_source": self.selector_source,
            "element_found": self.element_found,
            "element_count": self.element_count,
            "element_visible": self.element_visible,
            "element_clickable": self.element_clickable,
            "error": self.error,
            "error_stage": self.error_stage,
        }
    
    def __str__(self):
        if self.success:
            return f"✓ {self.selector} (via {self.selector_source})"
        stages = []
        if self.element_id:
            stages.append(f"id={self.element_id}")
        if self.selector:
            stages.append(f"sel={self.selector[:30]}")
        if self.element_found:
            stages.append(f"found={self.element_count}")
        if self.element_visible:
            stages.append("visible")
        return f"✗ [{self.error_stage}] {self.error} | {' → '.join(stages)}"


class SiFRResolver:
    """Resolve SiFR element IDs to selectors."""
    
    def __init__(self, sifr_content: str):
        try:
            self.data = json.loads(sifr_content)
            self._build_index()
        except json.JSONDecodeError:
            self.data = {}
            self._index = {}
    
    def _build_index(self):
        """Build flat index of all elements for fast lookup."""
        self._index = {}
        details = self.data.get("====DETAILS====", self.data.get("details", {}))
        
        for level in ["high", "med", "low"]:
            level_data = details.get(level, {})
            for elem_type, elements in level_data.items():
                if isinstance(elements, dict):
                    for elem_id, elem in elements.items():
                        if isinstance(elem, dict):
                            self._index[elem_id] = {
                                "selector": elem.get("selector"),
                                "text": elem.get("text"),
                                "type": elem_type,
                                "level": level,
                                "bbox": elem.get("bbox"),
                            }
        
        logger.debug(f"SiFR index built: {len(self._index)} elements")
    
    def get_selector(self, element_id: str) -> Optional[str]:
        """Resolve element ID to CSS selector."""
        elem = self._index.get(element_id)
        if elem:
            return elem.get("selector")
        
        # Try case-insensitive
        for eid, elem in self._index.items():
            if eid.lower() == element_id.lower():
                return elem.get("selector")
        
        return None
    
    def get_text(self, element_id: str) -> Optional[str]:
        """Get element text by ID."""
        elem = self._index.get(element_id)
        return elem.get("text") if elem else None
    
    def get_element(self, element_id: str) -> Optional[dict]:
        """Get full element data by ID."""
        return self._index.get(element_id)
    
    def list_ids(self) -> list[str]:
        """List all available element IDs."""
        return list(self._index.keys())
    
    def find_similar_ids(self, element_id: str, limit: int = 5) -> list[str]:
        """Find similar element IDs (for debugging typos)."""
        prefix = re.match(r'^([a-z]+)', element_id)
        if prefix:
            prefix = prefix.group(1)
            similar = [eid for eid in self._index.keys() if eid.startswith(prefix)]
            return sorted(similar)[:limit]
        return []


def extract_sifr_id(response: str) -> Optional[str]:
    """Extract SiFR element ID from response."""
    response = response.strip()
    
    # Direct ID match (case insensitive)
    if re.match(r'^[a-zA-Z]{1,4}\d{2,4}$', response):
        return response.lower()
    
    # ID in text
    match = re.search(r'\b([a-zA-Z]{1,4}\d{2,4})\b', response)
    if match:
        return match.group(1).lower()
    
    # Edge case: just letters like "a" - invalid
    if re.match(r'^[a-zA-Z]+$', response):
        logger.warning(f"Response '{response}' looks like incomplete ID (missing numbers)")
        return None
    
    return None


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
    sifr_resolver: Optional[SiFRResolver] = None,
    result: Optional[VerificationResult] = None
) -> Tuple[Optional[Locator], Optional[str], Optional[str]]:
    """
    Resolve model response to Playwright locator.
    
    Returns: (locator, selector_used, error)
    """
    if result is None:
        result = VerificationResult()
    
    response = response.strip()
    result.response_raw = response
    
    # Clean ANSWER: prefix
    if response.upper().startswith("ANSWER:"):
        response = response[7:].strip()
    
    if not response or response.lower() == "none":
        result.error = "Empty response"
        result.error_stage = "parse"
        return None, None, result.error
    
    # === SiFR Format ===
    if format_name == "sifr":
        elem_id = extract_sifr_id(response)
        result.element_id = elem_id
        
        if not elem_id:
            result.error = f"No valid element ID in response: '{response[:50]}'"
            result.error_stage = "parse"
            logger.warning(f"[SiFR] {result.error}")
            return None, None, result.error
        
        if not sifr_resolver:
            result.error = "No SiFR resolver provided"
            result.error_stage = "resolve"
            return None, None, result.error
        
        selector = sifr_resolver.get_selector(elem_id)
        result.selector = selector
        result.selector_source = "sifr"
        
        if not selector:
            # Debug: show similar IDs
            similar = sifr_resolver.find_similar_ids(elem_id)
            available = f"Similar IDs: {similar}" if similar else f"Total IDs: {len(sifr_resolver.list_ids())}"
            result.error = f"Cannot resolve ID '{elem_id}' to selector. {available}"
            result.error_stage = "resolve"
            logger.warning(f"[SiFR] {result.error}")
            return None, None, result.error
        
        logger.debug(f"[SiFR] Resolved {elem_id} → {selector}")
        
        try:
            return page.locator(selector), selector, None
        except Exception as e:
            result.error = f"Invalid selector '{selector}': {e}"
            result.error_stage = "resolve"
            return None, selector, result.error
    
    # === HTML Format ===
    elif format_name in ("html_raw", "html"):
        selector = extract_selector(response)
        if selector:
            result.selector = selector
            result.selector_source = "css"
            try:
                return page.locator(selector), selector, None
            except:
                pass
        
        # Fallback to text
        result.selector = f"text={response[:30]}"
        result.selector_source = "text"
        try:
            return page.get_by_text(response, exact=False), result.selector, None
        except Exception as e:
            result.error = str(e)
            result.error_stage = "resolve"
            return None, None, result.error
    
    # === AXTree Format ===
    elif format_name == "axtree":
        role, name = extract_role_name(response)
        valid_roles = ["button", "link", "textbox", "checkbox", "menuitem", "tab", "heading"]
        
        if role and role in valid_roles:
            result.selector = f"role={role}[name='{name}']"
            result.selector_source = "role"
            try:
                return page.get_by_role(role, name=name), result.selector, None
            except:
                pass
        
        # Fallback to text
        result.selector = f"text={name or response}"
        result.selector_source = "text"
        try:
            return page.get_by_text(name or response, exact=False), result.selector, None
        except Exception as e:
            result.error = str(e)
            result.error_stage = "resolve"
            return None, None, result.error
    
    # === Screenshot Format ===
    elif format_name == "screenshot":
        # Screenshots can only use text matching
        result.selector = f"text={response[:50]}"
        result.selector_source = "text"
        try:
            return page.get_by_text(response, exact=False), result.selector, None
        except Exception as e:
            result.error = str(e)
            result.error_stage = "resolve"
            return None, None, result.error
    
    result.error = f"Unknown format: {format_name}"
    result.error_stage = "resolve"
    return None, None, result.error


async def verify_locator(
    locator: Locator, 
    timeout: int = 3000,
    result: Optional[VerificationResult] = None
) -> Tuple[bool, Optional[str]]:
    """
    Verify locator targets a clickable element.
    
    Returns: (success, error)
    """
    if result is None:
        result = VerificationResult()
    
    try:
        # Stage 1: Find element
        count = await locator.count()
        result.element_count = count
        
        if count == 0:
            result.error = "Element not found on page"
            result.error_stage = "find"
            logger.debug(f"[Verify] Not found: {result.selector}")
            return False, result.error
        
        result.element_found = True
        logger.debug(f"[Verify] Found {count} element(s)")
        
        if count > 1:
            locator = locator.first
            logger.debug(f"[Verify] Using first of {count} matches")
        
        # Stage 2: Check visibility
        try:
            visible = await locator.is_visible(timeout=timeout)
        except Exception as e:
            result.error = f"Visibility check failed: {e}"
            result.error_stage = "visible"
            return False, result.error
        
        if not visible:
            result.error = "Element not visible (hidden or off-screen)"
            result.error_stage = "visible"
            logger.debug(f"[Verify] Not visible: {result.selector}")
            return False, result.error
        
        result.element_visible = True
        
        # Stage 3: Trial click
        try:
            await locator.click(trial=True, timeout=timeout)
        except Exception as e:
            result.error = f"Not clickable: {e}"
            result.error_stage = "click"
            logger.debug(f"[Verify] Click failed: {result.selector} - {e}")
            return False, result.error
        
        result.element_clickable = True
        result.success = True
        logger.debug(f"[Verify] ✓ Clickable: {result.selector}")
        return True, None
        
    except Exception as e:
        result.error = f"Unexpected error: {e}"
        result.error_stage = "unknown"
        return False, result.error


async def verify_response(
    page: Page,
    response: str,
    format_name: str,
    sifr_resolver: Optional[SiFRResolver] = None,
    verbose: bool = False
) -> Tuple[bool, Optional[str], Optional[str], Optional[VerificationResult]]:
    """
    Full verification: resolve + verify.
    
    Returns: (success, selector_used, error, detailed_result)
    """
    result = VerificationResult()
    
    locator, selector, error = await resolve_to_locator(
        page, response, format_name, sifr_resolver, result
    )
    
    if error:
        if verbose:
            logger.info(f"[{format_name}] FAIL: {result}")
        return False, selector, error, result
    
    success, verify_error = await verify_locator(locator, result=result)
    
    if verbose:
        if success:
            logger.info(f"[{format_name}] OK: {result}")
        else:
            logger.info(f"[{format_name}] FAIL: {result}")
    
    return success, selector, verify_error, result


def setup_verbose_logging(level: int = logging.DEBUG):
    """Enable verbose logging for verification."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(message)s",
        datefmt="%H:%M:%S"
    )
    logger.setLevel(level)
