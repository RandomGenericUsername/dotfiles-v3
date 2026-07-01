import re


def matches_any_pattern(text: str, patterns: tuple[str, ...]) -> bool:
    lower = text.lower()
    return any(re.search(rf"\b{re.escape(p.lower())}\b", lower) for p in patterns)
