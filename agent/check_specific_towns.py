"""
Targeted investigation for hard towns - check specific join strategies.
"""

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

def load_town(gdb_path, tl):
    parcel_df = gpd.read_file(gdb_path, layer=tl.parcels_layer_name)
    cama_df = gpd.read_file(gdb_path, layer=tl.cama_layer_name)
    normalize_cols(cama_df)
    return parcel_df, cama_df

def try_join(parcel_df, cama_df, pk, ck, as_number=False):
    if pk not in parcel_df.columns or ck not in cama_df.columns:
        return 0, 0
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
    return len(merged), ratio

def try_compound(parcel_df, cama_df, p_cols, c_cols, sep='-'):
    ap = [c for c in p_cols if c in parcel_df.columns]
    ac = [c for c in c_cols if c in cama_df.columns]
    if not ap or not ac:
        return 0, 0, None, None
    p = parcel_df.copy()
    c = cama_df.copy()
    pk = '__'.join(ap) + '_key'
    ck = '__'.join(ac) + '_key'
    p[pk] = p[ap].apply(lambda row: sep.join(str(v) for v in row), axis=1)
    c[ck] = c[ac].apply(lambda row: sep.join(str(v) for v in row), axis=1)
    merged = pd.merge(p[[pk]], c[[ck]], left_on=pk, right_on=ck, how='inner')
    ratio = len(merged) / len(parcel_df) if len(parcel_df) > 0 else 0
    return len(merged), ratio, pk, ck

def find_gdb_and_layer(town_name_lower, gdbs, towns_df):
    for cog_name, gdb_path in gdbs:
        tls = gdb_to_town_layers(gdb_path)
        for tl in tls:
            if tl.town_name and tl.town_name.lower() == town_name_lower:
                return gdb_path, tl
    return None, None

def investigate(town_name, gdbs, towns_df, checks):
    """checks = list of (parcel_cols_or_single, cama_cols_or_single, is_compound, as_number, sep)"""
    gdb_path, tl = find_gdb_and_layer(town_name.lower(), gdbs, towns_df)
    if gdb_path is None:
        print(f"  NOT FOUND: {town_name}")
        return
    parcel_df, cama_df = load_town(gdb_path, tl)
    print(f"\n{town_name} ({len(parcel_df)} parcels, {len(cama_df)} CAMA rows)")
    for check in checks:
        pk, ck, is_compound, as_number = check[:4]
        sep = check[4] if len(check) > 4 else '-'
        if is_compound:
            n, ratio, _, _ = try_compound(parcel_df, cama_df, pk, ck, sep)
            print(f"  compound {pk}↔{ck} sep='{sep}': {n}/{len(parcel_df)} = {ratio:.3f}")
        else:
            n, ratio = try_join(parcel_df, cama_df, pk, ck, as_number)
            print(f"  {pk}↔{ck} as_number={as_number}: {n}/{len(parcel_df)} = {ratio:.3f}")

def show_samples(town_name, gdbs, n=5):
    gdb_path, tl = find_gdb_and_layer(town_name.lower(), gdbs, read_towns_df(METADATA_PATH))
    if not gdb_path:
        print(f"NOT FOUND: {town_name}")
        return
    parcel_df, cama_df = load_town(gdb_path, tl)
    print(f"\n{town_name} PARCEL sample:")
    print(parcel_df.drop(columns=['geometry'], errors='ignore').head(n).to_string(index=False, max_colwidth=30))
    print(f"\n{town_name} CAMA sample:")
    print(cama_df.head(n).to_string(index=False, max_colwidth=30))
    return parcel_df, cama_df

def main():
    towns_df = read_towns_df(METADATA_PATH)
    gdbs = list_cog_gdbs(COG_DIR)

    # ---- Avon: PARNO in parcels, PROP in CAMA ----
    investigate('Avon', gdbs, towns_df, [
        ('PARNO', 'PROP', False, False),
        ('PARNO', 'PROP', False, True),
        ('PID_Number', 'PROP', False, False),
        ('PID_Number', 'PROP', False, True),
    ])

    # ---- Barkhamsted ----
    investigate('Barkhamsted', gdbs, towns_df, [
        ('Link', 'Parcel_ID', False, False),
        ('Link', 'GIS_Tag', False, False),
        ('Link', 'Account_Number', False, False),
        ('Link', 'Account_Number', False, True),
        ('Link', 'Map', False, False),
        (['Link'], ['Map', 'Map_Cut', 'Block', 'Lot'], True, False),
    ])

    # ---- Bethel ----
    investigate('Bethel', gdbs, towns_df, [
        ('Link', 'PARID', False, False),
        ('Link', 'ALT_ID', False, False),
    ])

    # ---- Bristol: has 'link' (lowercase) ----
    investigate('Bristol', gdbs, towns_df, [
        ('link', 'Account_Number', False, False),
        ('link', 'Account_Number', False, True),
        ('link', 'Parcel_ID', False, False),
        ('link', 'GIS_Tag', False, False),
    ])

    # ---- Canaan ----
    investigate('Canaan', gdbs, towns_df, [
        ('UniqueID', 'GIS_Tag', False, False),
        ('UniqueID', 'PID', False, False),
        ('UniqueID', 'Account_Number', False, False),
        ('MBL', 'GIS_Tag', False, False),
    ])

    # ---- Colebrook ----
    investigate('Colebrook', gdbs, towns_df, [
        ('UniqueID', 'GIS_Tag', False, False),
        ('UniqueID', 'Parcel_ID', False, False),
        ('UniqueID', 'Account_Number', False, False),
        ('MBL', 'GIS_Tag', False, False),
    ])

    # ---- Deep River: Map/Block/Lot compound ----
    investigate('Deep River', gdbs, towns_df, [
        ('Full_Num', 'GIS_Tag', False, False),
        ('Full_Num', 'PID', False, False),
        ('Full_Num', 'Account_Number', False, False),
        (['Map', 'Block', 'Lot'], ['Map', 'Map_Cut', 'Block'], True, False),
        (['Map', 'Block', 'Lot'], ['Map', 'Block', 'Lot'], True, False),
        ('GISFullNum', 'GIS_Tag', False, False),
    ])

    # ---- Durham: compound ----
    investigate('Durham', gdbs, towns_df, [
        ('Full_Num', 'GIS_Tag', False, False),
        ('Full_Num', 'PID', False, False),
        ('Full_Num', 'Account_Number', False, False),
        (['Map', 'Block', 'Lot'], ['Map', 'Block', 'Lot'], True, False),
    ])

    # ---- East Haddam ----
    investigate('East Haddam', gdbs, towns_df, [
        ('JWS_PID', 'PID', False, False),
        ('JWS_PID', 'GIS_Tag', False, False),
        ('Full_Num', 'GIS_Tag', False, False),
        (['JWS_MAP', 'JWS_LOT'], ['Map', 'Lot'], True, False),
        (['MAP', 'LOT'], ['Map', 'Lot'], True, False),
    ])

    # ---- Enfield ----
    investigate('Enfield', gdbs, towns_df, [
        ('GIS_ID', 'GIS_Tag', False, False),
        ('GIS_ID', 'Parcel_ID', False, False),
        ('GIS_ID', 'Account_Number', False, False),
        ('Parcel_ID', 'GIS_Tag', False, False),
        ('Parcel_ID', 'Parcel_ID', False, False),
        ('Map_Lot', 'GIS_Tag', False, False),
        ('Map_Lot', 'Parcel_ID', False, False),
    ])

    # ---- Groton: Map+MapCut+Block+Lot compound ----
    investigate('Groton', gdbs, towns_df, [
        ('Link', 'GIS_Tag', False, False),
        (['Link'], ['Map', 'Map_Cut', 'Block', 'Lot'], True, False),
        (['Link'], ['Map', 'Block', 'Lot'], True, False),
    ])

    # ---- Hartford ----
    investigate('Hartford', gdbs, towns_df, [
        ('GIS_PIN', 'GISTag', False, False),
        ('GIS_PIN', 'GIS_Tag', False, False),
        ('PARCELNUMB', 'GISTag', False, False),
        ('PARCELNUMB', 'PID', False, False),
        ('GIS_PIN', 'PID', False, False),
    ])

    # ---- Hartland: F_O_PIN, LOT, AMAP, BLOCK ----
    investigate('Hartland', gdbs, towns_df, [
        ('F_O_PIN', 'GIS_Tag', False, False),
        ('F_O_PIN', 'Parcel_ID', False, False),
        ('F_O_PIN', 'Account_Number', False, False),
        ('F_O_PIN', 'PID', False, False),
        (['AMAP', 'BLOCK', 'LOT'], ['Map', 'Block', 'Lot'], True, False),
    ])

    # ---- Harwinton ----
    investigate('Harwinton', gdbs, towns_df, [
        ('UniqueID', 'Account_Number', False, False),
        ('UniqueID', 'Parcel_ID', False, False),
        ('UniqueID', 'GIS_Tag', False, False),
        ('MBL', 'GIS_Tag', False, False),
    ])

    # ---- Kent ----
    investigate('Kent', gdbs, towns_df, [
        ('TA_ID', 'GIS_Tag', False, False),
        ('TA_ID', 'Parcel_ID', False, False),
        ('TA_ID', 'Account_Number', False, False),
        ('MAP_BL1', 'GIS_Tag', False, False),
        (['MAP2', 'LOT_2'], ['Map', 'Lot'], True, False),
    ])

    # ---- Lebanon: compound ----
    investigate('Lebanon', gdbs, towns_df, [
        ('Full_Num', 'GIS_Tag', False, False),
        ('Full_Num', 'Account_Number', False, False),
        ('Full_Num', 'Parcel_ID', False, False),
        (['Map', 'Block', 'Lot'], ['Map', 'Block', 'Lot'], True, False),
        (['Map', 'Block', 'Lot'], ['Map', 'Map_Cut', 'Block', 'Lot'], True, False),
    ])

    # ---- Ledyard: compound ----
    investigate('Ledyard', gdbs, towns_df, [
        ('Link', 'GIS_Tag', False, False),
        ('Link', 'Parcel_ID', False, False),
        (['Link'], ['Map', 'Block', 'Lot'], True, False),
    ])

    # ---- Middletown ----
    investigate('Middletown', gdbs, towns_df, [
        ('Parcel_ID', 'GIS_Tag', False, False),
        ('Parcel_ID', 'PID', False, False),
        ('Parcel_ID', 'Account_Number', False, False),
        (['Map', 'Lot'], ['Map', 'Lot'], True, False),
    ])

    # ---- Montville: compound ----
    investigate('Montville', gdbs, towns_df, [
        ('Full_Num', 'GIS_Tag', False, False),
        ('Full_Num', 'PID', False, False),
        ('Full_Num', 'Account_Number', False, False),
        (['Map', 'Block', 'Lot'], ['Map', 'Block', 'Lot'], True, False),
        (['Map', 'Block', 'Lot'], ['Map', 'Map_Cut', 'Block', 'Lot'], True, False),
    ])

    # ---- Morris ----
    investigate('Morris', gdbs, towns_df, [
        ('UniqueID', 'GIS_Tag', False, False),
        ('UniqueID', 'Account_Number', False, False),
        ('UniqueID', 'Parcel_ID', False, False),
        ('MBL', 'GIS_Tag', False, False),
    ])

    # ---- New London: compound ----
    investigate('New London', gdbs, towns_df, [
        ('Link', 'GIS_Tag', False, False),
        ('Link', 'Parcel_ID', False, False),
        (['Link'], ['Map', 'Block', 'Lot', 'Map_Cut', 'Lot_Cut', 'Unit'], True, False),
    ])

    # ---- Norfolk ----
    investigate('Norfolk', gdbs, towns_df, [
        ('UniqueID', 'GIS_Tag', False, False),
        ('UniqueID', 'PID', False, False),
        ('UniqueID', 'Account_Number', False, False),
        ('MBL', 'GIS_Tag', False, False),
    ])

    # ---- Old Lyme ----
    investigate('Old Lyme', gdbs, towns_df, [
        ('Link', 'PID', False, False),
        ('Link', 'GIS_Tag', False, False),
        ('Link', 'Account_Number', False, False),
        ('Link', 'link', False, False),
    ])

    # ---- Oxford ----
    investigate('Oxford', gdbs, towns_df, [
        ('Link', 'PID', False, False),
        ('Link', 'Account_Number', False, False),
        ('Parcel_ID', 'Parcel_ID', False, False),
        ('Parcel_ID', 'Account_Number', False, False),
    ])

    # ---- Redding ----
    investigate('Redding', gdbs, towns_df, [
        ('GIS_ID', 'GIS_Tag', False, False),
        ('GIS_ID', 'PID', False, False),
        ('GIS_ID', 'link', False, False),
        ('PIN', 'PID', False, False),
        ('PIN', 'GIS_Tag', False, False),
        (['Map', 'Lot'], ['Map', 'Lot'], True, False),
    ])

    # ---- Roxbury ----
    investigate('Roxbury', gdbs, towns_df, [
        ('MBL', 'GIS_Tag', False, False),
        ('MAP', 'Map', False, False),
        (['MAP', 'LOT'], ['Map', 'Lot'], True, False),
    ])

    # ---- Sharon ----
    investigate('Sharon', gdbs, towns_df, [
        ('MAP_LOT1', 'GIS_Tag', False, False),
        ('MAP_LOT2', 'GIS_Tag', False, False),
        (['MAP1', 'LOT1'], ['Map', 'Lot'], True, False),
        (['MAP2', 'LOT2'], ['Map', 'Lot'], True, False),
    ])

    # ---- Sherman: JWS_PID or Gis_Full_Number ----
    investigate('Sherman', gdbs, towns_df, [
        ('JWS_PID', 'Gis_Full_Number', False, False),
        ('JWS_PID', 'Cama_Full_Number', False, False),
        ('JWS_PID', 'ID', False, False),
        ('JWS_PID', 'Parcel_Number', False, False),
        (['JWS_MAP', 'JWS_LOT'], ['Map', 'Lot'], True, False),
        (['JWS_MAP', 'JWS_LOT', 'JWS_SUBLOT'], ['Map', 'Lot', 'Plot'], True, False),
    ])

    # ---- Sprague ----
    investigate('Sprague', gdbs, towns_df, [
        ('Link', 'PID', False, False),
        ('Link', 'Account_Number', False, False),
        ('Link', 'GIS_Tag', False, False),
    ])

    # ---- Thomaston ----
    investigate('Thomaston', gdbs, towns_df, [
        ('Link', 'PID', False, False),
        ('Link', 'Account_Number', False, False),
        ('Link', 'GIS_Tag', False, False),
    ])

    # ---- Warren ----
    investigate('Warren', gdbs, towns_df, [
        ('UNIQUE_ID', 'GISID', False, False),
        ('UNIQUE_ID', 'Account', False, False),
        ('Map_Lot', 'GISID', False, False),
        (['MAP', 'LOT'], ['Map', 'Lot'], True, False),  # Warren CAMA uses different cols
    ])

    # ---- Wethersfield ----
    investigate('Wethersfield', gdbs, towns_df, [
        ('GISID', 'GIS_Tag', False, False),
        ('GISID', 'PID', False, False),
        ('GISID', 'Account_Number', False, False),
    ])

    # ---- Winchester ----
    investigate('Winchester', gdbs, towns_df, [
        ('ParcelID', 'PROP_ID', False, False),
        (['Map', 'Block', 'Lot'], ['Map', 'Block', 'Lot'], True, False),
    ])

if __name__ == '__main__':
    main()
