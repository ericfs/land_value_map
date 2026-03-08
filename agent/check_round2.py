"""Round 2: Test specific join strategies for towns with format differences."""

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

def find(town_name_lower, gdbs):
    for cog_name, gdb_path in gdbs:
        tls = gdb_to_town_layers(gdb_path)
        for tl in tls:
            if tl.town_name and tl.town_name.lower() == town_name_lower:
                return gdb_path, tl
    return None, None

def load(town_name, gdbs):
    gdb_path, tl = find(town_name.lower(), gdbs)
    if not gdb_path:
        print(f"NOT FOUND: {town_name}")
        return None, None
    parcel_df = gpd.read_file(gdb_path, layer=tl.parcels_layer_name)
    cama_df = gpd.read_file(gdb_path, layer=tl.cama_layer_name)
    normalize_cols(cama_df)
    return parcel_df, cama_df

def do_join(p, c, pk, ck):
    p2 = p[[pk]].copy().astype(str)
    c2 = c[[ck]].copy().astype(str)
    m = pd.merge(p2, c2, left_on=pk, right_on=ck, how='inner')
    ratio = len(m) / len(p) if len(p) > 0 else 0
    print(f"  {pk}↔{ck}: {len(m)}/{len(p)} = {ratio:.3f}")
    return len(m), ratio

def main():
    gdbs = list_cog_gdbs(COG_DIR)

    # ---- Bethel: Link vs PARID - same format? Need to strip whitespace ----
    print("\n=== Bethel ===")
    p, c = load('bethel', gdbs)
    if p is not None:
        p2 = p[['Link']].copy()
        c2 = c[['PARID']].copy()
        p2['link_stripped'] = p2['Link'].str.strip()
        c2['parid_stripped'] = c2['PARID'].str.strip()
        m = pd.merge(p2[['link_stripped']], c2[['parid_stripped']], left_on='link_stripped', right_on='parid_stripped', how='inner')
        print(f"  Link.strip()↔PARID.strip(): {len(m)}/{len(p)} = {len(m)/len(p):.3f}")
        print(f"  Parcel Link samples: {list(p['Link'].str.strip().head(5))}")
        print(f"  CAMA PARID samples: {list(c['PARID'].str.strip().head(5))}")

    # ---- Bridgewater: B, M, L columns? ----
    print("\n=== Bridgewater ===")
    p, c = load('bridgewater', gdbs)
    if p is not None:
        print(f"  Parcel B,M,L samples: {list(p[['M','B','L']].head(10).to_records(index=False))}")
        print(f"  Parcel MBL samples: {list(p['MBL'].head(10))}")
        print(f"  CAMA Map,Block,Lot samples: {list(c[['Map','Block','Lot']].head(5).to_records(index=False))}")
        print(f"  CAMA Account_Number samples: {list(c['Account_Number'].head(5))}")
        # Try MBL
        c['map_block'] = c['Map'].astype(str).str.strip() + '-' + c['Block'].astype(str).str.strip()
        p['mbl_strip'] = p['MBL'].astype(str).str.strip()
        m = pd.merge(p[['mbl_strip']], c[['map_block']], left_on='mbl_strip', right_on='map_block')
        print(f"  MBL↔Map-Block: {len(m)}/{len(p)} = {len(m)/len(p):.3f}")
        # Try Parcel_ID (CAMA)
        c['parcel_id_str'] = c['Parcel_ID'].astype(str).str.strip()
        for pkey in ['PARNO', 'PIN', 'MBL']:
            if pkey in p.columns:
                p2 = p[[pkey]].astype(str).str.strip()
                m = pd.merge(p[[pkey]].astype(str), c[['parcel_id_str']], left_on=pkey, right_on='parcel_id_str')
                print(f"  {pkey}↔Parcel_ID: {len(m)}/{len(p)} = {len(m)/len(p):.3f}")

    # ---- Deep River ----
    print("\n=== Deep River ===")
    p, c = load('deep river', gdbs)
    if p is not None:
        print(f"  Parcel Map,Lot samples: {list(zip(p['Map'].head(5), p['Lot'].head(5)))}")
        print(f"  CAMA Map,Lot samples: {list(zip(c['Map'].head(5), c['Lot'].head(5)))}")
        # Map+Lot compound with numeric Map
        p2 = p.copy()
        c2 = c.copy()
        p2['map_num'] = pd.to_numeric(p2['Map'], errors='coerce')
        c2['map_num'] = pd.to_numeric(c2['Map'], errors='coerce')
        p2['lot_strip'] = p2['Lot'].astype(str).str.strip()
        c2['lot_strip'] = c2['Lot'].astype(str).str.strip()
        p2 = p2.dropna(subset=['map_num'])
        c2 = c2.dropna(subset=['map_num'])
        p2['key'] = p2['map_num'].astype(int).astype(str) + '-' + p2['lot_strip']
        c2['key'] = c2['map_num'].astype(int).astype(str) + '-' + c2['lot_strip']
        m = pd.merge(p2[['key']], c2[['key']], on='key', how='inner')
        print(f"  Map(int)+Lot↔Map(int)+Lot: {len(m)}/{len(p)} = {len(m)/len(p):.3f}")
        print(f"  Sample parcel keys: {list(p2['key'].head(5))}")
        print(f"  Sample CAMA keys: {list(c2['key'].head(5))}")

    # ---- Durham ----
    print("\n=== Durham ===")
    p, c = load('durham', gdbs)
    if p is not None:
        print(f"  Parcel Map,Lot samples: {list(zip(p['Map'].head(5), p['Lot'].head(5)))}")
        print(f"  CAMA Map,Lot samples: {list(zip(c['Map'].head(5), c['Lot'].head(5)))}")
        # Try Map+Lot numeric
        p2 = p.copy()
        c2 = c.copy()
        p2['map_num'] = pd.to_numeric(p2['Map'], errors='coerce')
        c2['map_num'] = pd.to_numeric(c2['Map'], errors='coerce')
        p2['lot_num'] = pd.to_numeric(p2['Lot'], errors='coerce')
        c2['lot_num'] = pd.to_numeric(c2['Lot'], errors='coerce')
        p2 = p2.dropna(subset=['map_num', 'lot_num'])
        c2 = c2.dropna(subset=['map_num', 'lot_num'])
        p2['key'] = p2['map_num'].astype(int).astype(str) + '-' + p2['lot_num'].astype(int).astype(str)
        c2['key'] = c2['map_num'].astype(int).astype(str) + '-' + c2['lot_num'].astype(int).astype(str)
        m = pd.merge(p2[['key']], c2[['key']], on='key', how='inner')
        print(f"  Map(int)+Lot(int)↔same: {len(m)}/{len(p)} = {len(m)/len(p):.3f}")

    # ---- East Haddam: Full_Num vs CAMA link (strip prefix) ----
    print("\n=== East Haddam ===")
    p, c = load('east haddam', gdbs)
    if p is not None:
        print(f"  Parcel Full_Num sample: {list(p['Full_Num'].head(5))}")
        print(f"  CAMA link sample: {list(c['link'].head(5))}")
        # Try stripping town prefix from CAMA link
        c['link_stripped'] = c['link'].astype(str).str.replace(r'^\d{5}-', '', regex=True)
        print(f"  CAMA link_stripped sample: {list(c['link_stripped'].head(5))}")
        m = pd.merge(p[['Full_Num']].astype(str), c[['link_stripped']], left_on='Full_Num', right_on='link_stripped', how='inner')
        print(f"  Full_Num↔link.strip_prefix: {len(m)}/{len(p)} = {len(m)/len(p):.3f}")
        # Also try JWS_PID
        m2 = pd.merge(p[['JWS_PID']].astype(str), c[['link_stripped']], left_on='JWS_PID', right_on='link_stripped', how='inner')
        print(f"  JWS_PID↔link.strip_prefix: {len(m2)}/{len(p)} = {len(m2)/len(p):.3f}")

    # ---- Groton: Link is a number, CAMA has PID as float ----
    print("\n=== Groton ===")
    p, c = load('groton', gdbs)
    if p is not None:
        print(f"  Parcel Link sample: {list(p['Link'].head(5))}")
        print(f"  CAMA PID sample (float): {list(c['PID'].head(10))}")
        print(f"  CAMA GIS_Tag sample: {list(c['GIS_Tag'].head(5))}")
        # Try Link as number vs PID as number
        p2 = p.copy()
        c2 = c.copy()
        p2['link_num'] = pd.to_numeric(p2['Link'], errors='coerce')
        c2['pid_num'] = pd.to_numeric(c2['PID'], errors='coerce')
        p2 = p2.dropna(subset=['link_num'])
        c2 = c2.dropna(subset=['pid_num'])
        m = pd.merge(p2[['link_num']], c2[['pid_num']], left_on='link_num', right_on='pid_num', how='inner')
        print(f"  Link(num)↔PID(num): {len(m)}/{len(p)} = {len(m)/len(p):.3f}")
        # Try Map*1e8 + Block*1e6 + Lot construct
        c2['parcel_id_calc'] = c['Map'].astype(float) * 1e8 + c['Block'].astype(float) * 1e6 + pd.to_numeric(c['Lot'], errors='coerce').fillna(0)
        m2 = pd.merge(p2[['link_num']], c2[['parcel_id_calc']], left_on='link_num', right_on='parcel_id_calc', how='inner')
        print(f"  Link(num)↔Map*1e8+Block*1e6+Lot: {len(m2)}/{len(p)} = {len(m2)/len(p):.3f}")
        # Try Parcel_ID column if exists
        if 'Parcel_ID' in p.columns:
            print(f"  Parcel Parcel_ID sample: {list(p['Parcel_ID'].head(5))}")

    # ---- Hartford: GIS_PIN vs GISTag as number ----
    print("\n=== Hartford ===")
    p, c = load('hartford', gdbs)
    if p is not None:
        p2 = p.copy()
        c2 = c.copy()
        p2['gis_pin_num'] = pd.to_numeric(p2['GIS_PIN'], errors='coerce')
        c2['gistag_num'] = pd.to_numeric(c2['GISTag'], errors='coerce')
        p2 = p2.dropna(subset=['gis_pin_num'])
        c2 = c2.dropna(subset=['gistag_num'])
        m = pd.merge(p2[['gis_pin_num']], c2[['gistag_num']], left_on='gis_pin_num', right_on='gistag_num', how='inner')
        print(f"  GIS_PIN(num)↔GISTag(num): {len(m)}/{len(p)} = {len(m)/len(p):.3f}")
        print(f"  PARCELNUMB samples: {list(p['PARCELNUMB'].head(3))}")
        m2 = pd.merge(p2[['PARCELNUMB']].astype(str), c2[['GISTag']].astype(str), left_on='PARCELNUMB', right_on='GISTag', how='inner')
        print(f"  PARCELNUMB↔GISTag(str): {len(m2)}/{len(p)} = {len(m2)/len(p):.3f}")
        # Also try stripping .0 from GISTag
        c2['gistag_str'] = c2['GISTag'].astype(str).str.replace(r'\.0$', '', regex=True)
        m3 = pd.merge(p[['GIS_PIN']].astype(str), c2[['gistag_str']], left_on='GIS_PIN', right_on='gistag_str', how='inner')
        print(f"  GIS_PIN↔GISTag(strip .0): {len(m3)}/{len(p)} = {len(m3)/len(p):.3f}")

    # ---- Lebanon ----
    print("\n=== Lebanon ===")
    p, c = load('lebanon', gdbs)
    if p is not None:
        print(f"  Parcel Map,Lot samples: {list(zip(p['Map'].head(5), p['Lot'].head(5)))}")
        print(f"  CAMA Map,Lot samples: {list(zip(c['Map'].head(5), c['Lot'].head(5)))}")
        print(f"  CAMA GIS_Tag samples: {list(c['GIS_Tag'].head(5))}")
        # Try Map+Lot numeric
        p2 = p.copy()
        c2 = c.copy()
        p2['map_num'] = pd.to_numeric(p2['Map'], errors='coerce')
        c2['map_num'] = pd.to_numeric(c2['Map'], errors='coerce')
        p2['lot_num'] = pd.to_numeric(p2['Lot'], errors='coerce')
        c2['lot_num'] = pd.to_numeric(c2['Lot'], errors='coerce')
        p2 = p2.dropna(subset=['map_num', 'lot_num'])
        c2 = c2.dropna(subset=['map_num', 'lot_num'])
        p2['key'] = p2['map_num'].astype(int).astype(str) + '-' + p2['lot_num'].astype(int).astype(str)
        c2['key'] = c2['map_num'].astype(int).astype(str) + '-' + c2['lot_num'].astype(int).astype(str)
        m = pd.merge(p2[['key']], c2[['key']], on='key', how='inner')
        print(f"  Map(int)+Lot(int)↔same: {len(m)}/{len(p)} = {len(m)/len(p):.3f}")
        print(f"  Sample parcel keys: {list(p2['key'].head(5))}")
        print(f"  Sample CAMA keys: {list(c2['key'].head(5))}")
        # Try GIS_Tag as parcel key (maybe it's in parcel?)
        print(f"  All parcel cols: {list(p.columns)}")

    # ---- Ledyard ----
    print("\n=== Ledyard ===")
    p, c = load('ledyard', gdbs)
    if p is not None:
        print(f"  Parcel Link sample: {list(p['Link'].head(5))}")
        print(f"  CAMA GIS_Tag sample: {list(c['GIS_Tag'].head(5))}")
        print(f"  CAMA Map,Block,Lot sample: {list(zip(c['Map'].head(5), c['Block'].head(5), c['Lot'].head(5)))}")
        # Try compound Map-Block-Lot from CAMA vs Link
        c2 = c.copy()
        c2['key'] = c2['Map'].astype(str).str.strip() + '-' + c2['Block'].astype(str).str.strip() + '-' + c2['Lot'].astype(str).str.strip()
        m = pd.merge(p[['Link']].astype(str).str.strip(), c2[['key']], left_on='Link', right_on='key', how='inner')
        print(f"  Link↔Map-Block-Lot: {len(m)}/{len(p)} = {len(m)/len(p):.3f}")
        # Try GIS_Tag as numeric
        p2 = p.copy()
        c2 = c.copy()
        p2['link_num'] = pd.to_numeric(p2['Link'], errors='coerce')
        c2['gistag_num'] = pd.to_numeric(c2['GIS_Tag'], errors='coerce')
        p2 = p2.dropna(subset=['link_num'])
        c2 = c2.dropna(subset=['gistag_num'])
        m2 = pd.merge(p2[['link_num']], c2[['gistag_num']], left_on='link_num', right_on='gistag_num', how='inner')
        print(f"  Link(num)↔GIS_Tag(num): {len(m2)}/{len(p)} = {len(m2)/len(p):.3f}")

    # ---- Middletown: Parcel_ID vs CAMA PID, link, GIS_Tag ----
    print("\n=== Middletown ===")
    p, c = load('middletown', gdbs)
    if p is not None:
        print(f"  Parcel Parcel_ID sample: {list(p['Parcel_ID'].head(5))}")
        print(f"  CAMA link sample: {list(c['link'].head(5))}")
        print(f"  CAMA GIS_Tag sample: {list(c['GIS_Tag'].head(5))}")
        print(f"  CAMA PID sample: {list(c['PID'].head(5))}")
        # Parcel_ID = "15-0409" → Map(2 digit)-Lot(4 digit). Try as-is against various CAMA cols
        for ck in ['link', 'GIS_Tag', 'PID', 'Map', 'Lot']:
            if ck in c.columns:
                m = pd.merge(p[['Parcel_ID']].astype(str), c[[ck]].astype(str), left_on='Parcel_ID', right_on=ck, how='inner')
                print(f"  Parcel_ID↔{ck}: {len(m)}/{len(p)} = {len(m)/len(p):.3f}")
        # Also Map column in parcel vs Map in CAMA
        if 'Map' in p.columns:
            p2 = p.copy()
            c2 = c.copy()
            p2['map_lot'] = p2['Map'].astype(str).str.strip() + '-' + p2['Lot'].astype(str).str.strip()
            c2['map_lot'] = c2['Map'].astype(str).str.strip() + '-' + c2['Lot'].astype(str).str.strip()
            m = pd.merge(p2[['map_lot']], c2[['map_lot']], on='map_lot', how='inner')
            print(f"  Map+Lot compound: {len(m)}/{len(p)} = {len(m)/len(p):.3f}")
            # Also try leading-zero normalization
            print(f"  Parcel Lot samples: {list(p['Lot'].head(5))}")

    # ---- Montville ----
    print("\n=== Montville ===")
    p, c = load('montville', gdbs)
    if p is not None:
        print(f"  Parcel Full_Num sample: {list(p['Full_Num'].head(5))}")
        print(f"  CAMA GIS_Tag sample: {list(c['GIS_Tag'].head(5))}")
        print(f"  CAMA Map sample: {list(c['Map'].head(5))}")
        # GIS_Tag "016/003-001" vs Full_Num "001-008-00A"
        # Try replacing / and - with same separator
        c2 = c.copy()
        c2['gis_norm'] = c2['GIS_Tag'].astype(str).str.replace('/', '-', regex=False)
        p2 = p.copy()
        p2['fn_norm'] = p2['Full_Num'].astype(str)
        m = pd.merge(p2[['fn_norm']], c2[['gis_norm']], left_on='fn_norm', right_on='gis_norm', how='inner')
        print(f"  Full_Num↔GIS_Tag(/ to -): {len(m)}/{len(p)} = {len(m)/len(p):.3f}")
        # Also show more samples
        print(f"  Full_Num sample (more): {list(p['Full_Num'].head(10))}")
        print(f"  CAMA GIS_Tag sample (more): {list(c['GIS_Tag'].head(10))}")

    # ---- New London ----
    print("\n=== New London ===")
    p, c = load('new london', gdbs)
    if p is not None:
        print(f"  Parcel Link sample: {list(p['Link'].head(5))}")
        print(f"  CAMA Map,Block,Lot sample: {list(zip(c['Map'].head(5), c['Block'].head(5), c['Lot'].head(5)))}")
        print(f"  CAMA GIS_Tag sample: {list(c['GIS_Tag'].head(5))}")
        # Try Map+Block+Lot from CAMA vs Link
        c2 = c.copy()
        c2['key'] = c2['Map'].astype(str).str.strip() + '-' + c2['Block'].astype(str).str.strip() + '-' + c2['Lot'].astype(str).str.strip()
        m = pd.merge(p[['Link']].astype(str).str.strip(), c2[['key']], left_on='Link', right_on='key', how='inner')
        print(f"  Link↔Map-Block-Lot: {len(m)}/{len(p)} = {len(m)/len(p):.3f}")
        print(f"  Sample CAMA keys: {list(c2['key'].head(5))}")
        print(f"  CAMA Parcel_ID sample: {list(c['Parcel_ID'].head(5))}")

    # ---- Old Lyme: Link vs CAMA link stripped ----
    print("\n=== Old Lyme ===")
    p, c = load('old lyme', gdbs)
    if p is not None:
        print(f"  Parcel Link sample: {list(p['Link'].head(5))}")
        print(f"  CAMA link sample: {list(c['link'].head(5))}")
        # Strip "57040-" prefix
        c2 = c.copy()
        c2['link_stripped'] = c2['link'].astype(str).str.replace(r'^\d{5}-', '', regex=True)
        print(f"  CAMA link_stripped sample: {list(c2['link_stripped'].head(5))}")
        m = pd.merge(p[['Link']].astype(str), c2[['link_stripped']], left_on='Link', right_on='link_stripped', how='inner')
        print(f"  Link↔link.strip_prefix: {len(m)}/{len(p)} = {len(m)/len(p):.3f}")
        # Also try Map-Lot join
        p2 = p.copy()
        c2b = c.copy()
        p2['map_num'] = pd.to_numeric(p2['Link'].str.split('-').str[0], errors='coerce')
        p2['lot_num'] = pd.to_numeric(p2['Link'].str.split('-').str[-1], errors='coerce')
        c2b['map_num'] = pd.to_numeric(c2b['Map'], errors='coerce')
        c2b['lot_num'] = pd.to_numeric(c2b['Lot'], errors='coerce')
        p2 = p2.dropna(subset=['map_num','lot_num'])
        c2b = c2b.dropna(subset=['map_num','lot_num'])
        p2['key'] = p2['map_num'].astype(int).astype(str) + '-' + p2['lot_num'].astype(int).astype(str)
        c2b['key'] = c2b['map_num'].astype(int).astype(str) + '-' + c2b['lot_num'].astype(int).astype(str)
        m2 = pd.merge(p2[['key']], c2b[['key']], on='key', how='inner')
        print(f"  Link(parse Map-Lot)↔Map-Lot: {len(m2)}/{len(p)} = {len(m2)/len(p):.3f}")

    # ---- Oxford: Link (hyphens) vs CAMA Map (spaces) ----
    print("\n=== Oxford ===")
    p, c = load('oxford', gdbs)
    if p is not None:
        print(f"  Parcel Link sample: {list(p['Link'].head(5))}")
        print(f"  CAMA Map sample: {list(c['Map'].head(5))}")
        # Replace spaces in CAMA Map with hyphens
        c2 = c.copy()
        c2['map_norm'] = c2['Map'].astype(str).str.strip().str.replace(r'\s+', '-', regex=True)
        m = pd.merge(p[['Link']].astype(str).str.strip(), c2[['map_norm']], left_on='Link', right_on='map_norm', how='inner')
        print(f"  Link↔Map(spaces->hyphens): {len(m)}/{len(p)} = {len(m)/len(p):.3f}")
        print(f"  Sample CAMA map_norm: {list(c2['map_norm'].head(5))}")
        # Also try stripping whitespace in parcel Link
        p2 = p.copy()
        p2['link_norm'] = p2['Link'].astype(str).str.strip()
        c3 = c.copy()
        c3['map_norm2'] = c3['Map'].astype(str).str.strip()
        m2 = pd.merge(p2[['link_norm']], c3[['map_norm2']], left_on='link_norm', right_on='map_norm2', how='inner')
        print(f"  Link.strip↔Map.strip: {len(m2)}/{len(p)} = {len(m2)/len(p):.3f}")

    # ---- Sherman: JWS_PID[:7] vs Gis_Full_Number ----
    print("\n=== Sherman ===")
    p, c = load('sherman', gdbs)
    if p is not None:
        print(f"  Parcel JWS_PID sample: {list(p['JWS_PID'].head(5))}")
        print(f"  CAMA Gis_Full_Number sample: {list(c['Gis_Full_Number'].head(5))}")
        # JWS_PID[:7] = "021-043" vs Gis_Full_Number = "076-001"
        p2 = p.copy()
        p2['pid_prefix'] = p2['JWS_PID'].astype(str).str[:7]
        m = pd.merge(p2[['pid_prefix']], c[['Gis_Full_Number']].astype(str), left_on='pid_prefix', right_on='Gis_Full_Number', how='inner')
        print(f"  JWS_PID[:7]↔Gis_Full_Number: {len(m)}/{len(p)} = {len(m)/len(p):.3f}")
        # Also try full JWS_PID without sublot (first 7) vs Parcel_Number
        m2 = pd.merge(p2[['pid_prefix']], c[['Parcel_Number']].astype(str), left_on='pid_prefix', right_on='Parcel_Number', how='inner')
        print(f"  JWS_PID[:7]↔Parcel_Number: {len(m2)}/{len(p)} = {len(m2)/len(p):.3f}")

    # ---- Sprague ----
    print("\n=== Sprague ===")
    p, c = load('sprague', gdbs)
    if p is not None:
        print(f"  Parcel all cols: {list(p.columns)}")
        print(f"  Parcel Link sample: {list(p['Link'].head(10))}")
        print(f"  CAMA PID sample: {list(c['PID'].head(10))}")
        print(f"  CAMA Map sample: {list(c['Map'].head(10))}")
        # Link = "24-03-03" = Map-Block-Lot. Try compound CAMA
        c2 = c.copy()
        c2['map_block_lot'] = c2['Map'].astype(str).str.zfill(2) + '-' + c2['Map'].astype(str)  # no, different
        # Try: Link format Map(2)-Block(2)-Lot(2) or Map(2)-Map(3)-something
        # CAMA has GIS_Tag = None, PID = sequential integer
        # Maybe join on Map only?
        p2 = p.copy()
        p2['link_map'] = p2['Link'].astype(str).str.split('-').str[0].str.strip()
        c2['map_str'] = c2['Map'].astype(str).str.strip()
        m = pd.merge(p2[['link_map']], c2[['map_str']], left_on='link_map', right_on='map_str', how='inner')
        print(f"  Link(map-part)↔Map: {len(m)}/{len(p)} = {len(m)/len(p):.3f}")
        # Check CAMA Account_Number_X (it was a float in sample)
        print(f"  CAMA GIS_Tag,PID,Account_Number,Map all cols: {list(c.columns[:15])}")

    # ---- Thomaston ----
    print("\n=== Thomaston ===")
    p, c = load('thomaston', gdbs)
    if p is not None:
        print(f"  Parcel Link sample: {list(p['Link'].head(10))}")
        print(f"  CAMA PID sample: {list(c['PID'].head(5))}")
        print(f"  CAMA Account_Number sample: {list(c['Account_Number'].head(5))}")
        # PID = "A0000100" (alpha-numeric) vs Link = "78-01-01"
        # Account_Number = "A0000100" also. Maybe a different CAMA column?
        print(f"  CAMA all cols: {list(c.columns)}")
        print(f"  CAMA sample first 5 rows:")
        print(c.head(5).to_string(index=False))
        # Show ALL parcel cols
        print(f"  Parcel all cols: {list(p.columns)}")

    # ---- Wethersfield: GISID vs GIS_Tag/PID ----
    print("\n=== Wethersfield ===")
    p, c = load('wethersfield', gdbs)
    if p is not None:
        print(f"  Parcel GISID sample: {list(p['GISID'].head(5))}")
        print(f"  CAMA GIS_Tag sample: {list(c['GIS_Tag'].head(5))}")
        print(f"  CAMA PID sample: {list(c['PID'].head(5))}")
        # GISID = 141026 (6-digit), GIS_Tag = 1001.0 (4-digit)
        # Try as numbers
        p2 = p.copy()
        c2 = c.copy()
        p2['gisid_num'] = pd.to_numeric(p2['GISID'], errors='coerce')
        c2['gistag_num'] = pd.to_numeric(c2['GIS_Tag'], errors='coerce')
        c2['pid_num'] = pd.to_numeric(c2['PID'], errors='coerce')
        p2 = p2.dropna(subset=['gisid_num'])
        c2 = c2.dropna(subset=['gistag_num'])
        m = pd.merge(p2[['gisid_num']], c2[['gistag_num']], left_on='gisid_num', right_on='gistag_num', how='inner')
        print(f"  GISID(num)↔GIS_Tag(num): {len(m)}/{len(p)} = {len(m)/len(p):.3f}")
        m2 = pd.merge(p2[['gisid_num']], c2[['pid_num']], left_on='gisid_num', right_on='pid_num', how='inner')
        print(f"  GISID(num)↔PID(num): {len(m2)}/{len(p)} = {len(m2)/len(p):.3f}")
        # Show parcel all cols
        print(f"  Parcel all cols: {list(p.columns)}")

    # ---- Winchester: Map+Block+Lot vs PROP_ID ----
    print("\n=== Winchester ===")
    p, c = load('winchester', gdbs)
    if p is not None:
        print(f"  Parcel ParcelID sample: {list(p['ParcelID'].head(5))}")
        print(f"  CAMA PROP_ID sample: {list(c['PROP_ID'].head(5))}")
        # PROP_ID = "001||155||019C|||" → try parsing out Map||Block||Lot
        c2 = c.copy()
        # Extract Map, Block, Lot from PROP_ID
        c2['prop_parts'] = c2['PROP_ID'].str.split(r'\|\|')
        c2['prop_map'] = c2['prop_parts'].apply(lambda x: x[0].strip() if len(x) > 0 else '')
        c2['prop_block'] = c2['prop_parts'].apply(lambda x: x[1].strip() if len(x) > 1 else '')
        c2['prop_lot'] = c2['prop_parts'].apply(lambda x: x[2].strip() if len(x) > 2 else '')
        c2['prop_key'] = c2['prop_map'] + ' ' + c2['prop_block'] + ' ' + c2['prop_lot']
        print(f"  CAMA prop_key sample: {list(c2['prop_key'].head(5))}")
        # Parcel has ParcelID = "110 001 002+2A" (space separated, + for suffix)
        p2 = p.copy()
        p2['parcel_base'] = p2['ParcelID'].astype(str).str.split('+').str[0].str.strip()
        print(f"  Parcel parcel_base sample: {list(p2['parcel_base'].head(5))}")
        m = pd.merge(p2[['parcel_base']], c2[['prop_key']], left_on='parcel_base', right_on='prop_key', how='inner')
        print(f"  ParcelID(base)↔prop_key: {len(m)}/{len(p)} = {len(m)/len(p):.3f}")
        # Also try D_GIS_PROP which is the same as ParcelID
        if 'D_GIS_PROP' in p.columns:
            p2['d_gis_base'] = p2['D_GIS_PROP'].astype(str).str.split('+').str[0].str.strip()
            m2 = pd.merge(p2[['d_gis_base']], c2[['prop_key']], left_on='d_gis_base', right_on='prop_key', how='inner')
            print(f"  D_GIS_PROP(base)↔prop_key: {len(m2)}/{len(p)} = {len(m2)/len(p):.3f}")

if __name__ == '__main__':
    main()
