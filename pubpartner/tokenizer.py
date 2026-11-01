"""
Token counting.

Uses tiktoken's cl100k_base encoding, which is a close-enough proxy for
Claude/GPT-family tokenization for the purpose of budgeting prompt content.
If tiktoken's vocab files can't be reached (e.g. no network), falls back to
a conservative character-based estimate so the rest of the system keeps
working rather than hard-failing on a missing download.
"""

from __future__ import annotations

_encoding = None
_encoding_load_attempted = False


def _get_encoding():
    global _encoding, _encoding_load_attempted
    if _encoding_load_attempted:
        return _encoding
    _encoding_load_attempted = True
    try:
        import tiktoken

        _encoding = tiktoken.get_encoding("cl100k_base")
    except Exception:
        _encoding = None
    return _encoding


def count_tokens(text: str) -> int:
    """Return the token count for `text`. Falls back to ~4 chars/token if
    tiktoken is unavailable."""
    if not text:
        return 0
    encoding = _get_encoding()
    if encoding is not None:
        return len(encoding.encode(text))
    return max(1, len(text) // 4)


def truncate_to_tokens(text: str, max_tokens: int) -> str:
    """Truncate `text` to at most `max_tokens` tokens, on a token boundary
    when tiktoken is available, otherwise on a character boundary."""
    if max_tokens <= 0:
        return ""
    encoding = _get_encoding()
    if encoding is not None:
        tokens = encoding.encode(text)
        if len(tokens) <= max_tokens:
            return text
        return encoding.decode(tokens[:max_tokens])
    approx_chars = max_tokens * 4
    return text[:approx_chars]
