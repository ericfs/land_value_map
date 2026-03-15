"""Classify parcels as tax-exempt based on State_Use_Description keywords.

See agent/state_use_codes.md for background on the CT OPM coding system
and why we use description-based matching rather than code ranges.
"""

import pandas as pd

# Case-insensitive keywords that indicate tax-exempt property.
# Order doesn't matter — any match triggers exempt classification.
EXEMPT_KEYWORDS = [
    "exempt",
    "church",
    "municipal",
    "state ",
    "federal",
    "cemetery",
    "religious",
    "school",
    "college",
    "university",
    "hospital",
    "charitable",
    "fire ",
    "library",
    "town ",
    "housing authority",
    "public",
]

# Descriptions containing these keywords are NOT exempt,
# even if they match an EXEMPT_KEYWORD above.
NON_EXEMPT_KEYWORDS = [
    "nonexempt",
    "non-exempt",
    "non exempt",
]


def classify_tax_exempt(df):
    """Return a boolean Series: True where the parcel is tax-exempt.

    Requires a 'State_Use_Description' column in df.
    Returns all-False if the column is missing.
    """
    if "State_Use_Description" not in df.columns:
        return pd.Series(False, index=df.index)

    desc = df["State_Use_Description"].fillna("").str.lower()

    # Match any exempt keyword
    pattern = "|".join(EXEMPT_KEYWORDS)
    is_exempt = desc.str.contains(pattern, na=False)

    # Exclude non-exempt overrides
    non_exempt_pattern = "|".join(NON_EXEMPT_KEYWORDS)
    is_non_exempt = desc.str.contains(non_exempt_pattern, na=False)

    return is_exempt & ~is_non_exempt
