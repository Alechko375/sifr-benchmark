"""
Page capture module - captures pages in all formats.
"""

import json
import asyncio
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


@dataclass
class CaptureResult:
    url: str
    sifr_path: Optional[Path] = None
    html_path: Optional[Path] = None
    screenshot_path: Optional[Path] = None
    axtree_path: Optional[Path] = None
    error: Optional[str] = None


def check_playwright():
    """Check if playwright is installed."""
    try:
        from playwright.sync_api import sync_playwright
        return True
    except ImportError:
        return False


def install_playwright_browsers():
    """Install playwright browsers."""
    import subprocess
    subprocess.run(["playwright", "install", "chromium"], check=True)


def generate_sifr_from_page(page) -> dict:
    """Generate SiFR format from Playwright page."""
    
    # Get page info
    url = page.url
    title = page.title()
    viewport = page.viewport_size
    
    # Extract elements using JavaScript
    elements = page.evaluate("""() => {
        const results = { high: {}, med: {}, low: {} };
        const buttons = document.querySelectorAll('button, [role="button"], input[type="submit"]');
        const links = document.querySelectorAll('a[href]');
        const inputs = document.querySelectorAll('input, textarea, select');
        const headings = document.querySelectorAll('h1, h2, h3');
        
        let btnCount = 1, linkCount = 1, inputCount = 1, textCount = 1;
        
        // High salience: buttons, main inputs
        buttons.forEach((el, i) => {
            if (i < 10) {
                const rect = el.getBoundingClientRect();
                results.high['btn' + String(btnCount++).padStart(3, '0')] = {
                    type: 'button',
                    text: el.textContent?.trim().slice(0, 50) || el.value || '',
                    position: [Math.round(rect.x), Math.round(rect.y), Math.round(rect.width), Math.round(rect.height)],
                    state: el.disabled ? 'disabled' : 'enabled'
                };
            }
        });
        
        // High salience: main input
        inputs.forEach((el, i) => {
            if (i < 5) {
                const rect = el.getBoundingClientRect();
                results.high['inp' + String(inputCount++).padStart(3, '0')] = {
                    type: 'input',
                    placeholder: el.placeholder || '',
                    input_type: el.type || 'text',
                    position: [Math.round(rect.x), Math.round(rect.y), Math.round(rect.width), Math.round(rect.height)],
                    state: el.disabled ? 'disabled' : 'enabled'
                };
            }
        });
        
        // Med salience: links
        links.forEach((el, i) => {
            if (i < 20) {
                const rect = el.getBoundingClientRect();
                if (!results.med.link) results.med.link = {};
                results.med['lnk' + String(linkCount++).padStart(3, '0')] = {
                    type: 'link',
                    text: el.textContent?.trim().slice(0, 50) || '',
                    href: el.href,
                    position: [Math.round(rect.x), Math.round(rect.y), Math.round(rect.width), Math.round(rect.height)]
                };
            }
        });
        
        // Low salience: headings as text
        headings.forEach((el, i) => {
            const rect = el.getBoundingClientRect();
            results.low['txt' + String(textCount++).padStart(3, '0')] = {
                type: 'text',
                content: el.textContent?.trim().slice(0, 100) || '',
                tag: el.tagName.toLowerCase(),
                position: [Math.round(rect.x), Math.round(rect.y), Math.round(rect.width), Math.round(rect.height)]
            };
        });
        
        return results;
    }""")
    
    # Build SiFR structure
    sifr = {
        "====METADATA====": {
            "format": "sifr-v2.0",
            "url": url,
            "title": title,
            "viewport": viewport,
            "stats": {
                "high": len(elements.get("high", {})),
                "med": len(elements.get("med", {})),
                "low": len(elements.get("low", {}))
            }
        },
        "====NODES====": elements,
        "====SUMMARY====": {
            "page": {
                "purpose": f"Page at {url}",
                "title": title
            }
        }
    }
    
    return sifr


def get_accessibility_tree(page) -> dict:
    """Get accessibility tree from page."""
    snapshot = page.accessibility.snapshot()
    return snapshot or {}


def capture_page(
    url: str,
    output_dir: Path,
    name: str,
    formats: list[str] = None,
    headless: bool = True
) -> CaptureResult:
    """
    Capture a page in multiple formats.
    
    Args:
        url: URL to capture
        output_dir: Output directory
        name: Base name for files
        formats: List of formats to capture (sifr, html, screenshot, axtree)
        headless: Run browser in headless mode
    
    Returns:
        CaptureResult with paths to captured files
    """
    if not check_playwright():
        return CaptureResult(url=url, error="Playwright not installed. Run: pip install playwright && playwright install chromium")
    
    if formats is None:
        formats = ["sifr", "html", "screenshot", "axtree"]
    
    from playwright.sync_api import sync_playwright
    
    result = CaptureResult(url=url)
    
    # Create output directories
    output_dir = Path(output_dir)
    (output_dir / "sifr").mkdir(parents=True, exist_ok=True)
    (output_dir / "html").mkdir(parents=True, exist_ok=True)
    (output_dir / "screenshots").mkdir(parents=True, exist_ok=True)
    (output_dir / "axtree").mkdir(parents=True, exist_ok=True)
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            page = browser.new_page(viewport={"width": 1920, "height": 1080})
            
            # Navigate
            page.goto(url, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(2000)  # Extra wait for dynamic content
            
            # Capture SiFR
            if "sifr" in formats:
                sifr_data = generate_sifr_from_page(page)
                sifr_path = output_dir / "sifr" / f"{name}.sifr"
                with open(sifr_path, "w", encoding="utf-8") as f:
                    json.dump(sifr_data, f, indent=2)
                result.sifr_path = sifr_path
            
            # Capture HTML
            if "html" in formats:
                html_content = page.content()
                html_path = output_dir / "html" / f"{name}.html"
                with open(html_path, "w", encoding="utf-8") as f:
                    f.write(html_content)
                result.html_path = html_path
            
            # Capture Screenshot
            if "screenshot" in formats:
                screenshot_path = output_dir / "screenshots" / f"{name}.png"
                page.screenshot(path=str(screenshot_path), full_page=False)
                result.screenshot_path = screenshot_path
            
            # Capture Accessibility Tree
            if "axtree" in formats:
                axtree = get_accessibility_tree(page)
                axtree_path = output_dir / "axtree" / f"{name}.json"
                with open(axtree_path, "w", encoding="utf-8") as f:
                    json.dump(axtree, f, indent=2)
                result.axtree_path = axtree_path
            
            browser.close()
            
    except Exception as e:
        result.error = str(e)
    
    return result


def capture_multiple(
    urls: list[str],
    output_dir: Path,
    formats: list[str] = None,
    headless: bool = True
) -> list[CaptureResult]:
    """Capture multiple pages."""
    results = []
    for url in urls:
        # Generate name from URL
        from urllib.parse import urlparse
        parsed = urlparse(url)
        name = parsed.netloc.replace(".", "_").replace("www_", "")
        
        result = capture_page(url, output_dir, name, formats, headless)
        results.append(result)
    
    return results
