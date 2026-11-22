# Deciding whether a value is low, normal or high.
# The AI reads the report, but our own code makes the final decision for numeric
# values, because comparing two numbers must be exact and repeatable.

import re

NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


def parse_number(text):
    """Turn printed text into a number: "13.5" -> 13.5, "1,20,000" -> 120000.0, "<5" -> 5.0.

    Returns None for text that isn't a single number, such as "Negative" or "1+ / 2+".
    """
    if text is None:
        return None
    cleaned = str(text).replace(",", "").strip().lstrip("<>=≤≥ ").strip()
    if not cleaned or not NUMBER.fullmatch(cleaned):
        return None
    return float(cleaned)


def decide_status(value, low, high, ai_status):
    """Return 'low', 'normal', 'high', 'abnormal' or 'unknown'.

    If the value and at least one limit are numbers, compare them ourselves.
    Otherwise (e.g. "Negative" vs "Negative"), fall back to what the AI read.
    """
    if value is not None and (low is not None or high is not None):
        if low is not None and value < low:
            return "low"
        if high is not None and value > high:
            return "high"
        return "normal"
    if ai_status in ("low", "normal", "high", "abnormal"):
        return ai_status
    return "unknown"
