"""
Investigation script to find correct join keys for each Connecticut town.
Outputs results to agent/join_results.json.
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

def try_join(parcel_df, cama_df, parcel_key, cama_key, as_number=False):
    """Try a join and return (count, parcel_count, ratio)."""
    if parcel_key not in parcel_df.columns or cama_key not in cama_df.columns:
        return None
    try:
        p = parcel_df[[parcel_key]].copy()
        c = cama_df[[cama_key]].copy()
        if as_number:
            p[parcel_key] = pd.to_numeric(p[parcel_key], errors='coerce')
            c[cama_key] = pd.to_numeric(c[cama_key], errors='coerce')
            p = p.dropna(subset=[parcel_key])
            c = c.dropna(subset=[cama_key])
        else:
            p[parcel_key] = p[parcel_key].astype(str)
            c[cama_key] = c[cama_key].astype(str)
        merged = pd.merge(p, c, left_on=parcel_key, right_on=cama_key, how='inner')
        n_merged = len(merged)
        n_parcel = len(p)
        n_cama = len(c)
        ratio = n_merged / n_parcel if n_parcel > 0 else 0
        return {'merged': n_merged, 'parcel': n_parcel, 'cama': n_cama, 'ratio': ratio}
    except Exception as e:
        return None

def make_compound_key(df, col_names, sep='-'):
    """Create a compound key column from multiple columns."""
    available = [c for c in col_names if c in df.columns]
    if len(available) < 2:
        return None, None
    key_name = '_'.join(available) + '_compound'
    df[key_name] = df[available].apply(lambda row: sep.join(str(v) for v in row), axis=1)
    return key_name, available

def investigate_town(gdb_path, town_layer_info, towns_df):
    town_name = town_layer_info.town_name
    parcel_layer = town_layer_info.parcels_layer_name
    cama_layer = town_layer_info.cama_layer_name

    try:
        parcel_df = gpd.read_file(gdb_path, layer=parcel_layer)
        cama_df = gpd.read_file(gdb_path, layer=cama_layer)
    except Exception as e:
        return {'town': town_name, 'error': str(e), 'parcel_cols': [], 'cama_cols': [], 'attempts': []}

    # Normalize CAMA column names (same as town_join.py)
    def camel_to_capital_snake(name):
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', name)
    cama_df.columns = [col.replace(' ', '_') for col in cama_df.columns]
    cama_df.columns = [camel_to_capital_snake(col) for col in cama_df.columns]

    parcel_cols = list(parcel_df.columns)
    cama_cols = list(cama_df.columns)

    # Look up metadata join keys
    town_row = towns_df[towns_df['Town'].str.lower() == town_name.lower()]
    meta_parcel_key = None
    meta_cama_key = None
    if not town_row.empty:
        meta_parcel_key = str(town_row['Link_field_for_Parcels'].iloc[0]).strip()
        meta_cama_key = str(town_row['Link_Field_for_CAMA'].iloc[0]).strip()

    # Candidate parcel keys
    parcel_candidates = ['Link', 'Parcel_ID', 'PARCELID', 'UNQ_CARD', 'REALESTATE',
                         'GIS_PIN', 'Unique_ID', 'UNIQUE_ID', 'pid', 'PID', 'LINK',
                         'FILECODE', 'MAP_BK_LOT', 'CAMALINK', 'Parcel_Num', 'PROPERTY_ID']
    if meta_parcel_key and meta_parcel_key not in ('nan', 'None', '?', 'Unknown', '.', 'N/A'):
        parcel_candidates = [meta_parcel_key] + parcel_candidates

    # Candidate CAMA keys
    cama_candidates = ['Parcel_ID', 'Parcel_ID_', 'PID', 'Link', 'GIS_Tag', 'GIS_Tag_',
                       'GIS_ID', 'Account_Number', 'Map', 'Unique_ID', 'UNIQUE_ID',
                       'Acct_Num', 'AccountNumber', 'Account_Num', 'GIS_link',
                       'AV_PID', 'Property_ID', 'REM_PIN', 'REM_PID', 'REM_ACCT_NUM',
                       'GISFullNumber', 'uid', 'UID', 'PROP', 'ACCTNUM', 'ParID', 'pid',
                       'GIS_Tag', 'Parcel_ID', 'Unique_id']
    if meta_cama_key and meta_cama_key not in ('nan', 'None', '?', 'Unknown', '.', 'N/A'):
        cama_candidates = [meta_cama_key] + cama_candidates

    attempts = []
    best = None

    for pk in parcel_candidates:
        if pk not in parcel_df.columns:
            continue
        for ck in cama_candidates:
            if ck not in cama_df.columns:
                continue
            for as_num in [False, True]:
                result = try_join(parcel_df, cama_df, pk, ck, as_number=as_num)
                if result and result['merged'] > 0:
                    entry = {
                        'parcel_key': pk, 'cama_key': ck,
                        'as_number': as_num, **result
                    }
                    attempts.append(entry)
                    if best is None or result['ratio'] > best['ratio']:
                        best = entry
                    # If good enough, record and move on to next parcel key
                    if result['ratio'] > 0.9:
                        break
            if best and best['ratio'] > 0.9:
                break
        if best and best['ratio'] > 0.9:
            break

    # Sort attempts by ratio
    attempts.sort(key=lambda x: -x['ratio'])

    return {
        'town': town_name,
        'parcel_layer': parcel_layer,
        'cama_layer': cama_layer,
        'parcel_count': len(parcel_df),
        'cama_count': len(cama_df),
        'parcel_cols': parcel_cols,
        'cama_cols': cama_cols,
        'meta_parcel_key': meta_parcel_key,
        'meta_cama_key': meta_cama_key,
        'best': best,
        'attempts': attempts[:10],  # top 10
    }

def main():
    towns_df = read_towns_df(METADATA_PATH)
    gdbs = list_cog_gdbs(COG_DIR)

    all_results = {}

    for cog_name, gdb_path in gdbs:
        print(f"\n=== COG: {cog_name} ===")
        town_layers = gdb_to_town_layers(gdb_path)
        for tl in town_layers:
            if tl.town_name is None:
                print(f"  Skipping unknown town: CAMA={tl.cama_layer_name} Parcel={tl.parcels_layer_name}")
                continue
            print(f"  Investigating: {tl.town_name} ... ", end='', flush=True)
            result = investigate_town(gdb_path, tl, towns_df)
            all_results[tl.town_name.lower()] = result
            best = result.get('best')
            if best:
                flag = '✓' if best['ratio'] > 0.5 else ('~' if best['ratio'] > 0.05 else '✗')
                print(f"{flag} best={best['parcel_key']}↔{best['cama_key']} ratio={best['ratio']:.2f} ({best['merged']}/{best['parcel']})")
            else:
                print("✗ no join found")

    output_path = os.path.join(os.path.dirname(__file__), 'join_results.json')
    with open(output_path, 'w') as f:
        json.dump(all_results, f, indent=2)
    print(f"\nResults written to {output_path}")

    # Summary
    print("\n=== SUMMARY ===")
    total = len(all_results)
    good = sum(1 for r in all_results.values() if r.get('best') and r['best']['ratio'] > 0.5)
    weak = sum(1 for r in all_results.values() if r.get('best') and 0.05 < r['best']['ratio'] <= 0.5)
    none_ = sum(1 for r in all_results.values() if not r.get('best') or r['best']['ratio'] <= 0.05)
    print(f"Total towns: {total}")
    print(f"Good joins (>50%): {good}")
    print(f"Weak joins (5-50%): {weak}")
    print(f"No/poor joins (<5%): {none_}")

    print("\n=== TOWNS NEEDING ATTENTION ===")
    for name, r in sorted(all_results.items()):
        best = r.get('best')
        if not best or best['ratio'] < 0.5:
            ratio_str = f"{best['ratio']:.2f}" if best else "N/A"
            print(f"  {r['town']}: ratio={ratio_str} | parcel_cols={r['parcel_cols'][:8]} | cama_cols={r['cama_cols'][:8]}")

if __name__ == '__main__':
    main()
