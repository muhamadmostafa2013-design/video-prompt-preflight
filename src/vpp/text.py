import re

ARABIC_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]")
WORD_RE = re.compile(r"\S+")


def contains_arabic(text: str) -> bool:
    return bool(ARABIC_RE.search(text or ""))


def word_count(text: str) -> int:
    return len(WORD_RE.findall(text or ""))
