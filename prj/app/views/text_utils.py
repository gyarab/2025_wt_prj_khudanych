"""
Text processing utilities using Rust-powered acceleration.
"""

import flag_search_core


def strip_accents(text: str) -> str:
    """Remove diacritics using Rust extension."""
    return flag_search_core.strip_accents(text)


def accent_insensitive_match(haystack: str, needle: str) -> bool:
    """Case- and accent-insensitive substring match using Rust extension."""
    return flag_search_core.accent_insensitive_match(haystack, needle)
