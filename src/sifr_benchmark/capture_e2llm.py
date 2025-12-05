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
    timeout: int = 30000
) -> dict:
    """
    Capture page using E2LLM extension CustomEvent API.
    
    Returns:
        dict with sifr (stringified), html, axtree, metadata
    """
    
    result = await page.evaluate("""
        ([selector, timeout]) => {
            return new Promise((resolve, reject) => {
                const id = Date.now().toString();
                
                const timer = setTimeout(() => {
                    reject(new Error('E2LLM capture timeout - is extension installed?'));
                }, timeout);
                
                document.addEventListener('e2llm-capture-response', (e) => {
                    if (e.detail && e.detail.requestId === id) {
                        clearTimeout(timer);
                        
                        // E2LLM v2.6.x returns: {requestId, success, data, meta}
                        // data contains the SiFR structure directly
                        const response = e.detail;
                        
                        if (response.success && response.data) {
                            resolve({
                                sifr: JSON.stringify(response.data, null, 2),
                                meta: response.meta || {},
                                html: document.documentElement.outerHTML
                            });
                        } else {
                            resolve({
                                sifr: '',
                                meta: {},
                                html: document.documentElement.outerHTML,
                                error: response.error || 'Unknown error'
                            });
                        }
                    }
                }, { once: true });
                
                document.dispatchEvent(new CustomEvent('e2llm-capture-request', {
                    detail: { 
                        requestId: id, 
                        selector: selector
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
            await page.wait_for_timeout(2000)  # Wait for extension to be ready
            
            result = await capture_with_e2llm(page, selector)
            screenshot = await page.screenshot(full_page=True)
            axtree = await page.accessibility.snapshot()
            
            return CaptureResult(
                url=url,
                sifr=result.get("sifr", ""),
                html=result.get("html", ""),
                axtree=axtree or {},
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
                await page.wait_for_timeout(2000)  # Wait for extension
                
                result = await capture_with_e2llm(page)
                screenshot = await page.screenshot(full_page=True)
                
                # Get real accessibility tree via Playwright
                axtree = await page.accessibility.snapshot()
                
                # Generate page_id from URL
                page_id = url.replace("https://", "").replace("http://", "")
                page_id = page_id.replace("/", "_").replace(".", "_").rstrip("_")
                
                sifr_content = result.get("sifr", "")
                html_content = result.get("html", "")
                
                # Save files
                (output / "sifr" / f"{page_id}.sifr").write_text(
                    sifr_content, encoding="utf-8"
                )
                (output / "html" / f"{page_id}.html").write_text(
                    html_content, encoding="utf-8"
                )
                (output / "axtree" / f"{page_id}.json").write_text(
                    json.dumps(axtree, indent=2, ensure_ascii=False),
                    encoding="utf-8"
                )
                (output / "screenshots" / f"{page_id}.png").write_bytes(screenshot)
                
                results.append(CaptureResult(
                    url=url,
                    sifr=sifr_content,
                    html=html_content,
                    axtree=axtree or {},
                    screenshot=screenshot
                ))
                
                sifr_size = len(sifr_content)
                print(f"  ✅ Saved: {page_id} (SiFR: {sifr_size} bytes)")
                
                await page.wait_for_timeout(500)
                
            except Exception as e:
                print(f"  ❌ Error: {e}")
                # Save empty files to avoid breaking pipeline
                (output / "sifr" / f"{page_id}.sifr").write_text("", encoding="utf-8")
                (output / "html" / f"{page_id}.html").write_text("", encoding="utf-8")
                
        await context.close()
    
    return results


if __name__ == "__main__":
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
