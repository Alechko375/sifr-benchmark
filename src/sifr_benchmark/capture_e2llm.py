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

# Default budget: 100KB (good balance of accuracy vs tokens)
# Max recommended: 380KB (LLM context limit ~400KB)
DEFAULT_TARGET_SIZE = 100 * 1024  # 100KB


@dataclass
class CaptureResult:
    url: str
    sifr: str
    html: str
    axtree: dict
    screenshot: Optional[bytes] = None
    sifr_meta: Optional[dict] = None  # E2LLM metadata


async def capture_with_e2llm(
    page,
    selector: str = "body",
    timeout: int = 30000,
    target_size: int = DEFAULT_TARGET_SIZE
) -> dict:
    """
    Capture page using E2LLM extension CustomEvent API.
    
    Args:
        page: Playwright page object
        selector: CSS selector to capture (default: body)
        timeout: Timeout in ms
        target_size: Target SiFR size in bytes (default: 100KB)
    
    Returns:
        dict with sifr (stringified), html, axtree, metadata
    """
    
    result = await page.evaluate("""
        ([selector, timeout, targetSize]) => {
            return new Promise((resolve, reject) => {
                const id = Date.now().toString();
                
                const timer = setTimeout(() => {
                    reject(new Error('E2LLM capture timeout - is extension installed?'));
                }, timeout);
                
                document.addEventListener('e2llm-capture-response', (e) => {
                    if (e.detail && e.detail.requestId === id) {
                        clearTimeout(timer);
                        
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
                        selector: selector,
                        options: {
                            fullPage: true,
                            targetSize: targetSize
                        }
                    }
                }));
            });
        }
    """, [selector, timeout, target_size])
    
    return result


async def capture_page(
    url: str,
    extension_path: str,
    user_data_dir: str = "./e2llm-chrome-profile",
    headless: bool = False,
    selector: str = "body",
    target_size: int = DEFAULT_TARGET_SIZE
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
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_timeout(3000)
            
            result = await capture_with_e2llm(page, selector, target_size=target_size)
            screenshot = await page.screenshot(full_page=True)
            axtree = await page.accessibility.snapshot()
            
            return CaptureResult(
                url=url,
                sifr=result.get("sifr", ""),
                html=result.get("html", ""),
                axtree=axtree or {},
                screenshot=screenshot,
                sifr_meta=result.get("meta")
            )
            
        finally:
            await context.close()


async def capture_multiple(
    urls: list[str],
    extension_path: str,
    output_dir: str = "./datasets/formats",
    user_data_dir: str = "./e2llm-chrome-profile",
    target_size: int = DEFAULT_TARGET_SIZE
) -> list[CaptureResult]:
    """
    Capture multiple pages, saving to output directory.
    
    Args:
        urls: List of URLs to capture
        extension_path: Path to E2LLM extension
        output_dir: Output directory for captures
        user_data_dir: Chrome profile directory
        target_size: Target SiFR size in bytes (default: 100KB)
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
        
        # Log budget info
        print(f"📦 SiFR budget: {target_size // 1024}KB")
        
        for url in urls:
            page_id = url.replace("https://", "").replace("http://", "")
            page_id = page_id.replace("/", "_").replace(".", "_").rstrip("_")
            
            try:
                print(f"Capturing: {url}")
                
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                await page.wait_for_timeout(3000)
                
                result = await capture_with_e2llm(page, target_size=target_size)
                screenshot = await page.screenshot(full_page=True)
                axtree = await page.accessibility.snapshot()
                
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
                    screenshot=screenshot,
                    sifr_meta=result.get("meta")
                ))
                
                sifr_size = len(sifr_content)
                print(f"  ✅ {page_id} (SiFR: {sifr_size // 1024}KB)")
                
                await page.wait_for_timeout(500)
                
            except Exception as e:
                print(f"  ❌ Error capturing {page_id}: {e}")
                (output / "sifr" / f"{page_id}.sifr").write_text("", encoding="utf-8")
                (output / "html" / f"{page_id}.html").write_text("", encoding="utf-8")
                (output / "axtree" / f"{page_id}.json").write_text("{}", encoding="utf-8")
                
        await context.close()
    
    return results


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Capture pages using E2LLM extension")
    parser.add_argument("urls", nargs="+", help="URLs to capture")
    parser.add_argument("--extension", "-e", required=True, help="Path to E2LLM extension")
    parser.add_argument("--output", "-o", default="./datasets/formats", help="Output directory")
    parser.add_argument("--profile", default="./e2llm-chrome-profile", help="Chrome profile dir")
    parser.add_argument(
        "--target-size", "-s", 
        type=int, 
        default=100,
        help="Target SiFR size in KB (default: 100, max recommended: 380)"
    )
    
    args = parser.parse_args()
    
    asyncio.run(capture_multiple(
        urls=args.urls,
        extension_path=args.extension,
        output_dir=args.output,
        user_data_dir=args.profile,
        target_size=args.target_size * 1024  # Convert KB to bytes
    ))
