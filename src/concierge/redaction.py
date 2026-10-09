"""Deterministic redaction of rep-pasted SSNs, card numbers, expirations, and CVVs.

Human turns are redacted before every model call so raw values never enter
model context or tool arguments. Each value is swapped for a stable
placeholder (`[SSN_1]`, `[CARD_1]`, `[EXP_1]`, `[CVV_1]`) and the
placeholder -> raw value mapping is kept in graph state for server-side
resolution. The same rules back the LangSmith trace anonymizer.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence

from langchain_core.messages import BaseMessage, HumanMessage
from langsmith.anonymizer import create_anonymizer

_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_LABELED_SSN = re.compile(
    r"(?i)\b(?:ssn|social(?:\s+security)?(?:\s+(?:number|no|#))?)[\s:#.-]*(?:is\s+)?(\d{9})\b"
)
_CARD = re.compile(r"\b\d(?:[ -]?\d){12,18}\b")
_EXP = re.compile(
    r"(?i)\b(?:exp(?:iry|iration)?(?:\s+date)?|expires)[\s:.]*(\d{1,2}\s*/\s*\d{2,4})\b"
)
_CVV = re.compile(
    r"(?i)\b(?:cvv2?|cvc2?|csc|security\s+code)[\s:#.-]*(?:is\s+)?(\d{3,4})\b"
)


def _luhn_valid(value: str) -> bool:
    """Return True when the digits in `value` form a 13-19 digit Luhn-valid PAN."""
    digits = [int(c) for c in value if c.isdigit()]
    if not 13 <= len(digits) <= 19:
        return False
    total = 0
    for i, digit in enumerate(reversed(digits)):
        if i % 2:
            digit *= 2
            if digit > 9:
                digit -= 9
        total += digit
    return total % 10 == 0


_RULES: list[tuple[str, re.Pattern[str], Callable[[str], bool] | None]] = [
    ("SSN", _SSN, None),
    ("SSN", _LABELED_SSN, None),
    ("CARD", _CARD, _luhn_valid),
    ("EXP", _EXP, None),
    ("CVV", _CVV, None),
]


def _placeholder(kind: str, value: str, mapping: dict[str, str]) -> str:
    """Return the placeholder for `value`, adding a new one to `mapping` if needed."""
    prefix = f"[{kind}_"
    for placeholder, raw in mapping.items():
        if raw == value and placeholder.startswith(prefix):
            return placeholder
    placeholder = f"{prefix}{sum(1 for p in mapping if p.startswith(prefix)) + 1}]"
    mapping[placeholder] = value
    return placeholder


def redact_text(
    text: str, mapping: dict[str, str] | None = None
) -> tuple[str, dict[str, str]]:
    """Replace sensitive values in `text` with placeholders; return text and mapping."""
    mapping = dict(mapping or {})
    for kind, pattern, validate in _RULES:
        text = pattern.sub(_replacer(kind, validate, mapping), text)
    return text, mapping


def _replacer(
    kind: str, validate: Callable[[str], bool] | None, mapping: dict[str, str]
) -> Callable[[re.Match[str]], str]:
    """Build a `re.sub` callback that swaps the matched value for its placeholder."""

    def _replace(match: re.Match[str]) -> str:
        group = 1 if match.re.groups else 0
        value = match.group(group)
        if validate is not None and not validate(value):
            return match.group(0)
        start = match.start(group) - match.start(0)
        end = match.end(group) - match.start(0)
        whole = match.group(0)
        return whole[:start] + _placeholder(kind, value, mapping) + whole[end:]

    return _replace


def redact_messages(
    messages: Sequence[BaseMessage], mapping: dict[str, str] | None = None
) -> tuple[list[BaseMessage], dict[str, str]]:
    """Return copies of `messages` with human turns redacted, plus the updated mapping."""
    mapping = dict(mapping or {})
    redacted: list[BaseMessage] = []
    for message in messages:
        if not isinstance(message, HumanMessage):
            redacted.append(message)
            continue
        content = message.content
        if isinstance(content, str):
            content, mapping = redact_text(content, mapping)
        else:
            blocks = []
            for block in content:
                if isinstance(block, str):
                    block, mapping = redact_text(block, mapping)
                elif isinstance(block, dict) and isinstance(block.get("text"), str):
                    text, mapping = redact_text(block["text"], mapping)
                    block = {**block, "text": text}
                blocks.append(block)
            content = blocks
        redacted.append(message.model_copy(update={"content": content}))
    return redacted, mapping


trace_anonymizer = create_anonymizer(lambda text: redact_text(text)[0])
