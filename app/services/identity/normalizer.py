from __future__ import annotations
import re
import unicodedata
from dataclasses import dataclass

# Transliteration table: cyrillic → latin
_CYR_TO_LAT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d",
    "е": "e", "ё": "yo", "ж": "zh", "з": "z", "и": "i",
    "й": "j", "к": "k", "л": "l", "м": "m", "н": "n",
    "о": "o", "п": "p", "р": "r", "с": "s", "т": "t",
    "у": "u", "ф": "f", "х": "kh", "ц": "ts", "ч": "ch",
    "ш": "sh", "щ": "shch", "ъ": "", "ы": "y", "ь": "",
    "э": "e", "ю": "yu", "я": "ya",
}


def _transliterate(text: str) -> str:
    result = []
    for ch in text.lower():
        if ch in _CYR_TO_LAT:
            result.append(_CYR_TO_LAT[ch])
        else:
            result.append(ch)
    return "".join(result)


def _normalize_chars(text: str) -> str:
    """Remove diacritics and non-ASCII characters."""
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if unicodedata.category(c) != "Mn" and c.isascii())


def _clean(text: str) -> str:
    text = _transliterate(text)
    text = _normalize_chars(text)
    # Replace non-alphanumeric with space
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return text.strip()


@dataclass
class NormalizedIdentity:
    canonical_username: str  # e.g. "d_ivanov"
    first_name: str
    last_name: str
    confidence: float  # 0.0 – 1.0
    is_ambiguous: bool = False
    source: str = "name"  # "name" | "email" | "override"


def normalize_identity(
    raw_name: str,
    raw_email: str | None = None,
    overrides: dict[str, str] | None = None,
) -> NormalizedIdentity:
    """
    Map raw git author name / email to canonical username like d_ivanov.
    Priority: manual override → email hint → name parsing.
    """
    overrides = overrides or {}
    name_key = raw_name.strip().lower()
    email_key = (raw_email or "").strip().lower()

    # 1. Manual override by name
    if name_key in overrides:
        u = overrides[name_key]
        return NormalizedIdentity(u, "", "", 1.0, False, "override")

    # 2. Manual override by email
    if email_key and email_key in overrides:
        u = overrides[email_key]
        return NormalizedIdentity(u, "", "", 1.0, False, "override")

    # 3. Try to derive from email (e.g. d.ivanov@company.com → d_ivanov)
    if raw_email:
        email_username = _email_to_username(raw_email)
        if email_username:
            return NormalizedIdentity(email_username, "", "", 0.9, False, "email")

    # 4. Parse from name
    return _name_to_identity(raw_name)


def _email_to_username(email: str) -> str | None:
    local = email.split("@")[0].lower()
    # d.ivanov → d_ivanov
    local = re.sub(r"[.\-+]", "_", local)
    local = re.sub(r"[^a-z0-9_]", "", local)
    if not local:
        return None
    # Already looks canonical: one letter + _ + word
    if re.match(r"^[a-z]_[a-z]+$", local):
        return local
    # Try to parse as firstname.lastname pattern
    parts = local.split("_")
    if len(parts) >= 2:
        first_initial = parts[0][0] if parts[0] else ""
        last = parts[-1]
        if first_initial and last:
            return f"{first_initial}_{last}"
    return local if local else None


def _name_to_identity(raw_name: str) -> NormalizedIdentity:
    cleaned = _clean(raw_name)
    parts = cleaned.split()

    if not parts:
        return NormalizedIdentity("unknown", "", "", 0.1, True, "name")

    if len(parts) == 1:
        # Single token — use as-is with underscore prefix if short
        token = parts[0]
        return NormalizedIdentity(token, token, "", 0.5, True, "name")

    # Assume first token = first name, last token = last name
    first = parts[0]
    last = parts[-1]
    first_initial = first[0] if first else ""
    username = f"{first_initial}_{last}"

    # Ambiguity: if first name is just an initial already
    is_ambiguous = len(first) == 1

    return NormalizedIdentity(
        canonical_username=username,
        first_name=first,
        last_name=last,
        confidence=0.85 if not is_ambiguous else 0.7,
        is_ambiguous=is_ambiguous,
        source="name",
    )
