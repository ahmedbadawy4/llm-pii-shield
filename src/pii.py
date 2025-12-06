import re
from typing import List, Tuple

# PII patterns
EMAIL_REGEX = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_REGEX = re.compile(r"\+?\d[\d\s().-]{7,}\d")
IBAN_REGEX = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b")
CREDIT_CARD_REGEX = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
SSN_REGEX = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
# Very loose street address matcher: number + at least two words
ADDRESS_REGEX = re.compile(r"\b\d{1,6}\s+[A-Za-z]{2,}(?:\s+[A-Za-z]{2,})+\b")

PII_PATTERNS = [
    ("email", EMAIL_REGEX, "[REDACTED_EMAIL]"),
    ("iban", IBAN_REGEX, "[REDACTED_IBAN]"),
    ("phone", PHONE_REGEX, "[REDACTED_PHONE]"),
    ("credit_card", CREDIT_CARD_REGEX, "[REDACTED_CARD]"),
    ("ssn", SSN_REGEX, "[REDACTED_SSN]"),
    ("address", ADDRESS_REGEX, "[REDACTED_ADDRESS]"),
]


def mask_pattern(text: str, pattern: re.Pattern, placeholder: str) -> Tuple[str, bool]:
    if pattern.search(text):
        text = pattern.sub(placeholder, text)
        return text, True
    return text, False


def redact_pii(text: str) -> Tuple[str, List[str]]:
    """
    Redact known PII patterns from text and return the masked text plus detected types.
    """
    detected: List[str] = []
    for label, regex, placeholder in PII_PATTERNS:
        text, hit = mask_pattern(text, regex, placeholder)
        if hit:
            detected.append(label)
    return text, detected
