"""
Format loading and validation utilities.
Supports isolated run directory structure.
"""

import json
from pathlib import Path
from typing import Optional


def load_sifr(page_id: str, base_dir: Optional[Path] = None) -> str:
    """Load a SiFR file."""
    paths_to_try = []
    
    # New structure: base_dir/captures/sifr/
    if base_dir:
        paths_to_try.append(base_dir / "captures" / "sifr" / f"{page_id}.sifr")
    
    # Legacy paths
    paths_to_try.extend([
        Path(f"datasets/formats/sifr/{page_id}.sifr"),
        Path(f"examples/{page_id}.sifr"),
    ])
    
    for path in paths_to_try:
        if path.exists():
            return path.read_text(encoding="utf-8")
    
    raise FileNotFoundError(f"SiFR file not found for: {page_id}. Tried: {[str(p) for p in paths_to_try]}")


def load_html(page_id: str, base_dir: Optional[Path] = None, clean: bool = False) -> str:
    """Load an HTML file."""
    suffix = "_clean" if clean else ""
    paths_to_try = []
    
    # New structure: base_dir/captures/html/
    if base_dir:
        paths_to_try.append(base_dir / "captures" / "html" / f"{page_id}{suffix}.html")
    
    # Legacy paths
    paths_to_try.extend([
        Path(f"datasets/formats/html/{page_id}{suffix}.html"),
    ])
    
    for path in paths_to_try:
        if path.exists():
            return path.read_text(encoding="utf-8")
    
    raise FileNotFoundError(f"HTML file not found for: {page_id}. Tried: {[str(p) for p in paths_to_try]}")


def load_axtree(page_id: str, base_dir: Optional[Path] = None) -> str:
    """Load an accessibility tree file."""
    paths_to_try = []
    
    # New structure: base_dir/captures/axtree/
    if base_dir:
        paths_to_try.append(base_dir / "captures" / "axtree" / f"{page_id}.json")
    
    # Legacy paths
    paths_to_try.extend([
        Path(f"datasets/formats/axtree/{page_id}.json"),
        Path(f"datasets/formats/axtree/{page_id}.txt"),
    ])
    
    for path in paths_to_try:
        if path.exists():
            content = path.read_text(encoding="utf-8")
            if path.suffix == ".json":
                try:
                    data = json.loads(content)
                    return json.dumps(data, indent=2)
                except json.JSONDecodeError:
                    pass
            return content
    
    raise FileNotFoundError(f"AXTree file not found for: {page_id}. Tried: {[str(p) for p in paths_to_try]}")


def load_format(page_id: str, format_name: str, base_dir: Optional[Path] = None) -> str:
    """
    Load a page in specified format.
    
    Args:
        page_id: Page identifier
        format_name: One of: sifr, html_raw, html_clean, axtree
        base_dir: Run directory (new structure) or None for legacy
        
    Returns:
        File content as string
    """
    if format_name == "sifr":
        return load_sifr(page_id, base_dir)
    elif format_name == "html_raw":
        return load_html(page_id, base_dir, clean=False)
    elif format_name == "html_clean":
        return load_html(page_id, base_dir, clean=True)
    elif format_name == "axtree":
        return load_axtree(page_id, base_dir)
    else:
        raise ValueError(f"Unknown format: {format_name}")


def discover_pages(base_dir: Path) -> list[str]:
    """Discover available pages in a run directory."""
    # Look for ground truth files
    gt_dir = base_dir / "ground-truth"
    if gt_dir.exists():
        return [f.stem for f in gt_dir.glob("*.json")]
    
    # Fallback: look for SiFR files
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
