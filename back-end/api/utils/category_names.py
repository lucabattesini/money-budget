"""Category names may start with an emoji ("🛒 Supermercado"). The emoji is part of the name, not a separate field.

Anything that compares names (duplicates, the assistant finding a category by what the user said, merging categories
when someone joins a family) must look at the words only, so "🛒 Supermercado", "Supermercado" and "🏪 supermercado" are
the same category. Pure functions. The front-end (src/lib/categoryName.js) uses exactly the same idea of what the
start of a name is made of, so the page and the server split a name the same way.
"""

import unicodedata


def _is_decoration(char: str) -> bool:
    """What a name may start with that is not part of its words: an emoji and the spaces around it.

    Emoji are symbols (Unicode category So: pictographs, flags, arrows...), skin tones are modifier symbols (Sk),
    and a sequence is joined with the zero-width joiner and the emoji variation selector.
    """
    return unicodedata.category(char) in {"So", "Sk"} or char in "‍️" or char.isspace()


def plain_name(name: str | None) -> str:
    """The name without the emoji (and spaces) it starts with, as the person wrote it: "🛒 Supermercado" -> "Supermercado"."""
    text = (name or "").strip()
    start = 0
    while start < len(text) and _is_decoration(text[start]):
        start += 1
    return text[start:].strip()


def name_key(name: str | None) -> str:
    """What two names are compared by: their words, ignoring emoji, case, accents written in two ways, runs of
    spaces and characters that cannot be seen (zero-width spaces, joiners, variation selectors). Empty means the name
    has no words at all."""
    text = unicodedata.normalize("NFKC", plain_name(name))
    visible = "".join(c for c in text if unicodedata.category(c) != "Cf" and not "︀" <= c <= "️")
    return " ".join(visible.split()).casefold()


def same_name(a: str | None, b: str | None) -> bool:
    """True if two names are the same words."""
    return name_key(a) == name_key(b)
