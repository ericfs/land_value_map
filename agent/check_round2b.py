"""Round 2b: Continue from Bridgewater."""

import sys
import os
import re
import geopandas as gpd
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from town_layers import gdb_to_town_layers

COG_DIR = os.path.join(os.path.dirname(__file__), '..', 'inputs', 'Parcel Collection 2024', 'Parcel_By_COG')

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

def try_merge(p, c, pk, ck, transform_p=None, transform_c=None):
    p2 = p.copy()
    c2 = c.copy()
    if transform_p:
        p2[pk] = transform_p(p2[pk])
    else:
        p2[pk] = p2[pk].astype(str)
    if transform_c:
        c2[ck] = transform_c(c2[ck])
    else:
        c2[ck] = c2[ck].astype(str)
    m = pd.merge(p2[[pk]], c2[[ck]], left_on=pk, right_on=ck, how='inner')
    ratio = len(m) / len(p) if len(p) > 0 else 0
    print(f"  {pk}↔{ck}: {len(m)}/{len(p)} = {ratio:.3f}")
    return ratio

def main():
    gdbs = list_cog_gdbs(COG_DIR)

    # ---- Bridgewater: MBL = "33 10" vs Map=33, Block=10 ----
    print("\n=== Bridgewater ===")
    p, c = load('bridgewater', gdbs)
    if p is not None:
        # MBL = "33 10" (Map Block with space), try vs Map-Block compound from CAMA
        p2 = p.copy()
        c2 = c.copy()
        # Normalize MBL: strip and replace double spaces
        p2['mbl_norm'] = p2['MBL'].astype(str).str.strip().str.replace(r'\s+', ' ', regex=True)
        # CAMA Map+Block compound
        c2['map_block'] = c2['Map'].astype(str).str.strip() + ' ' + c2['Block'].astype(str).str.strip()
        print(f"  Parcel MBL_norm: {list(p2['mbl_norm'].head(10))}")
        print(f"  CAMA Map+Block: {list(c2['map_block'].head(5))}")
        m = pd.merge(p2[['mbl_norm']], c2[['map_block']], left_on='mbl_norm', right_on='map_block', how='inner')
        print(f"  MBL_norm↔Map Block: {len(m)}/{len(p)} = {len(m)/len(p):.3f}")
        # Try Parcel_ID from CAMA
        c2['parcel_id_str'] = c2['Parcel_ID'].astype(str).str.strip()
        for pkey in ['PARNO', 'PIN']:
            if pkey in p.columns:
                m = pd.merge(p[[pkey]].astype(str).apply(lambda x: x.str.strip()), c2[['parcel_id_str']], left_on=pkey, right_on='parcel_id_str')
                print(f"  {pkey}↔Parcel_ID: {len(m)}/{len(p)} = {len(m)/len(p):.3f}")
        print(f"  CAMA Account_Number (unique): {sorted(c['Account_Number'].astype(str).unique())[:10]}")

    # ---- Deep River ----
    print("\n=== Deep River ===")
    p, c = load('deep river', gdbs)
    if p is not None:
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
        print(f"  Sample parcel keys: {list(p2['key'].head(10))}")
        print(f"  Sample CAMA keys: {list(c2['key'].head(10))}")

    # ---- Durham ----
    print("\n=== Durham ===")
    p, c = load('durham', gdbs)
    if p is not None:
        p2 = p.copy()
        c2 = c.copy()
        # Try Map+Lot numeric and string
        p2['map_num'] = pd.to_numeric(p2['Map'], errors='coerce')
        c2['map_num'] = pd.to_numeric(c2['Map'], errors='coerce')
        p2['lot_num'] = pd.to_numeric(p2['Lot'], errors='coerce')
        c2['lot_num'] = pd.to_numeric(c2['Lot'], errors='coerce')
        print(f"  Parcel Map/Lot types: Map={p['Map'].dtype}, Lot={p['Lot'].dtype}")
        print(f"  CAMA Map/Lot types: Map={c['Map'].dtype}, Lot={c['Lot'].dtype}")
        print(f"  Parcel Map,Lot sample: {list(zip(p['Map'][:5], p['Lot'][:5]))}")
        print(f"  CAMA Map,Lot sample: {list(zip(c['Map'][:10], c['Lot'][:10]))}")
        p2 = p2.dropna(subset=['map_num'])
        c2 = c2.dropna(subset=['map_num'])
        p2['key'] = p2['map_num'].astype(int).astype(str) + '-' + p2['Lot'].astype(str)
        c2['key'] = c2['map_num'].astype(int).astype(str) + '-' + c2['Lot'].astype(str)
        m = pd.merge(p2[['key']], c2[['key']], on='key', how='inner')
        print(f"  Map(int)+Lot_str: {len(m)}/{len(p)} = {len(m)/len(p):.3f}")
        print(f"  Sample parcel keys: {list(p2['key'].head(5))}")
        print(f"  Sample CAMA keys: {list(c2['key'].head(5))}")

    # ---- East Haddam ----
    print("\n=== East Haddam ===")
    p, c = load('east haddam', gdbs)
    if p is not None:
        # Full_Num = "083-004", CAMA link = "22280-083-004"
        c2 = c.copy()
        c2['link_stripped'] = c2['link'].astype(str).str.replace(r'^\d{5}-', '', regex=True)
        print(f"  Parcel Full_Num samples: {list(p['Full_Num'].head(5))}")
        print(f"  CAMA link_stripped samples: {list(c2['link_stripped'].head(5))}")
        m = pd.merge(p[['Full_Num']].astype(str), c2[['link_stripped']], left_on='Full_Num', right_on='link_stripped', how='inner')
        print(f"  Full_Num↔link.strip_prefix: {len(m)}/{len(p)} = {len(m)/len(p):.3f}")

    # ---- Groton ----
    print("\n=== Groton ===")
    p, c = load('groton', gdbs)
    if p is not None:
        # Link = "260714436344" (big number), PID = float huge
        print(f"  Parcel Link types: {p['Link'].dtype}, sample: {list(p['Link'][:5])}")
        print(f"  CAMA PID type: {c['PID'].dtype}, sample: {list(c['PID'][:5])}")
        print(f"  CAMA all cols: {list(c.columns)}")
        # All CAMA cols
        print(c.head(3).to_string(index=False))
        # Try Link as number vs PID/Account_Number
        p2 = p.copy()
        c2 = c.copy()
        p2['link_num'] = pd.to_numeric(p2['Link'], errors='coerce')
        c2['pid_num'] = pd.to_numeric(c2['PID'], errors='coerce')
        c2['acct_num'] = pd.to_numeric(c2['Account_Number'], errors='coerce')
        p2 = p2.dropna(subset=['link_num'])
        c2_pid = c2.dropna(subset=['pid_num'])
        c2_acct = c2.dropna(subset=['acct_num'])
        m = pd.merge(p2[['link_num']], c2_pid[['pid_num']], left_on='link_num', right_on='pid_num', how='inner')
        print(f"  Link(num)↔PID(num): {len(m)}/{len(p)} = {len(m)/len(p):.3f}")
        m2 = pd.merge(p2[['link_num']], c2_acct[['acct_num']], left_on='link_num', right_on='acct_num', how='inner')
        print(f"  Link(num)↔Account_Number(num): {len(m2)}/{len(p)} = {len(m2)/len(p):.3f}")
        # Check all parcel cols
        print(f"  All parcel cols: {list(p.columns)}")

    # ---- Hartford ----
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
        # Also try stripping .0
        c2b = c.copy()
        c2b['gistag_str'] = c2b['GISTag'].astype(str).str.replace(r'\.0$', '', regex=True)
        m3 = pd.merge(p[['GIS_PIN']].astype(str), c2b[['gistag_str']], left_on='GIS_PIN', right_on='gistag_str', how='inner')
        print(f"  GIS_PIN↔GISTag(strip .0): {len(m3)}/{len(p)} = {len(m3)/len(p):.3f}")

    # ---- Lebanon ----
    print("\n=== Lebanon ===")
    p, c = load('lebanon', gdbs)
    if p is not None:
        print(f"  Parcel all cols: {list(p.columns)}")
        print(f"  Parcel Map/Lot types: {p['Map'].dtype}/{p['Lot'].dtype}")
        print(f"  CAMA Map/Lot types: {c['Map'].dtype}/{c['Lot'].dtype}")
        print(f"  Parcel Map,Lot sample (10): {list(zip(p['Map'][:10], p['Lot'][:10]))}")
        print(f"  CAMA Map,Lot sample (10): {list(zip(c['Map'][:10], c['Lot'][:10]))}")
        # Map-Lot compound
        p2 = p.copy()
        c2 = c.copy()
        p2['map_num'] = pd.to_numeric(p2['Map'], errors='coerce')
        c2['map_num'] = pd.to_numeric(c2['Map'], errors='coerce')
        p2['lot_str'] = p2['Lot'].astype(str).str.strip()
        c2['lot_str'] = c2['Lot'].astype(str).str.strip()
        p2['key'] = p2['map_num'].fillna(-1).astype(int).astype(str) + '-' + p2['lot_str']
        c2['key'] = c2['map_num'].fillna(-1).astype(int).astype(str) + '-' + c2['lot_str']
        m = pd.merge(p2[['key']], c2[['key']], on='key', how='inner')
        print(f"  Map(int)+Lot↔same: {len(m)}/{len(p)} = {len(m)/len(p):.3f}")
        print(f"  Sample parcel keys: {list(p2['key'][:5])}")
        print(f"  Sample CAMA keys: {list(c2['key'][:5])}")

    # ---- Ledyard ----
    print("\n=== Ledyard ===")
    p, c = load('ledyard', gdbs)
    if p is not None:
        # Link = "144-1070-3", CAMA Map=2, Block=2420, Lot=23, GIS_Tag=176
        # GIS_Tag is sequential. PID also sequential.
        # Link could be Map-Block-Lot. CAMA: Map=2, Block=2420, Lot=23
        # "144-1070-3" = Map=144, Block=1070, Lot=3?
        p2 = p.copy()
        c2 = c.copy()
        # Try Link vs Map-Block-Lot from CAMA
        c2['key'] = c2['Map'].astype(str).str.strip() + '-' + c2['Block'].astype(str).str.strip() + '-' + c2['Lot'].astype(str).str.strip()
        print(f"  Parcel Link: {list(p['Link'].head(10))}")
        print(f"  CAMA Map-Block-Lot: {list(c2['key'].head(10))}")
        p2['link_strip'] = p2['Link'].astype(str).str.strip()
        m = pd.merge(p2[['link_strip']], c2[['key']], left_on='link_strip', right_on='key', how='inner')
        print(f"  Link↔Map-Block-Lot: {len(m)}/{len(p)} = {len(m)/len(p):.3f}")
        # Try with integer conversion
        def parse_ledyard_link(s):
            parts = str(s).strip().split('-')
            return '-'.join(str(int(x)) if x.strip().isdigit() else x.strip() for x in parts)
        p2['link_int'] = p2['Link'].apply(parse_ledyard_link)
        c2['key_int'] = c2['Map'].apply(lambda x: str(int(float(x))) if pd.notna(x) else '') + '-' + \
                        c2['Block'].apply(lambda x: str(int(float(x))) if pd.notna(x) else '') + '-' + \
                        c2['Lot'].apply(lambda x: str(int(float(x))) if pd.notna(x) and str(x) != 'nan' else str(x))
        print(f"  Parcel link_int: {list(p2['link_int'].head(10))}")
        print(f"  CAMA key_int: {list(c2['key_int'].head(10))}")
        m2 = pd.merge(p2[['link_int']], c2[['key_int']], left_on='link_int', right_on='key_int', how='inner')
        print(f"  Link(int)↔Map(int)-Block(int)-Lot: {len(m2)}/{len(p)} = {len(m2)/len(p):.3f}")

    # ---- Middletown ----
    print("\n=== Middletown ===")
    p, c = load('middletown', gdbs)
    if p is not None:
        # Parcel_ID = "15-0409" = Map(2digit)-Lot(4digit with leading zeros)
        # CAMA: Map=24,Lot=102,link="47360-1"
        print(f"  Parcel Parcel_ID: {list(p['Parcel_ID'].head(10))}")
        print(f"  Parcel Map,Lot: {list(zip(p['Map'].head(5), p['Lot'].head(5)))}")
        print(f"  CAMA link,GIS_Tag,Map,Lot: {list(zip(c['link'].head(5), c['GIS_Tag'].head(5), c['Map'].head(5), c['Lot'].head(5)))}")
        # Try: Parcel Map+Lot as number vs CAMA Map+Lot as number
        p2 = p.copy()
        c2 = c.copy()
        p2['map_num'] = pd.to_numeric(p2['Map'], errors='coerce')
        p2['lot_num'] = pd.to_numeric(p2['Lot'], errors='coerce')
        c2['map_num'] = pd.to_numeric(c2['Map'], errors='coerce')
        c2['lot_num'] = pd.to_numeric(c2['Lot'], errors='coerce')
        p2 = p2.dropna(subset=['map_num','lot_num'])
        c2 = c2.dropna(subset=['map_num','lot_num'])
        p2['key'] = p2['map_num'].astype(int).astype(str) + '-' + p2['lot_num'].astype(int).astype(str)
        c2['key'] = c2['map_num'].astype(int).astype(str) + '-' + c2['lot_num'].astype(int).astype(str)
        m = pd.merge(p2[['key']], c2[['key']], on='key', how='inner')
        print(f"  Map(int)+Lot(int)↔same: {len(m)}/{len(p)} = {len(m)/len(p):.3f}")
        print(f"  Sample parcel keys: {list(p2['key'].head(5))}")
        print(f"  Sample CAMA keys: {list(c2['key'].head(5))}")
        # Also try Parcel_ID directly (format "15-0409") vs CAMA GIS_Tag
        for ck in ['GIS_Tag', 'link', 'PID']:
            m = pd.merge(p[['Parcel_ID']].astype(str), c[[ck]].astype(str), left_on='Parcel_ID', right_on=ck, how='inner')
            print(f"  Parcel_ID↔{ck}: {len(m)}/{len(p)} = {len(m)/len(p):.3f}")

    # ---- Montville ----
    print("\n=== Montville ===")
    p, c = load('montville', gdbs)
    if p is not None:
        # Full_Num = "001-008-00A", CAMA GIS_Tag = "016/003-001", Map = "016/003/001"
        # Full_Num format: Map(3)-Block(3)-Lot(3letters)
        # GIS_Tag format: Map(3)/Block(3)-Lot(3)
        # Try normalizing: replace / with -
        p2 = p.copy()
        c2 = c.copy()
        c2['gis_norm'] = c2['GIS_Tag'].astype(str).str.replace('/', '-')
        print(f"  Full_Num samples: {list(p['Full_Num'].head(10))}")
        print(f"  CAMA GIS_Tag_norm samples: {list(c2['gis_norm'].head(10))}")
        m = pd.merge(p2[['Full_Num']].astype(str), c2[['gis_norm']], left_on='Full_Num', right_on='gis_norm', how='inner')
        print(f"  Full_Num↔GIS_Tag(/ to -): {len(m)}/{len(p)} = {len(m)/len(p):.3f}")
        # Try: CAMA PID
        print(f"  CAMA PID samples: {list(c['PID'].head(5))}")
        print(f"  Parcel Full_Num vs CAMA PID?")

    # ---- New London ----
    print("\n=== New London ===")
    p, c = load('new london', gdbs)
    if p is not None:
        print(f"  Parcel Link: {list(p['Link'].head(10))}")
        # Link = "E01-321-4" = GridRef-Block-Lot?
        # CAMA Map="F27", Block=11, Lot=13
        # "E01-321-4": GridRef=E01, Block=321, Lot=4
        # CAMA Map="F27" is like "LetterNumber", Block=11, Lot=13
        # Try concatenating CAMA Map+Block+Lot
        c2 = c.copy()
        c2['key'] = c2['Map'].astype(str).str.strip() + '-' + c2['Block'].astype(str).str.strip() + '-' + c2['Lot'].astype(str).str.strip()
        print(f"  CAMA Map-Block-Lot key: {list(c2['key'].head(10))}")
        p2 = p.copy()
        p2['link_strip'] = p2['Link'].astype(str).str.strip()
        m = pd.merge(p2[['link_strip']], c2[['key']], left_on='link_strip', right_on='key', how='inner')
        print(f"  Link↔Map-Block-Lot: {len(m)}/{len(p)} = {len(m)/len(p):.3f}")
        # Parcel_ID in CAMA
        print(f"  CAMA Parcel_ID samples: {list(c['Parcel_ID'].head(10))}")
        # Try link (CAMA has Link) as is
        if 'Link' in c.columns or 'link' in c.columns:
            ck = 'Link' if 'Link' in c.columns else 'link'
            m2 = pd.merge(p[['Link']].astype(str), c[[ck]].astype(str), left_on='Link', right_on=ck, how='inner')
            print(f"  Link↔CAMA {ck}: {len(m2)}/{len(p)} = {len(m2)/len(p):.3f}")
        # Try CAMA GIS_Tag
        print(f"  CAMA all cols: {list(c.columns)}")
        # CAMA has Parcel_ID = sequential int. Check if that matches anything.
        # Try numeric Link vs CAMA PID
        p2['link_num'] = pd.to_numeric(p2['link_strip'].str.extract(r'(\d+)', expand=False), errors='coerce')
        print(f"  Parcel link_num extract: {list(p2['link_num'].head(5))}")

    # ---- Old Lyme ----
    print("\n=== Old Lyme ===")
    p, c = load('old lyme', gdbs)
    if p is not None:
        c2 = c.copy()
        c2['link_stripped'] = c2['link'].astype(str).str.replace(r'^\d{5}-', '', regex=True)
        print(f"  Parcel Link: {list(p['Link'].head(10))}")
        print(f"  CAMA link_stripped: {list(c2['link_stripped'].head(10))}")
        m = pd.merge(p[['Link']].astype(str), c2[['link_stripped']], left_on='Link', right_on='link_stripped', how='inner')
        print(f"  Link↔link.strip_prefix: {len(m)}/{len(p)} = {len(m)/len(p):.3f}")
        # Also try Map+Lot from CAMA vs Link parsed
        p2 = p.copy()
        c2b = c.copy()
        p2['link_strip'] = p2['Link'].astype(str).str.strip()
        c2b['map_lot'] = c2b['Map'].astype(str).str.strip() + '-' + c2b['Lot'].astype(str).str.strip().apply(lambda x: str(int(float(x))) if x not in ('nan','None') else x)
        print(f"  CAMA Map-Lot: {list(c2b['map_lot'].head(5))}")
        m2 = pd.merge(p2[['link_strip']], c2b[['map_lot']], left_on='link_strip', right_on='map_lot', how='inner')
        print(f"  Link↔Map-Lot: {len(m2)}/{len(p)} = {len(m2)/len(p):.3f}")

    # ---- Oxford ----
    print("\n=== Oxford ===")
    p, c = load('oxford', gdbs)
    if p is not None:
        c2 = c.copy()
        c2['map_norm'] = c2['Map'].astype(str).str.strip().str.replace(r'\s+', '-', regex=True)
        print(f"  Parcel Link: {list(p['Link'].head(10))}")
        print(f"  CAMA map_norm: {list(c2['map_norm'].head(10))}")
        m = pd.merge(p[['Link']].astype(str).apply(lambda x: x.str.strip()), c2[['map_norm']], left_on='Link', right_on='map_norm', how='inner')
        print(f"  Link↔Map(spaces->hyphens): {len(m)}/{len(p)} = {len(m)/len(p):.3f}")

    # ---- Sherman ----
    print("\n=== Sherman ===")
    p, c = load('sherman', gdbs)
    if p is not None:
        p2 = p.copy()
        p2['pid_prefix'] = p2['JWS_PID'].astype(str).str[:7]
        print(f"  JWS_PID samples: {list(p['JWS_PID'].head(5))}")
        print(f"  pid_prefix samples: {list(p2['pid_prefix'].head(5))}")
        print(f"  CAMA Gis_Full_Number samples: {list(c['Gis_Full_Number'].head(5))}")
        m = pd.merge(p2[['pid_prefix']], c[['Gis_Full_Number']].astype(str), left_on='pid_prefix', right_on='Gis_Full_Number', how='inner')
        print(f"  JWS_PID[:7]↔Gis_Full_Number: {len(m)}/{len(p)} = {len(m)/len(p):.3f}")
        # Also try full JWS_PID vs Cama_Full_Number
        m2 = pd.merge(p[['JWS_PID']].astype(str), c[['Cama_Full_Number']].astype(str), left_on='JWS_PID', right_on='Cama_Full_Number', how='inner')
        print(f"  JWS_PID↔Cama_Full_Number: {len(m2)}/{len(p)} = {len(m2)/len(p):.3f}")

    # ---- Sprague ----
    print("\n=== Sprague ===")
    p, c = load('sprague', gdbs)
    if p is not None:
        print(f"  All parcel cols: {list(p.columns)}")
        print(f"  Parcel sample:")
        print(p.drop(columns=['geometry'], errors='ignore').head(5).to_string(index=False))
        print(f"  CAMA all cols: {list(c.columns)}")
        print(f"  CAMA sample:")
        print(c.head(5).to_string(index=False))

    # ---- Thomaston ----
    print("\n=== Thomaston ===")
    p, c = load('thomaston', gdbs)
    if p is not None:
        print(f"  All parcel cols: {list(p.columns)}")
        print(f"  Parcel sample:")
        print(p.drop(columns=['geometry'], errors='ignore').head(5).to_string(index=False))
        print(f"  CAMA all cols: {list(c.columns)}")
        print(f"  CAMA sample (more rows, more cols):")
        print(c.head(10).to_string(index=False))

    # ---- Wethersfield ----
    print("\n=== Wethersfield ===")
    p, c = load('wethersfield', gdbs)
    if p is not None:
        print(f"  All parcel cols: {list(p.columns)}")
        print(f"  Parcel GISID samples: {list(p['GISID'].head(10))}")
        print(f"  CAMA GIS_Tag: {list(c['GIS_Tag'].head(10))}")
        print(f"  CAMA PID: {list(c['PID'].head(5))}")
        # numeric join
        p2 = p.copy()
        c2 = c.copy()
        p2['gisid_num'] = pd.to_numeric(p2['GISID'], errors='coerce')
        c2['gistag_num'] = pd.to_numeric(c2['GIS_Tag'], errors='coerce')
        m = pd.merge(p2.dropna(subset=['gisid_num'])[['gisid_num']],
                     c2.dropna(subset=['gistag_num'])[['gistag_num']],
                     left_on='gisid_num', right_on='gistag_num', how='inner')
        print(f"  GISID(num)↔GIS_Tag(num): {len(m)}/{len(p)} = {len(m)/len(p):.3f}")

    # ---- Winchester ----
    print("\n=== Winchester ===")
    p, c = load('winchester', gdbs)
    if p is not None:
        p2 = p.copy()
        c2 = c.copy()
        # PROP_ID = "001||155||019C|||" → Map||Block||Lot
        c2['prop_parts'] = c2['PROP_ID'].astype(str).str.split(r'\|\|')
        c2['prop_map'] = c2['prop_parts'].apply(lambda x: x[0].strip() if len(x) > 0 else '')
        c2['prop_block'] = c2['prop_parts'].apply(lambda x: x[1].strip() if len(x) > 1 else '')
        c2['prop_lot'] = c2['prop_parts'].apply(lambda x: x[2].strip() if len(x) > 2 else '')
        # parcel: Map="110", Block="001", Lot="002A"
        # key from PROP_ID: "001 155 019C" → no, the prop_lot needs to handle trailing |||
        c2['prop_lot_clean'] = c2['prop_lot'].str.replace(r'\|+$', '', regex=True).str.strip()
        c2['prop_key'] = c2['prop_map'] + ' ' + c2['prop_block'] + ' ' + c2['prop_lot_clean']
        # key from parcel
        p2['p_key'] = p2['Map'].astype(str).str.strip() + ' ' + p2['Block'].astype(str).str.strip() + ' ' + p2['Lot'].astype(str).str.strip()
        print(f"  CAMA prop_key samples: {list(c2['prop_key'].head(5))}")
        print(f"  Parcel p_key samples: {list(p2['p_key'].head(5))}")
        m = pd.merge(p2[['p_key']], c2[['prop_key']], left_on='p_key', right_on='prop_key', how='inner')
        print(f"  Map Block Lot↔PROP_ID parsed: {len(m)}/{len(p)} = {len(m)/len(p):.3f}")
        # Also show CAMA cols
        print(f"  CAMA all cols: {list(c.columns)}")

if __name__ == '__main__':
    main()
