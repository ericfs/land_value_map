"""Process all CT towns from the statewide CAMA and Parcel Layer GDB.

This replaces the per-COG pipeline by reading from a single pre-joined
statewide dataset where parcel geometry and CAMA attributes are already combined.
"""

import gc
import os
import pandas as pd
import geopandas as gpd
from shapely.validation import make_valid

from export_geojson import export_geojson
from tax_exempt import classify_tax_exempt
from town_name import town_name_to_file_name, normalize_town_name
from value_per_acre import compute_value_per_acre, filter_value_per_acre, compute_capped_value_per_acre

DROP_ROWS = {
    # This is the entire road network in a single parcel
    'shelton': ('Link', '40  40'),
}


def drop_rows(df, town_name):
    town_name = normalize_town_name(town_name)
    if town_name in DROP_ROWS:
        drop_key, drop_value = DROP_ROWS[town_name]
        df = df[df[drop_key] != drop_value]
    return df


def find_cama_csv(cama_dir, town_name):
    """Find a CAMA CSV for a town by searching cama_dir subdirectories."""
    if not cama_dir:
        return None
    import glob
    pattern = os.path.join(cama_dir, "**", f"{town_name}_2024_CAMA.csv")
    matches = glob.glob(pattern, recursive=True)
    return matches[0] if matches else None


def process_town(gdf, town_name, output_dir, cama_dir=None):
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
        csv_path = find_cama_csv(cama_dir, town_name)
        if csv_path:
            cama = pd.read_csv(csv_path)
            if "Appraised Total" in cama.columns and "PID" in cama.columns:
                gdf = gdf.merge(
                    cama[["PID", "Appraised Total"]].rename(
                        columns={"PID": "Link", "Appraised Total": "Appraised_Total_CSV"}
                    ),
                    on="Link", how="left",
                )
                gdf["Appraised_Total"] = pd.to_numeric(
                    gdf["Appraised_Total_CSV"], errors="coerce"
                ).fillna(0)
                gdf = gdf.drop(columns=["Appraised_Total_CSV"])
                print(f"\t\tUsing CAMA CSV for Appraised_Total for {town_name}")

    gdf["Land_Acres"] = pd.to_numeric(gdf["Land_Acres"], errors="coerce")
    gdf["Tax_Exempt"] = classify_tax_exempt(gdf)

    compute_value_per_acre(gdf)
    gdf = filter_value_per_acre(gdf)
    compute_capped_value_per_acre(gdf)

    filename = town_name_to_file_name(output_dir, town_name)
    export_geojson(gdf, filename)
    return filename


def process_statewide(output_dir, parquet_path, cama_dir=None, overwrite=False):
    """Read the statewide GeoParquet town-by-town and process each.
    Returns list of towns that failed."""
    # Read just the Town_Name column to get the list of towns (low memory)
    names_df = pd.read_parquet(parquet_path, columns=["Town_Name"])
    town_names = sorted(names_df["Town_Name"].str.strip().unique())
    print(f"Found {len(town_names)} towns in {parquet_path}")
    del names_df

    failed = []
    for town_name in town_names:
        filename = town_name_to_file_name(output_dir, town_name)
        if not overwrite and os.path.exists(filename):
            print(f"\tFile already exists: {filename}")
            continue

        try:
            # Read one town at a time using row-group filtering
            gdf = gpd.read_parquet(
                parquet_path,
                filters=[("Town_Name", "==", town_name)],
            )
            print(f"\tProcessing {town_name} ({len(gdf)} parcels)")
            process_town(gdf, town_name, output_dir, cama_dir)
            print(f"\t\tExported {town_name}")
        except Exception as e:
            print(f"\t\tError processing {town_name}: {e}")
            failed.append(town_name)
        finally:
            gc.collect()

    return failed
