"""Analyze State_Use and State_Use_Description from the statewide GDB.

Standalone utility to inspect the full set of codes and validate
the keyword-based tax-exempt classification logic.

Usage:
    python3 analyze_state_use.py [--gdb PATH]
"""

import argparse
import os
import sys

import pandas as pd
import pyogrio

from tax_exempt import EXEMPT_KEYWORDS, NON_EXEMPT_KEYWORDS, classify_tax_exempt

STATEWIDE_LAYER = "Connecticut_CAMA_and_Parcel_Layer"
DEFAULT_GDB = os.path.join(
    os.path.dirname(__file__), "..", "inputs",
    "5b462e9a-7190-47bf-a2ce-9b69d12ea06b.gdb",
)


def load_state_use(gdb_path):
    """Read only State_Use and State_Use_Description (no geometry)."""
    return pyogrio.read_dataframe(
        gdb_path, layer=STATEWIDE_LAYER,
        columns=["State_Use", "State_Use_Description"],
        read_geometry=False,
    )


def analyze(gdb_path):
    print(f"Reading {gdb_path} ...")
    df = load_state_use(gdb_path)
    print(f"Total parcels: {len(df):,}\n")

    # Classify
    df["Tax_Exempt"] = classify_tax_exempt(df)

    # Group by (State_Use, State_Use_Description)
    grouped = (
        df.groupby(["State_Use", "State_Use_Description", "Tax_Exempt"])
        .size()
        .reset_index(name="count")
        .sort_values(["Tax_Exempt", "count"], ascending=[False, False])
    )

    # Summary
    exempt_parcels = df["Tax_Exempt"].sum()
    taxable_parcels = len(df) - exempt_parcels
    print(f"Tax-exempt parcels: {exempt_parcels:,}")
    print(f"Taxable parcels:    {taxable_parcels:,}")
    print()

    # Print exempt entries
    exempt = grouped[grouped["Tax_Exempt"]].copy()
    print(f"=== EXEMPT descriptions ({len(exempt)} unique code/description pairs) ===")
    pd.set_option("display.max_rows", None)
    pd.set_option("display.max_colwidth", 80)
    pd.set_option("display.width", 200)
    print(exempt[["State_Use", "State_Use_Description", "count"]].to_string(index=False))
    print()

    # Print taxable entries with descriptions that might look exempt (for auditing)
    taxable = grouped[~grouped["Tax_Exempt"]].copy()
    lower_desc = taxable["State_Use_Description"].str.lower().fillna("")
    suspect = taxable[
        lower_desc.str.contains("|".join(EXEMPT_KEYWORDS), na=False)
    ]
    if len(suspect) > 0:
        print(f"=== TAXABLE entries matching exempt keywords (review these) ===")
        print(suspect[["State_Use", "State_Use_Description", "count"]].to_string(index=False))
        print()

    print("Keywords used:", EXEMPT_KEYWORDS)
    print("Exclusion keywords:", NON_EXEMPT_KEYWORDS)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze State_Use codes")
    parser.add_argument("--gdb", default=DEFAULT_GDB, help="Path to statewide GDB")
    args = parser.parse_args()
    analyze(args.gdb)
