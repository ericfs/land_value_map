"""Show sample data for towns with 0 matches to understand format differences."""

import sys
import os
import re
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

def normalize_cols(df):
    def camel_to_capital_snake(name):
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', name)
    df.columns = [col.replace(' ', '_') for col in df.columns]
    df.columns = [camel_to_capital_snake(col) for col in df.columns]

def show(gdb_path, tl, p_cols=None, c_cols=None, n=5):
    parcel_df = gpd.read_file(gdb_path, layer=tl.parcels_layer_name)
    cama_df = gpd.read_file(gdb_path, layer=tl.cama_layer_name)
    normalize_cols(cama_df)
    town_name = tl.town_name
    print(f"\n{'='*60}\n{town_name} ({len(parcel_df)} parcels, {len(cama_df)} CAMA)")

    if p_cols:
        pc = [c for c in p_cols if c in parcel_df.columns]
        if pc:
            print(f"  PARCEL [{', '.join(pc)}]:")
            print(parcel_df[pc].head(n).to_string(index=False))
    else:
        print(f"  PARCEL cols: {list(parcel_df.columns)}")
        print(parcel_df.drop(columns=['geometry'], errors='ignore').head(n).iloc[:, :10].to_string(index=False))

    if c_cols:
        cc = [c for c in c_cols if c in cama_df.columns]
        if cc:
            print(f"  CAMA [{', '.join(cc)}]:")
            print(cama_df[cc].head(n).to_string(index=False))
    else:
        print(f"  CAMA cols: {list(cama_df.columns)}")
        print(cama_df.head(n).iloc[:, :10].to_string(index=False))

def find(town_name_lower, gdbs):
    for cog_name, gdb_path in gdbs:
        tls = gdb_to_town_layers(gdb_path)
        for tl in tls:
            if tl.town_name and tl.town_name.lower() == town_name_lower:
                return gdb_path, tl
    return None, None

def main():
    gdbs = list_cog_gdbs(COG_DIR)

    targets = [
        ('barkhamsted', None, None),
        ('bethel', ['Link'], ['PARID', 'ALT_ID', 'ADRNO', 'ADRSTR']),
        ('bridgewater', None, None),
        ('deep river', ['Map', 'Block', 'Lot', 'Full_Num', 'GISFullNum', 'Parcel_Num'], ['GIS_Tag', 'Map', 'Block', 'Lot', 'PID', 'Account_Number']),
        ('durham', ['Map', 'Block', 'Lot', 'Full_Num', 'Parcel_Num'], ['GIS_Tag', 'Map', 'Block', 'Lot', 'PID']),
        ('east haddam', ['JWS_PID', 'JWS_MAP', 'JWS_LOT', 'MAP', 'LOT', 'Full_Num'], ['GIS_Tag', 'Map', 'Block', 'Lot', 'link', 'PID']),
        ('groton', ['Link'], ['GIS_Tag', 'Map', 'Map_Cut', 'Block', 'Lot', 'PID']),
        ('hartford', ['GIS_PIN', 'PARCELNUMB', 'CODE'], ['GISTag', 'GIS_Tag', 'PID', 'Map', 'Block', 'Lot']),
        ('lebanon', ['Map', 'Block', 'Lot', 'Full_Num', 'Parcel_Num'], ['GIS_Tag', 'Map', 'Block', 'Lot', 'PID', 'Account_Number']),
        ('ledyard', ['Link'], ['GIS_Tag', 'Map', 'Block', 'Lot', 'PID', 'Account_Number']),
        ('middletown', ['Parcel_ID', 'Map', 'Lot'], ['GIS_Tag', 'link', 'Map', 'Block', 'Lot', 'Map_Cut', 'PID']),
        ('montville', ['Map', 'Block', 'Lot', 'Full_Num', 'Parcel_Num'], ['GIS_Tag', 'Map', 'Block', 'Lot', 'Map_Cut', 'PID']),
        ('new london', ['Link'], ['GIS_Tag', 'Map', 'Block', 'Lot', 'Map_Cut', 'Lot_Cut', 'Unit', 'Parcel_ID']),
        ('old lyme', ['Link'], ['PID', 'GIS_Tag', 'link', 'Map', 'Block', 'Lot', 'Account_Number']),
        ('oxford', ['Link', 'Parcel_ID'], ['GIS_Tag', 'Map', 'Block', 'Lot', 'PID', 'Account_Number']),
        ('roxbury', ['MAP', 'LOT', 'MBL', 'MAP_STRNG'], ['GIS_Tag', 'Map', 'Lot', 'PID']),
        ('sherman', ['JWS_PID', 'JWS_MAP', 'JWS_LOT', 'JWS_SUBLOT', 'ORIG_PID'], ['Gis_Full_Number', 'Cama_Full_Number', 'ID', 'Parcel_Number', 'Map', 'Lot', 'Plot']),
        ('sprague', ['Link'], ['GIS_Tag', 'PID', 'Account_Number', 'Account_Number_X', 'Map']),
        ('thomaston', ['Link'], ['GIS_Tag', 'PID', 'Account_Number', 'Map']),
        ('wethersfield', ['GISID', 'Code', 'DisplayOnT'], ['GIS_Tag', 'PID', 'Map', 'Block', 'Lot', 'Account_Number']),
        ('winchester', ['Map', 'Block', 'Lot', 'ParcelID', 'D_GIS_PROP'], ['PROP_ID', 'LAND_VAL', 'TOTAL_VAL']),
    ]

    for town_name, p_cols, c_cols in targets:
        gdb_path, tl = find(town_name, gdbs)
        if gdb_path is None:
            print(f"\nNOT FOUND: {town_name}")
            continue
        try:
            show(gdb_path, tl, p_cols, c_cols)
        except Exception as e:
            print(f"ERROR {town_name}: {e}")

if __name__ == '__main__':
    main()
