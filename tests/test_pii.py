import pytest

from src.pii import redact_pii


@pytest.mark.parametrize(
    "text, expected_mask, expected_types",
    [
        ("Contact me at jane.doe@example.com", "Contact me at [REDACTED_EMAIL]", ["email"]),
        ("Call me at +1 (555) 123-4567", "Call me at [REDACTED_PHONE]", ["phone"]),
        ("IBAN DE89370400440532013000", "IBAN [REDACTED_IBAN]", ["iban"]),
        ("Card 4111-1111-1111-1111", "Card [REDACTED_CARD]", ["credit_card"]),
        ("SSN 123-45-6789", "SSN [REDACTED_SSN]", ["ssn"]),
        ("123 Main Street Springfield", "[REDACTED_ADDRESS] Springfield", ["address"]),
    ],
)
def test_single_type_redaction(text, expected_mask, expected_types):
    masked, types = redact_pii(text)
    assert masked == expected_mask
    assert sorted(types) == expected_types


def test_mixed_pii_redaction():
    text = "Email jane@example.com, phone (555) 123-4567, card 4111 1111 1111 1111"
    masked, types = redact_pii(text)
    assert "[REDACTED_EMAIL]" in masked
    assert "[REDACTED_PHONE]" in masked
    assert "[REDACTED_CARD]" in masked
    assert sorted(types) == ["credit_card", "email", "phone"]


@pytest.mark.parametrize(
    "text",
    [
        "This is not@valid",
        "No numbers here",
        "Street without number Main Street",
        "Card-like but short 4111-1111-1111",
    ],
)
def test_no_false_positive(text):
    masked, types = redact_pii(text)
    assert masked == text
    assert types == []
