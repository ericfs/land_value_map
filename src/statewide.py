"""Process all CT towns from the statewide CAMA and Parcel Layer GDB.

This replaces the per-COG pipeline by reading from a single pre-joined
statewide dataset where parcel geometry and CAMA attributes are already combined.
"""

import gc
import os
import pandas as pd
import pyogrio
from shapely.validation import make_valid

from export_geojson import export_geojson
from town_name import town_name_to_file_name, normalize_town_name
from value_per_acre import compute_value_per_acre, filter_value_per_acre, compute_capped_value_per_acre

STATEWIDE_GDB = "5b462e9a-7190-47bf-a2ce-9b69d12ea06b.gdb"
STATEWIDE_LAYER = "Connecticut_CAMA_and_Parcel_Layer"
DROP_ROWS = {
    # This is the entire road network in a single parcel
    'shelton': ('Link', '40  40'),
}
# Towns where the statewide GDB has no value data;
# join appraised values from the per-COG CAMA CSV instead.
# (csv_path relative to input_dir, csv_join_col, gdb_join_col)
CAMA_CSV_FALLBACK = {
    'woodbridge': (
        'Parcel Collection 2024/CAMA_By_COG/SCRCOG/Woodbridge_2024_CAMA.csv',
        'PID', 'Link',
    ),
}


def drop_rows(df, town_name):
    town_name = normalize_town_name(town_name)
    if town_name in DROP_ROWS:
        drop_key, drop_value = DROP_ROWS[town_name]
        df = df[df[drop_key] != drop_value]
    return df


def process_town(gdf, town_name, output_dir, input_dir=None):
    """Compute value per acre and export GeoJSON for a single town."""
    # Drop rows with null geometry and fix invalid geometries
    gdf = gdf[gdf.geometry.notna()].copy()
    gdf["geometry"] = gdf["geometry"].apply(make_valid)
    gdf = drop_rows(gdf, town_name)

    for col in ["Appraised_Land", "Appraised_Building", "Appraised_Outbuilding"]:
        gdf[col] = pd.to_numeric(gdf[col], errors="coerce").fillna(0)
    gdf["Appraised_Total"] = (
        gdf["Appraised_Land"] + gdf["Appraised_Building"] + gdf["Appraised_Outbuilding"]
    )

    # Fall back to Assessed_Total / 0.7 when appraised data is missing
    if gdf["Appraised_Total"].sum() == 0 and "Assessed_Total" in gdf.columns:
        gdf["Assessed_Total"] = pd.to_numeric(gdf["Assessed_Total"], errors="coerce").fillna(0)
        if gdf["Assessed_Total"].sum() > 0:
            gdf["Appraised_Total"] = gdf["Assessed_Total"] / 0.7
            print(f"\t\tUsing Assessed_Total / 0.7 as Appraised_Total for {town_name}")

    # Fall back to CAMA CSV for towns with no value data in the statewide GDB
    if gdf["Appraised_Total"].sum() == 0:
        norm = normalize_town_name(town_name)
        if norm in CAMA_CSV_FALLBACK:
            csv_path, csv_key, gdb_key = CAMA_CSV_FALLBACK[norm]
            csv_path = os.path.join(input_dir, csv_path)
            cama = pd.read_csv(csv_path)
            gdf = gdf.merge(
                cama[[csv_key, "Appraised Total"]].rename(
                    columns={csv_key: gdb_key, "Appraised Total": "Appraised_Total_CSV"}
                ),
                on=gdb_key, how="left",
            )
            gdf["Appraised_Total"] = pd.to_numeric(
                gdf["Appraised_Total_CSV"], errors="coerce"
            ).fillna(0)
            gdf = gdf.drop(columns=["Appraised_Total_CSV"])
            print(f"\t\tUsing CAMA CSV for Appraised_Total for {town_name}")

    gdf["Land_Acres"] = pd.to_numeric(gdf["Land_Acres"], errors="coerce")

    compute_value_per_acre(gdf)
    gdf = filter_value_per_acre(gdf)
    compute_capped_value_per_acre(gdf)

    filename = town_name_to_file_name(output_dir, town_name)
    export_geojson(gdf, filename)
    return filename


def process_statewide_gdb(input_dir, output_dir, overwrite=False):
    """Read the statewide GDB town-by-town and process each.
    Returns list of towns that failed."""
    gdb_path = os.path.join(input_dir, STATEWIDE_GDB)

    # First pass: get list of unique town names (no geometry, low memory)
    names_df = pyogrio.read_dataframe(
        gdb_path, layer=STATEWIDE_LAYER,
        columns=["Town_Name"], read_geometry=False,
    )
    town_names = sorted(names_df["Town_Name"].str.strip().unique())
    del names_df
    print(f"Found {len(town_names)} towns in {gdb_path}")

    failed = []
    for town_name in town_names:
        filename = town_name_to_file_name(output_dir, town_name)
        if not overwrite and os.path.exists(filename):
            print(f"\tFile already exists: {filename}")
            continue

        try:
            # Read one town at a time using SQL filter to limit memory
            gdf = pyogrio.read_dataframe(
                gdb_path, layer=STATEWIDE_LAYER,
                where=f"Town_Name = '{town_name}' OR Town_Name = '{town_name} '",
                on_invalid="fix",
            )
            print(f"\tProcessing {town_name} ({len(gdf)} parcels)")
            process_town(gdf, town_name, output_dir, input_dir)
            print(f"\t\tExported {town_name}")
        except Exception as e:
            print(f"\t\tError processing {town_name}: {e}")
            failed.append(town_name)
        finally:
            gc.collect()

    return failed
