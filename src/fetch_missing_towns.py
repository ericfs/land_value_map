"""Fetch parcel data for towns missing from the per-COG GDB files.

These 10 towns have no _Parcels layer in their COG's GDB, so we fetch
pre-joined parcel+CAMA data from the CT statewide CAMA and Parcel Layer
(ArcGIS Feature Service).
"""

import argparse
import os
import pandas as pd
import geopandas as gpd
import requests

from export_geojson import export_geojson
from town_name import town_name_to_file_name
from value_per_acre import compute_value_per_acre, filter_value_per_acre, compute_capped_value_per_acre

FEATURE_SERVICE_URL = (
    "https://services3.arcgis.com/3FL1kr7L4LvwA2Kb/arcgis/rest/services/"
    "Connecticut_CAMA_and_Parcel_Layer/FeatureServer/0/query"
)

MISSING_TOWNS = [
    "Bolton", "Columbia", "Granby", "Hebron", "Rocky Hill",
    "Stafford", "Willington", "Cornwall", "New Hartford", "North Canaan",
]

OUT_FIELDS = "Appraised_Land,Appraised_Building,Appraised_Outbuilding,Land_Acres"


def fetch_town_parcels(town_name):
    """Query the ArcGIS Feature Service for all parcels in a town.
    Paginates automatically (ArcGIS caps at 2000 features per request).
    """
    all_features = []
    offset = 0
    while True:
        params = {
            "where": f"Town_Name='{town_name}'",
            "outFields": OUT_FIELDS,
            "f": "geojson",
            "resultOffset": offset,
            "resultRecordCount": 2000,
        }
        resp = requests.get(FEATURE_SERVICE_URL, params=params, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        features = data.get("features", [])
        if not features:
            break
        all_features.extend(features)
        # If we got fewer than 2000, we've reached the end
        if len(features) < 2000:
            break
        offset += len(features)

    if not all_features:
        return gpd.GeoDataFrame()

    geojson = {"type": "FeatureCollection", "features": all_features}
    gdf = gpd.GeoDataFrame.from_features(geojson, crs="EPSG:4326")
    return gdf


def process_town(gdf, town_name, output_dir):
    """Compute value per acre and export GeoJSON for a fetched town."""
    # Compute Appraised_Total from component fields
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


def fetch_missing_towns(output_dir, overwrite=False):
    """Fetch and process all missing towns. Returns list of towns that failed."""
    failed = []
    for town_name in MISSING_TOWNS:
        filename = town_name_to_file_name(output_dir, town_name)
        if not overwrite and os.path.exists(filename):
            print(f"\tFile already exists: {filename}")
            continue

        print(f"\n\tFetching statewide parcel data for: {town_name}")
        try:
            gdf = fetch_town_parcels(town_name)
            if gdf.empty:
                print(f"\t\tNo parcels returned for {town_name}")
                failed.append(town_name)
                continue
            print(f"\t\tFetched {len(gdf)} parcels")
            process_town(gdf, town_name, output_dir)
            print(f"\t\tExported {town_name}")
        except Exception as e:
            print(f"\t\tError processing {town_name}: {e}")
            failed.append(town_name)
    return failed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Fetch parcel data for towns missing from COG GDB files."
    )
    parser.add_argument("--output_dir", required=True, help="Output directory for GeoJSON files.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing files.")
    args = parser.parse_args()

    failed = fetch_missing_towns(args.output_dir, overwrite=args.overwrite)
    if failed:
        print(f"\nFailed towns: {failed}")
    else:
        print("\nAll missing towns fetched successfully.")
