"""Category names may start with an emoji ("🛒 Supermercado"). The emoji is part of the name, not a separate field.

Anything that compares names (duplicates, the assistant finding a category by what the user said) must look at the
words only, so "🛒 Supermercado", "Supermercado" and "🏪 supermercado" are the same category. Pure functions.
"""

import unicodedata

# Unicode categories of what an emoji is made of: symbols (So), modifiers such as skin tones (Sk), the invisible
# joiners and variation selectors (Cf, Mn, Me), and the spaces between them (Zs)
_DECORATION = {"So", "Sk", "Cf", "Mn", "Me", "Zs"}


def plain_name(name: str | None) -> str:
    """The name without the emoji (and spaces) it starts with: "🛒 Supermercado" -> "Supermercado"."""
    text = (name or "").strip()
    start = 0
    while start < len(text) and (unicodedata.category(text[start]) in _DECORATION or text[start].isspace()):
        start += 1
    return text[start:].strip()


def same_name(a: str | None, b: str | None) -> bool:
    """True if two names are the same words, ignoring emoji, case and surrounding spaces."""
    return plain_name(a).casefold() == plain_name(b).casefold()
