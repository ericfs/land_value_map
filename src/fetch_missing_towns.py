"""Process parcel data for towns missing from the per-COG GDB files.

These 10 towns have no _Parcels layer in their COG's GDB, so we read
pre-joined parcel+CAMA data from the CT statewide CAMA and Parcel Layer GDB.
"""

import argparse
import os
import pandas as pd
import geopandas as gpd
import pyogrio
from shapely.validation import make_valid

from export_geojson import export_geojson
from town_name import town_name_to_file_name
from value_per_acre import compute_value_per_acre, filter_value_per_acre, compute_capped_value_per_acre

STATEWIDE_GDB = "5b462e9a-7190-47bf-a2ce-9b69d12ea06b.gdb"
STATEWIDE_LAYER = "Connecticut_CAMA_and_Parcel_Layer"

MISSING_TOWNS = [
    "Bolton", "Columbia", "Granby", "Hebron", "Rocky Hill",
    "Stafford", "Willington", "Cornwall", "New Hartford", "North Canaan",
]


def read_town_parcels(gdb_path, town_name):
    """Read parcels for a single town from the statewide GDB using a SQL filter."""
    result = pyogrio.read_dataframe(
        gdb_path, layer=STATEWIDE_LAYER,
        where=f"Town_Name = '{town_name}'",
        on_invalid="fix",
    )
    return result


def process_town(gdf, town_name, output_dir):
    """Compute value per acre and export GeoJSON for a town."""
    # Drop rows with null geometry and fix invalid geometries
    gdf = gdf[gdf.geometry.notna()].copy()
    gdf["geometry"] = gdf["geometry"].apply(make_valid)

    for col in ["Appraised_Land", "Appraised_Building", "Appraised_Outbuilding"]:
        gdf[col] = pd.to_numeric(gdf[col], errors="coerce").fillna(0)
    gdf["Appraised_Total"] = (
        gdf["Appraised_Land"] + gdf["Appraised_Building"] + gdf["Appraised_Outbuilding"]
    )

    gdf["Land_Acres"] = pd.to_numeric(gdf["Land_Acres"], errors="coerce")

    compute_value_per_acre(gdf)
    gdf = filter_value_per_acre(gdf)
    compute_capped_value_per_acre(gdf)

    filename = town_name_to_file_name(output_dir, town_name)
    export_geojson(gdf, filename)
    return filename


def fetch_missing_towns(output_dir, overwrite=False, input_dir=None):
    """Read and process all missing towns from the statewide GDB.
    Returns list of towns that failed."""
    gdb_path = os.path.join(input_dir, STATEWIDE_GDB) if input_dir else STATEWIDE_GDB
    failed = []
    for town_name in MISSING_TOWNS:
        filename = town_name_to_file_name(output_dir, town_name)
        if not overwrite and os.path.exists(filename):
            print(f"\tFile already exists: {filename}")
            continue

        print(f"\n\tReading statewide parcel data for: {town_name}")
        try:
            gdf = read_town_parcels(gdb_path, town_name)
            if gdf.empty:
                print(f"\t\tNo parcels found for {town_name}")
                failed.append(town_name)
                continue
            print(f"\t\tRead {len(gdf)} parcels")
            process_town(gdf, town_name, output_dir)
            print(f"\t\tExported {town_name}")
        except Exception as e:
            print(f"\t\tError processing {town_name}: {e}")
            failed.append(town_name)
    return failed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Process parcel data for towns missing from COG GDB files."
    )
    parser.add_argument("--input_dir", default="inputs", help="Path to inputs directory.")
    parser.add_argument("--output_dir", required=True, help="Output directory for GeoJSON files.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing files.")
    args = parser.parse_args()

    failed = fetch_missing_towns(args.output_dir, overwrite=args.overwrite, input_dir=args.input_dir)
    if failed:
        print(f"\nFailed towns: {failed}")
    else:
        print("\nAll missing towns processed successfully.")
