"""Classify parcels as tax-exempt based on State_Use code and description.

See agent/state_use_codes.md for background on the CT OPM coding system.

Primary signal: State_Use codes starting with digit "9" (900-999, 9000-9999)
are exempt in the CAMA vendor system used by the statewide GDB.

Secondary signal: State_Use_Description keyword matching catches edge cases
where the code is missing or non-standard.
"""

import pandas as pd

# Case-insensitive keywords that indicate tax-exempt property.
# Used as a fallback when State_Use code doesn't start with "9".
EXEMPT_KEYWORDS = [
    "exempt",
    "church",
    "municipal",
    "cemetery",
    "religious",
    "charitable",
]

# Descriptions containing these keywords are NOT exempt,
# even if they match an EXEMPT_KEYWORD above.
NON_EXEMPT_KEYWORDS = [
    "nonexempt",
    "non-exempt",
    "non exempt",
]


def _code_starts_with_9(state_use):
    """Return boolean Series: True where State_Use starts with digit '9'."""
    return state_use.fillna("").astype(str).str.strip().str.startswith("9")


def classify_tax_exempt(df):
    """Return a boolean Series: True where the parcel is tax-exempt.

    Uses two signals:
    1. State_Use code starts with "9" (primary — covers 900-999, 9000-9999)
    2. State_Use_Description contains exempt keywords (fallback)

    Excludes parcels whose description contains "NonExempt" variants.
    """
    is_exempt = pd.Series(False, index=df.index)

    # Primary: code starts with "9"
    if "State_Use" in df.columns:
        is_exempt = is_exempt | _code_starts_with_9(df["State_Use"])

    # Fallback: description keyword matching
    if "State_Use_Description" in df.columns:
        desc = df["State_Use_Description"].fillna("").str.lower()
        pattern = "|".join(EXEMPT_KEYWORDS)
        is_exempt = is_exempt | desc.str.contains(pattern, na=False)

    # Exclude non-exempt overrides
    if "State_Use_Description" in df.columns:
        desc = df["State_Use_Description"].fillna("").str.lower()
        non_exempt_pattern = "|".join(NON_EXEMPT_KEYWORDS)
        is_non_exempt = desc.str.contains(non_exempt_pattern, na=False)
        is_exempt = is_exempt & ~is_non_exempt

    return is_exempt
