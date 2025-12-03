"""
Verify benchmark results by executing actions via Playwright.
"""

import json
import time
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


@dataclass
class VerifyResult:
    task_id: str
    format: str
    response: str
    action_success: bool
    error: Optional[str] = None


def verify_click(page, target: str) -> tuple[bool, str]:
    """
    Try to click an element based on model's response.
    
    Args:
        page: Playwright page
        target: Model's response (could be ID, selector, or text)
        
    Returns:
        (success, error_message)
    """
    try:
        # Try different strategies
        
        # 1. If it looks like element ID (btn001, inp002, etc.)
        if target.startswith(("btn", "inp", "lnk", "div")):
            # Try data attribute or id
            selectors = [
                f"[data-sifr-id='{target}']",
                f"#{target}",
                f"[id*='{target}']"
            ]
            for sel in selectors:
                try:
                    el = page.locator(sel).first
                    if el.is_visible(timeout=1000):
                        el.click(timeout=3000)
                        return True, None
                except:
                    continue
        
        # 2. If it's a CSS selector
        if "." in target or "#" in target or "[" in target:
            try:
                el = page.locator(target).first
                if el.is_visible(timeout=1000):
                    el.click(timeout=3000)
                    return True, None
            except:
                pass
        
        # 3. Try by text content
        try:
            el = page.get_by_text(target, exact=False).first
            if el.is_visible(timeout=1000):
                el.click(timeout=3000)
                return True, None
        except:
            pass
        
        # 4. Try by role and name
        try:
            el = page.get_by_role("button", name=target).first
            if el.is_visible(timeout=1000):
                el.click(timeout=3000)
                return True, None
        except:
            pass
        
        return False, f"Element not found: {target}"
        
    except Exception as e:
        return False, str(e)


def verify_fill(page, target: str, text: str = "test") -> tuple[bool, str]:
    """
    Try to fill an input based on model's response.
    """
    try:
        # Similar strategies as click
        selectors_to_try = []
        
        if target.startswith(("inp", "txt")):
            selectors_to_try.extend([
                f"[data-sifr-id='{target}']",
                f"#{target}"
            ])
        
        if "." in target or "#" in target or "[" in target:
            selectors_to_try.append(target)
        
        # Try each selector
        for sel in selectors_to_try:
            try:
                el = page.locator(sel).first
                if el.is_visible(timeout=1000):
                    el.fill(text, timeout=3000)
                    return True, None
            except:
                continue
        
        # Try by placeholder
        try:
            el = page.get_by_placeholder(target).first
            if el.is_visible(timeout=1000):
                el.fill(text, timeout=3000)
                return True, None
        except:
            pass
        
        return False, f"Input not found: {target}"
        
    except Exception as e:
        return False, str(e)


def verify_results(
    url: str,
    results: list[dict],
    headless: bool = True
) -> list[VerifyResult]:
    """
    Verify benchmark results by executing actions.
    
    Args:
        url: Page URL to test on
        results: List of benchmark results (from raw_results.json)
        headless: Run browser in headless mode
        
    Returns:
        List of verification results
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return [VerifyResult(
            task_id="",
            format="",
            response="",
            action_success=False,
            error="Playwright not installed"
        )]
    
    verify_results = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        
        for result in results:
            # Skip if no response or error
            if not result.get("response") or result.get("error"):
                verify_results.append(VerifyResult(
                    task_id=result.get("task_id", ""),
                    format=result.get("format", ""),
                    response=result.get("response", ""),
                    action_success=False,
                    error=result.get("error", "No response")
                ))
                continue
            
            # Navigate to page (fresh each time)
            page.goto(url, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(1000)
            
            task_id = result.get("task_id", "")
            response = result.get("response", "")
            
            # Determine action based on task
            if task_id.startswith("int_"):
                # Interactive task - try to click first item in list
                target = response
                if response.startswith("["):
                    try:
                        items = json.loads(response.replace("'", '"'))
                        target = items[0] if items else response
                    except:
                        target = response.strip("[]").split(",")[0].strip()
                
                success, error = verify_click(page, target)
            else:
                # Non-action task - just mark as not verifiable
                success = True
                error = "Not an action task"
            
            verify_results.append(VerifyResult(
                task_id=task_id,
                format=result.get("format", ""),
                response=response,
                action_success=success,
                error=error
            ))
            
            # Small delay between tests
            time.sleep(0.5)
        
        browser.close()
    
    return verify_results


def verify_from_file(
    url: str,
    results_file: Path,
    headless: bool = True
) -> list[VerifyResult]:
    """
    Verify results from a raw_results.json file.
    """
    with open(results_file) as f:
        results = json.load(f)
    
    return verify_results(url, results, headless)
