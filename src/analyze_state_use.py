"""Analyze State_Use and State_Use_Description from the statewide GDB.

Standalone utility to inspect the full set of codes and validate
the tax-exempt classification logic.

Usage:
    python3 analyze_state_use.py [--gdb PATH] [--town TOWN_NAME]
"""

import argparse
import os

import pandas as pd
import pyogrio

from tax_exempt import EXEMPT_KEYWORDS, NON_EXEMPT_KEYWORDS, classify_tax_exempt

STATEWIDE_LAYER = "Connecticut_CAMA_and_Parcel_Layer"
DEFAULT_GDB = os.path.join(
    os.path.dirname(__file__), "..", "inputs",
    "5b462e9a-7190-47bf-a2ce-9b69d12ea06b.gdb",
)


def load_data(gdb_path, town=None):
    """Read State_Use, State_Use_Description, and Land_Acres (no geometry)."""
    columns = ["State_Use", "State_Use_Description", "Land_Acres", "Town_Name"]
    where = None
    if town:
        where = f"Town_Name = '{town}' OR Town_Name = '{town} '"
    return pyogrio.read_dataframe(
        gdb_path, layer=STATEWIDE_LAYER,
        columns=columns, read_geometry=False,
        where=where,
    )


def analyze(gdb_path, town=None):
    label = f" for {town}" if town else ""
    print(f"Reading {gdb_path}{label} ...")
    df = load_data(gdb_path, town)
    df["Land_Acres"] = pd.to_numeric(df["Land_Acres"], errors="coerce").fillna(0)
    total_acres = df["Land_Acres"].sum()
    print(f"Total parcels: {len(df):,}")
    print(f"Total acres:   {total_acres:,.1f}\n")

    # Classify
    df["Tax_Exempt"] = classify_tax_exempt(df)

    # Summary
    exempt = df[df["Tax_Exempt"]]
    taxable = df[~df["Tax_Exempt"]]
    exempt_acres = exempt["Land_Acres"].sum()
    taxable_acres = taxable["Land_Acres"].sum()
    pct = (exempt_acres / total_acres * 100) if total_acres > 0 else 0

    print(f"Tax-exempt: {len(exempt):,} parcels, {exempt_acres:,.1f} acres ({pct:.1f}%)")
    print(f"Taxable:    {len(taxable):,} parcels, {taxable_acres:,.1f} acres ({100 - pct:.1f}%)")
    print()

    # Group by (State_Use, State_Use_Description)
    pd.set_option("display.max_rows", None)
    pd.set_option("display.max_colwidth", 80)
    pd.set_option("display.width", 200)

    grouped = df.groupby(["State_Use", "State_Use_Description", "Tax_Exempt"]).agg(
        count=("Land_Acres", "size"),
        acres=("Land_Acres", "sum"),
    ).reset_index().sort_values(["Tax_Exempt", "acres"], ascending=[False, False])

    # Print exempt entries
    exempt_g = grouped[grouped["Tax_Exempt"]].copy()
    exempt_g["acres"] = exempt_g["acres"].round(1)
    print(f"=== EXEMPT ({len(exempt_g)} unique code/description pairs) ===")
    print(exempt_g[["State_Use", "State_Use_Description", "count", "acres"]].to_string(index=False))
    print()

    # Print taxable entries with descriptions that might look exempt (for auditing)
    taxable_g = grouped[~grouped["Tax_Exempt"]].copy()
    lower_desc = taxable_g["State_Use_Description"].str.lower().fillna("")
    suspect = taxable_g[
        lower_desc.str.contains("|".join(EXEMPT_KEYWORDS), na=False)
    ]
    if len(suspect) > 0:
        suspect = suspect.copy()
        suspect["acres"] = suspect["acres"].round(1)
        print(f"=== TAXABLE entries matching exempt keywords (review these) ===")
        print(suspect[["State_Use", "State_Use_Description", "count", "acres"]].to_string(index=False))
        print()

    print("Exempt keywords:", EXEMPT_KEYWORDS)
    print("Exclusion keywords:", NON_EXEMPT_KEYWORDS)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze State_Use codes")
    parser.add_argument("--gdb", default=DEFAULT_GDB, help="Path to statewide GDB")
    parser.add_argument("--town", default=None, help="Filter to a single town")
    args = parser.parse_args()
    analyze(args.gdb, args.town)
