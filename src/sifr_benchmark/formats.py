"""
Format loading and validation utilities.
"""

import json
import re
from pathlib import Path
from typing import Optional


def load_sifr(page_id: str, base_path: Optional[str] = None) -> str:
    """Load a SiFR file."""
    paths_to_try = [
        Path(f"datasets/formats/sifr/{page_id}.sifr"),
        Path(f"examples/{page_id}.sifr"),
    ]
    
    if base_path:
        paths_to_try.insert(0, Path(base_path) / f"{page_id}.sifr")
    
    for path in paths_to_try:
        if path.exists():
            return path.read_text(encoding="utf-8")
    
    raise FileNotFoundError(f"SiFR file not found for: {page_id}")


def load_html(page_id: str, clean: bool = False, base_path: Optional[str] = None) -> str:
    """Load an HTML file."""
    suffix = "_clean" if clean else ""
    
    paths_to_try = [
        Path(f"datasets/formats/html/{page_id}{suffix}.html"),
        Path(f"datasets/pages/**/{page_id}.html"),
    ]
    
    if base_path:
        paths_to_try.insert(0, Path(base_path) / f"{page_id}{suffix}.html")
    
    for path in paths_to_try:
        # Handle glob patterns
        if "**" in str(path):
            matches = list(Path(".").glob(str(path)))
            if matches:
                return matches[0].read_text(encoding="utf-8")
        elif path.exists():
            return path.read_text(encoding="utf-8")
    
    raise FileNotFoundError(f"HTML file not found for: {page_id}")


def load_axtree(page_id: str, base_path: Optional[str] = None) -> str:
    """Load an accessibility tree file."""
    paths_to_try = [
        Path(f"datasets/formats/axtree/{page_id}.json"),
        Path(f"datasets/formats/axtree/{page_id}.txt"),
    ]
    
    if base_path:
        paths_to_try.insert(0, Path(base_path) / f"{page_id}.json")
    
    for path in paths_to_try:
        if path.exists():
            content = path.read_text(encoding="utf-8")
            # If JSON, pretty print for readability
            if path.suffix == ".json":
                try:
                    data = json.loads(content)
                    return json.dumps(data, indent=2)
                except json.JSONDecodeError:
                    pass
            return content
    
    raise FileNotFoundError(f"AXTree file not found for: {page_id}")


def load_format(page_id: str, format_name: str, base_path: Optional[str] = None) -> str:
    """
    Load a page in specified format.
    
    Args:
        page_id: Page identifier
        format_name: One of: sifr, html_raw, html_clean, axtree
        base_path: Optional base path to search
        
    Returns:
        File content as string
    """
    if format_name == "sifr":
        return load_sifr(page_id, base_path)
    elif format_name == "html_raw":
        return load_html(page_id, clean=False, base_path=base_path)
    elif format_name == "html_clean":
        return load_html(page_id, clean=True, base_path=base_path)
    elif format_name == "axtree":
        return load_axtree(page_id, base_path)
    else:
        raise ValueError(f"Unknown format: {format_name}")


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
    
    # Check required sections
    required_sections = ["====METADATA====", "====NODES===="]
    for section in required_sections:
        if section not in content:
            errors.append(f"Missing required section: {section}")
    
    # Check METADATA has required fields
    if "====METADATA====" in content:
        metadata_match = re.search(
            r"====METADATA====\s*(.*?)(?:====|$)", 
            content, 
            re.DOTALL
        )
        if metadata_match:
            metadata = metadata_match.group(1)
            required_fields = ["format:", "url:"]
            for field in required_fields:
                if field not in metadata:
                    errors.append(f"Missing metadata field: {field}")
    
    # Check for at least one node
    if "====NODES====" in content:
        nodes_match = re.search(
            r"====NODES====\s*(.*?)(?:====|$)", 
            content, 
            re.DOTALL
        )
        if nodes_match:
            nodes = nodes_match.group(1).strip()
            if not nodes or len(nodes) < 10:
                errors.append("NODES section appears empty")
    
    # Check file size (warn if too large)
    if len(content) > 500_000:  # 500KB
        errors.append(f"File is large ({len(content)} bytes), may cause token issues")
    
    return errors


def sifr_to_minimal(content: str) -> str:
    """
    Convert full SiFR to minimal format.
    Reduces tokens while preserving key information.
    """
    # Extract just high-salience nodes
    lines = []
    in_high = False
    
    for line in content.split("\n"):
        if "high:" in line:
            in_high = True
            continue
        elif "med:" in line or "low:" in line:
            in_high = False
            continue
        
        if in_high and line.strip():
            # Simplify node representation
            lines.append(line)
    
    return "\n".join(lines[:50])  # Limit to first 50 lines
