"""
Format loading and validation utilities.
Supports isolated run directory structure.
"""

import json
from pathlib import Path
from typing import Optional, Union, Tuple
from dataclasses import dataclass


@dataclass
class FormatMeta:
    """Metadata about loaded format."""
    original_size: int
    truncated_size: Optional[int] = None
    was_truncated: bool = False
    format_name: str = ""
    path: str = ""


# Default truncation limit (can be overridden via max_chars parameter)
DEFAULT_MAX_CHARS = 400 * 1024  # 400KB default, same as CLI default


def _truncate_content(content: str, max_chars: int = DEFAULT_MAX_CHARS) -> Tuple[str, bool, int]:
    """
    Truncate content if too large.
    Returns: (content, was_truncated, original_size)
    """
    original_size = len(content)
    
    if len(content) <= max_chars:
        return content, False, original_size
    
    content = content[:max_chars]
    # Try to cut at a newline for cleaner truncation
    last_newline = content.rfind('\n')
    if last_newline > max_chars * 0.8:
        content = content[:last_newline]
    content += "\n... [truncated]"
    
    return content, True, original_size


def load_sifr(
    page_id: str, 
    base_dir: Optional[Path] = None,
    return_meta: bool = False,
    max_chars: int = DEFAULT_MAX_CHARS
) -> Union[str, Tuple[str, FormatMeta]]:
    """Load a SiFR file, truncating if too large."""
    paths_to_try = []
    
    if base_dir:
        paths_to_try.append(base_dir / "captures" / "sifr" / f"{page_id}.sifr")
    
    paths_to_try.extend([
        Path(f"datasets/formats/sifr/{page_id}.sifr"),
        Path(f"examples/{page_id}.sifr"),
    ])
    
    for path in paths_to_try:
        if path.exists():
            content = path.read_text(encoding="utf-8")
            content, was_truncated, original_size = _truncate_content(content, max_chars)
            
            if return_meta:
                meta = FormatMeta(
                    original_size=original_size,
                    truncated_size=len(content) if was_truncated else None,
                    was_truncated=was_truncated,
                    format_name="sifr",
                    path=str(path),
                )
                return content, meta
            return content
    
    raise FileNotFoundError(f"SiFR file not found for: {page_id}")


def load_html(
    page_id: str, 
    base_dir: Optional[Path] = None, 
    clean: bool = False,
    return_meta: bool = False,
    max_chars: int = DEFAULT_MAX_CHARS
) -> Union[str, Tuple[str, FormatMeta]]:
    """Load an HTML file, truncating if too large."""
    format_name = "html_clean" if clean else "html_raw"
    paths_to_try = []
    
    if base_dir:
        if clean:
            paths_to_try.append(base_dir / "captures" / "html_clean" / f"{page_id}.html")
        else:
            paths_to_try.append(base_dir / "captures" / "html" / f"{page_id}.html")
    
    suffix = "_clean" if clean else ""
    paths_to_try.extend([
        Path(f"datasets/formats/html/{page_id}{suffix}.html"),
    ])
    
    for path in paths_to_try:
        if path.exists():
            content = path.read_text(encoding="utf-8")
            content, was_truncated, original_size = _truncate_content(content, max_chars)
            
            if return_meta:
                meta = FormatMeta(
                    original_size=original_size,
                    truncated_size=len(content) if was_truncated else None,
                    was_truncated=was_truncated,
                    format_name=format_name,
                    path=str(path),
                )
                return content, meta
            return content
    
    raise FileNotFoundError(f"HTML file not found for: {page_id}")


def load_axtree(
    page_id: str, 
    base_dir: Optional[Path] = None,
    return_meta: bool = False,
    max_chars: int = DEFAULT_MAX_CHARS
) -> Union[str, Tuple[str, FormatMeta]]:
    """Load an accessibility tree file, truncating if too large."""
    paths_to_try = []
    
    if base_dir:
        paths_to_try.append(base_dir / "captures" / "axtree" / f"{page_id}.json")
    
    paths_to_try.extend([
        Path(f"datasets/formats/axtree/{page_id}.json"),
        Path(f"datasets/formats/axtree/{page_id}.txt"),
    ])
    
    for path in paths_to_try:
        if path.exists():
            content = path.read_text(encoding="utf-8")
            
            # Pretty-print JSON for readability
            if path.suffix == ".json":
                try:
                    data = json.loads(content)
                    content = json.dumps(data, indent=2)
                except json.JSONDecodeError:
                    pass
            
            content, was_truncated, original_size = _truncate_content(content, max_chars)
            
            if return_meta:
                meta = FormatMeta(
                    original_size=original_size,
                    truncated_size=len(content) if was_truncated else None,
                    was_truncated=was_truncated,
                    format_name="axtree",
                    path=str(path),
                )
                return content, meta
            return content
    
    raise FileNotFoundError(f"AXTree file not found for: {page_id}")


def load_screenshot(
    page_id: str,
    base_dir: Optional[Path] = None,
    return_meta: bool = False,
    max_chars: int = DEFAULT_MAX_CHARS  # unused for screenshots, but keeps signature consistent
) -> Union[bytes, Tuple[bytes, FormatMeta]]:
    """Load a screenshot file."""
    paths_to_try = []
    
    if base_dir:
        paths_to_try.append(base_dir / "captures" / "screenshots" / f"{page_id}.png")
    
    paths_to_try.extend([
        Path(f"datasets/formats/screenshots/{page_id}.png"),
    ])
    
    for path in paths_to_try:
        if path.exists():
            content = path.read_bytes()
            
            if return_meta:
                meta = FormatMeta(
                    original_size=len(content),
                    was_truncated=False,
                    format_name="screenshot",
                    path=str(path),
                )
                return content, meta
            return content
    
    raise FileNotFoundError(f"Screenshot not found for: {page_id}")


def load_format(
    page_id: str, 
    format_name: str, 
    base_dir: Optional[Path] = None,
    return_meta: bool = False,
    max_chars: int = DEFAULT_MAX_CHARS
) -> Union[str, Tuple[str, FormatMeta]]:
    """
    Load a page in specified format.
    
    Args:
        page_id: Page identifier
        format_name: One of: sifr, html_raw, html_clean, axtree, screenshot
        base_dir: Run directory (new structure) or None for legacy
        return_meta: If True, return (content, FormatMeta) tuple
        max_chars: Maximum characters before truncation (default: 400KB)
        
    Returns:
        File content as string (or bytes for screenshot)
        If return_meta=True: (content, FormatMeta)
    """
    if format_name == "sifr":
        return load_sifr(page_id, base_dir, return_meta, max_chars)
    elif format_name == "html_raw":
        return load_html(page_id, base_dir, clean=False, return_meta=return_meta, max_chars=max_chars)
    elif format_name == "html_clean":
        return load_html(page_id, base_dir, clean=True, return_meta=return_meta, max_chars=max_chars)
    elif format_name == "axtree":
        return load_axtree(page_id, base_dir, return_meta, max_chars)
    elif format_name == "screenshot":
        return load_screenshot(page_id, base_dir, return_meta, max_chars)
    else:
        raise ValueError(f"Unknown format: {format_name}")


def discover_pages(base_dir: Path) -> list[str]:
    """Discover available pages in a run directory."""
    gt_dir = base_dir / "ground-truth"
    if gt_dir.exists():
        return [f.stem for f in gt_dir.glob("*.json")]
    
    sifr_dir = base_dir / "captures" / "sifr"
    if sifr_dir.exists():
        return [f.stem for f in sifr_dir.glob("*.sifr")]
    
    return []


def validate_sifr_file(path: Path) -> list[str]:
    """
    Validate a SiFR file.
    Returns list of error messages (empty if valid).
    """
    errors = []
    
    try:
        content = path.read_text(encoding="utf-8")
    except Exception as e:
        return [f"Cannot read file: {e}"]
    
    if content.strip().startswith("{"):
        try:
            data = json.loads(content)
            metadata = data.get("====METADATA====", {})
            if not metadata.get("format"):
                errors.append("Missing metadata field: format")
            if not metadata.get("url"):
                errors.append("Missing metadata field: url")
            if "====NODES====" not in data:
                errors.append("Missing NODES section")
            return errors
        except json.JSONDecodeError as e:
            return [f"Invalid JSON: {e}"]
    
    required_sections = ["====METADATA====", "====NODES===="]
    for section in required_sections:
        if section not in content:
            errors.append(f"Missing required section: {section}")
    
    return errors


def get_format_stats(page_id: str, base_dir: Path, max_chars: int = DEFAULT_MAX_CHARS) -> dict:
    """Get size statistics for all formats of a page."""
    stats = {}
    
    for fmt in ["sifr", "html_raw", "axtree", "screenshot"]:
        try:
            if fmt == "screenshot":
                _, meta = load_screenshot(page_id, base_dir, return_meta=True)
            else:
                _, meta = load_format(page_id, fmt, base_dir, return_meta=True, max_chars=max_chars)
            
            stats[fmt] = {
                "original_size": meta.original_size,
                "truncated": meta.was_truncated,
                "truncated_size": meta.truncated_size,
                "approx_tokens": meta.original_size // 4 if fmt != "screenshot" else None,
            }
        except FileNotFoundError:
            stats[fmt] = {"available": False}
    
    return stats
