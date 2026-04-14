"""
shared/id_generator.py
Standardized unique identifier generation.
"""
import secrets
from typing import Optional

def generate_id(prefix: str = "", length: int = 8) -> str:
    """Generate a unique hex identifier."""
    # Generate slightly more bytes than needed to ensure length coverage, then slice
    hex_part = secrets.token_hex((length // 2) + 1)[:length]
    return f"{prefix}{hex_part}"

def validate_id(id_str: str, prefix: Optional[str] = None) -> bool:
    """Check if a string looks like a valid ID."""
    if not id_str:
        return False
        
    if prefix:
        if not id_str.startswith(prefix):
            return False
        payload = id_str[len(prefix):]
    else:
        payload = id_str
        
    # Check if payload is valid hex
    try:
        int(payload, 16)
        return True
    except ValueError:
        return False

def extract_prefix(id_str: str) -> tuple[str, str]:
    """
    Split ID into (prefix, hex_part).
    Example: 't12345' -> ('t', '12345')
    """
    if not id_str: return ("", "")
    
    # Find the first hex digit
    for i, char in enumerate(id_str):
        if char in "0123456789abcdef":
            return (id_str[:i], id_str[i:])
            
    # If strictly no hex found, return as prefix
    return (id_str, "")

def shorten_id(id_str: str, length: int = 8) -> str:
    """
    Shorten an ID for display purposes.
    Example: 'a3f7b2c1e4' -> 'a3f7b2c1'
    """
    if not id_str:
        return ""
    return id_str[:length]
