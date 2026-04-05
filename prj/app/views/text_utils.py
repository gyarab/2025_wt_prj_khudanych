"""
Text processing utilities with optional Rust acceleration.
"""

import unicodedata

import flag_search_core


def _python_strip_accents(text: str) -> str:
    """Portable fallback for environments where Rust symbols are unavailable."""
    if not isinstance(text, str):
        return ''
    normalized = unicodedata.normalize('NFKD', text)
    return ''.join(ch for ch in normalized if not unicodedata.combining(ch))


def strip_accents(text: str) -> str:
    """Remove diacritics; prefer Rust implementation when present."""
    rust_fn = getattr(flag_search_core, 'strip_accents', None)
    if callable(rust_fn):
        return rust_fn(text)
    return _python_strip_accents(text)


def accent_insensitive_match(haystack: str, needle: str) -> bool:
    """Case- and accent-insensitive substring match with Rust/Python fallback."""
    rust_fn = getattr(flag_search_core, 'accent_insensitive_match', None)
    if callable(rust_fn):
        return rust_fn(haystack, needle)

    lhs = _python_strip_accents(haystack).casefold()
    rhs = _python_strip_accents(needle).casefold()
    return rhs in lhs
