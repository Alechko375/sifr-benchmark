"""
Capture pages using E2LLM extension API.
Requires: pip install playwright
First run: playwright install chromium
"""

import asyncio
import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


@dataclass
class CaptureResult:
    url: str
    sifr: str
    html: str
    axtree: dict
    screenshot: Optional[bytes] = None


async def capture_with_e2llm(
    page,
    selector: str = "body",
    timeout: int = 10000
) -> dict:
    """
    Capture page using E2LLM extension CustomEvent API.
    
    Args:
        page: Playwright page object
        selector: CSS selector to capture (default: full page)
        timeout: Timeout in ms
        
    Returns:
        dict with sifr, html, axtree, metadata
    """
    
    result = await page.evaluate("""
        ([selector, timeout]) => {
            return new Promise((resolve, reject) => {
                const id = Date.now().toString();
                
                const timer = setTimeout(() => {
                    reject(new Error('E2LLM capture timeout - is extension installed?'));
                }, timeout);
                
                document.addEventListener('e2llm-capture-response', (e) => {
                    if (e.detail.requestId === id) {
                        clearTimeout(timer);
                        resolve(e.detail);
                    }
                }, { once: true });
                
                document.dispatchEvent(new CustomEvent('e2llm-capture-request', {
                    detail: { 
                        requestId: id, 
                        selector: selector, 
                        options: { fullPage: true }
                    }
                }));
            });
        }
    """, [selector, timeout])
    
    return result


async def capture_page(
    url: str,
    extension_path: str,
    user_data_dir: str = "./e2llm-chrome-profile",
    headless: bool = False,
    selector: str = "body"
) -> CaptureResult:
    """
    Capture a page using Playwright + E2LLM extension.
    
    Args:
        url: URL to capture
        extension_path: Path to unpacked E2LLM extension
        user_data_dir: Chrome profile directory
        headless: Run headless (note: extensions need headless=False or --headless=new)
        selector: CSS selector to capture
        
    Returns:
        CaptureResult with all formats
    """
    from playwright.async_api import async_playwright
    
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=headless,
            args=[
                f"--disable-extensions-except={extension_path}",
                f"--load-extension={extension_path}",
            ]
        )
        
        page = await context.new_page()
        
        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(1000)  # Extra wait for extension
            
            # Capture via E2LLM API
            result = await capture_with_e2llm(page, selector)
            
            # Screenshot
            screenshot = await page.screenshot(full_page=True)
            
            return CaptureResult(
                url=url,
                sifr=result.get("sifr", ""),
                html=result.get("html", ""),
                axtree=result.get("axtree", {}),
                screenshot=screenshot
            )
            
        finally:
            await context.close()


async def capture_multiple(
    urls: list[str],
    extension_path: str,
    output_dir: str = "./datasets/formats",
    user_data_dir: str = "./e2llm-chrome-profile"
) -> list[CaptureResult]:
    """
    Capture multiple pages, saving to output directory.
    
    Args:
        urls: List of URLs to capture
        extension_path: Path to E2LLM extension
        output_dir: Directory to save captured formats
        user_data_dir: Chrome profile directory
        
    Returns:
        List of CaptureResults
    """
    from playwright.async_api import async_playwright
    
    output = Path(output_dir)
    (output / "sifr").mkdir(parents=True, exist_ok=True)
    (output / "html").mkdir(parents=True, exist_ok=True)
    (output / "axtree").mkdir(parents=True, exist_ok=True)
    (output / "screenshots").mkdir(parents=True, exist_ok=True)
    
    results = []
    
    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False,
            args=[
                f"--disable-extensions-except={extension_path}",
                f"--load-extension={extension_path}",
            ]
        )
        
        page = await context.new_page()
        
        for url in urls:
            try:
                print(f"Capturing: {url}")
                
                await page.goto(url, wait_until="networkidle", timeout=30000)
                await page.wait_for_timeout(1000)
                
                result = await capture_with_e2llm(page)
                screenshot = await page.screenshot(full_page=True)
                
                # Generate page_id from URL
                page_id = url.replace("https://", "").replace("http://", "")
                page_id = page_id.replace("/", "_").replace(".", "_").rstrip("_")
                
                # Save files
                (output / "sifr" / f"{page_id}.sifr").write_text(
                    result.get("sifr", ""), encoding="utf-8"
                )
                (output / "html" / f"{page_id}.html").write_text(
                    result.get("html", ""), encoding="utf-8"
                )
                (output / "axtree" / f"{page_id}.json").write_text(
                    json.dumps(result.get("axtree", {}), indent=2, ensure_ascii=False),
                    encoding="utf-8"
                )
                (output / "screenshots" / f"{page_id}.png").write_bytes(screenshot)
                
                results.append(CaptureResult(
                    url=url,
                    sifr=result.get("sifr", ""),
                    html=result.get("html", ""),
                    axtree=result.get("axtree", {}),
                    screenshot=screenshot
                ))
                
                print(f"  ✅ Saved: {page_id}")
                
                # Rate limiting
                await page.wait_for_timeout(500)
                
            except Exception as e:
                print(f"  ❌ Error: {e}")
                
        await context.close()
    
    return results


# CLI entry point
def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Capture pages using E2LLM extension")
    parser.add_argument("urls", nargs="+", help="URLs to capture")
    parser.add_argument("--extension", "-e", required=True, help="Path to E2LLM extension")
    parser.add_argument("--output", "-o", default="./datasets/formats", help="Output directory")
    parser.add_argument("--profile", default="./e2llm-chrome-profile", help="Chrome profile dir")
    
    args = parser.parse_args()
    
    asyncio.run(capture_multiple(
        urls=args.urls,
        extension_path=args.extension,
        output_dir=args.output,
        user_data_dir=args.profile
    ))


if __name__ == "__main__":
    main()
