"""
Investigate the specific towns that failed to find join keys.
"""

import sys
import os
import json
import re
import fiona
import geopandas as gpd
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from town_layers import gdb_to_town_layers
from town_metadata import read_towns_df

COG_DIR = os.path.join(os.path.dirname(__file__), '..', 'inputs', 'Parcel Collection 2024', 'Parcel_By_COG')
METADATA_PATH = os.path.join(os.path.dirname(__file__), '..', 'inputs', 'Metadata_2024.csv')

def list_cog_gdbs(cog_dir):
    items = os.listdir(cog_dir)
    folders = [i for i in items if os.path.isdir(os.path.join(cog_dir, i))]
    return [(item, os.path.join(cog_dir, item, f'{item}.gdb')) for item in sorted(folders)]

def show_town(gdb_path, town_layer_info, sample_rows=3):
    town_name = town_layer_info.town_name
    parcel_layer = town_layer_info.parcels_layer_name
    cama_layer = town_layer_info.cama_layer_name

    parcel_df = gpd.read_file(gdb_path, layer=parcel_layer)
    cama_df = gpd.read_file(gdb_path, layer=cama_layer)

    def camel_to_capital_snake(name):
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', name)
    cama_df.columns = [col.replace(' ', '_') for col in cama_df.columns]
    cama_df.columns = [camel_to_capital_snake(col) for col in cama_df.columns]

    print(f"\n{'='*60}")
    print(f"TOWN: {town_name}")
    print(f"  Parcel rows: {len(parcel_df)}, CAMA rows: {len(cama_df)}")
    print(f"\n  Parcel columns: {list(parcel_df.columns)}")
    print(f"  Parcel sample:")
    print(parcel_df.drop(columns=['geometry'], errors='ignore').head(sample_rows).to_string(index=False))
    print(f"\n  CAMA columns: {list(cama_df.columns)}")
    print(f"  CAMA sample:")
    print(cama_df.head(sample_rows).to_string(index=False))
    return parcel_df, cama_df

def try_compound_join(parcel_df, cama_df, parcel_cols, cama_cols, sep='-'):
    """Try a compound key join."""
    available_p = [c for c in parcel_cols if c in parcel_df.columns]
    available_c = [c for c in cama_cols if c in cama_df.columns]
    if len(available_p) < 2 or len(available_c) < 2:
        return None, None, None, None
    p = parcel_df.copy()
    c = cama_df.copy()
    pk = '_'.join(available_p) + '_key'
    ck = '_'.join(available_c) + '_key'
    p[pk] = p[available_p].apply(lambda row: sep.join(str(v) for v in row), axis=1)
    c[ck] = c[available_c].apply(lambda row: sep.join(str(v) for v in row), axis=1)
    merged = pd.merge(p[[pk]], c[[ck]], left_on=pk, right_on=ck, how='inner')
    n_parcel = len(p)
    ratio = len(merged) / n_parcel if n_parcel > 0 else 0
    print(f"    Compound join {available_p}↔{available_c}: {len(merged)}/{n_parcel} = {ratio:.2f}")
    return merged, ratio, pk, ck

def try_single_join(parcel_df, cama_df, pk, ck, as_number=False):
    if pk not in parcel_df.columns or ck not in cama_df.columns:
        return 0
    p = parcel_df[[pk]].copy()
    c = cama_df[[ck]].copy()
    if as_number:
        p[pk] = pd.to_numeric(p[pk], errors='coerce')
        c[ck] = pd.to_numeric(c[ck], errors='coerce')
        p = p.dropna(subset=[pk])
        c = c.dropna(subset=[ck])
    else:
        p[pk] = p[pk].astype(str)
        c[ck] = c[ck].astype(str)
    merged = pd.merge(p, c, left_on=pk, right_on=ck, how='inner')
    ratio = len(merged) / len(parcel_df) if len(parcel_df) > 0 else 0
    print(f"    Join {pk}↔{ck} (as_number={as_number}): {len(merged)}/{len(parcel_df)} = {ratio:.2f}")
    return ratio

HARD_TOWNS = [
    'avon', 'barkhamsted', 'bethel', 'bridgewater', 'bristol', 'canaan', 'colebrook',
    'deep river', 'durham', 'east haddam', 'enfield', 'groton', 'hartford', 'hartland',
    'harwinton', 'kent', 'lebanon', 'ledyard', 'middletown', 'montville', 'morris',
    'new london', 'norfolk', 'old lyme', 'oxford', 'redding', 'roxbury', 'sharon',
    'sherman', 'sprague', 'thomaston', 'warren', 'wethersfield', 'winchester'
]

def main():
    towns_df = read_towns_df(METADATA_PATH)
    gdbs = list_cog_gdbs(COG_DIR)

    for cog_name, gdb_path in gdbs:
        town_layers = gdb_to_town_layers(gdb_path)
        for tl in town_layers:
            if tl.town_name is None:
                continue
            if tl.town_name.lower() not in HARD_TOWNS:
                continue
            try:
                parcel_df, cama_df = show_town(gdb_path, tl)
            except Exception as e:
                print(f"  ERROR for {tl.town_name}: {e}")

if __name__ == '__main__':
    main()
