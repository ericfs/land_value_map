"""Verify town joins with ratio > 1.0 by checking area, address, and map rendering.

Usage:
    python3 agent/verify_joins.py                    # all unverified towns
    python3 agent/verify_joins.py --town hartford    # single town
    python3 agent/verify_joins.py --recheck          # re-verify already-done towns

Can also be imported and used interactively:
    from verify_joins import load_and_verify_town, get_towns_to_verify
"""

import gc
import json
import os
import re
import sys
import argparse

import geopandas as gpd
import numpy as np
import pandas as pd

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import contextily as cx

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from town_layers import gdb_to_town_layers
from town_metadata import read_towns_df
from town_join import (
    read_town_layers, apply_transform, inner_join, drop_rows,
    JOIN_KEYS, add_column_suffix, normalize_column_names,
)
from town_name import normalize_town_name
from value_per_acre import compute_value_per_acre, filter_value_per_acre, compute_capped_value_per_acre

COG_DIR = os.path.join(os.path.dirname(__file__), '..', 'inputs', 'Parcel Collection 2024', 'Parcel_By_COG')
METADATA_PATH = os.path.join(os.path.dirname(__file__), '..', 'inputs', 'Metadata_2024.csv')
JOIN_KEYS_PATH = os.path.join(os.path.dirname(__file__), 'join_keys.json')
MAP_DIR = os.path.join(os.path.dirname(__file__), 'verify_maps')


def list_cog_gdbs(cog_dir):
    items = os.listdir(cog_dir)
    folders = [i for i in items if os.path.isdir(os.path.join(cog_dir, i))]
    return [(item, os.path.join(cog_dir, item, f'{item}.gdb')) for item in sorted(folders)]


def find_town_in_gdbs(town_name_lower, gdbs):
    for cog_name, gdb_path in gdbs:
        tls = gdb_to_town_layers(gdb_path)
        for tl in tls:
            if tl.town_name and tl.town_name.lower() == town_name_lower:
                return gdb_path, tl
    return None, None


def load_and_join(town_name, gdbs, towns_df):
    """Load parcel + CAMA data and perform the join. Returns (parcel_gdf, cama_gdf, merged_gdf)."""
    norm = normalize_town_name(town_name)
    entry = JOIN_KEYS.get(norm)
    if not entry or entry.get('no_cama_layer') or entry.get('no_working_join'):
        return None, None, None

    gdb_path, tl = find_town_in_gdbs(town_name.lower(), gdbs)
    if not gdb_path:
        print(f"  Could not find {town_name} in any GDB")
        return None, None, None

    parcel_gdf, cama_gdf, town_info = read_town_layers(gdb_path, tl, towns_df)
    parcel_gdf = drop_rows(parcel_gdf, town_name)

    # Perform join using the same logic as town_join._join_from_entry
    as_number = entry.get('as_number', False)
    parcel_key, cama_key = apply_transform(parcel_gdf, cama_gdf, entry)
    merged = inner_join(parcel_gdf, cama_gdf, parcel_key, cama_key, town_name, as_number=as_number)

    if merged.empty:
        print(f"  Join produced empty result for {town_name}")
        return parcel_gdf, cama_gdf, None

    # Apply column remapping (same as cog.py)
    if 'value_col' in entry:
        vc = entry['value_col']
        for candidate in [vc, f'{vc}_x', f'{vc}_y']:
            if candidate in merged.columns:
                merged = merged.rename(columns={candidate: 'Appraised_Total'})
                break
        if 'value_multiplier' in entry:
            merged['Appraised_Total'] = pd.to_numeric(
                merged['Appraised_Total'], errors='coerce') * entry['value_multiplier']
    if 'acres_col' in entry:
        ac = entry['acres_col']
        for candidate in [ac, f'{ac}_x', f'{ac}_y']:
            if candidate in merged.columns:
                merged = merged.rename(columns={candidate: 'Land_Acres'})
                break
    if 'value_cols_sum' in entry:
        merged['Appraised_Total'] = sum(
            pd.to_numeric(merged[c], errors='coerce').fillna(0)
            for c in entry['value_cols_sum'] if c in merged.columns
        )
    if 'acres_cols_sum' in entry:
        merged['Land_Acres'] = sum(
            pd.to_numeric(merged[c], errors='coerce').fillna(0)
            for c in entry['acres_cols_sum'] if c in merged.columns
        )
    cols = merged.columns
    if 'Appraised_Total' not in cols and 'Appraised_Total_y' in cols:
        merged = merged.rename(columns={'Appraised_Total_y': 'Appraised_Total'})
    if 'Land_Acres' not in cols and 'Land_Acres_y' in cols:
        merged = merged.rename(columns={'Land_Acres_y': 'Land_Acres'})

    # Convert to GeoDataFrame
    if 'geometry' in merged.columns and not isinstance(merged, gpd.GeoDataFrame):
        merged = gpd.GeoDataFrame(merged, geometry='geometry', crs=parcel_gdf.crs)

    # Compute value per acre
    try:
        compute_value_per_acre(merged)
        merged = filter_value_per_acre(merged)
        compute_capped_value_per_acre(merged)
    except Exception as e:
        print(f"  Warning: value per acre computation failed: {e}")

    return parcel_gdf, cama_gdf, merged


def _detect_area_unit(crs):
    """Return divisor to convert CRS area units to acres."""
    if crs is None:
        return 43560  # assume feet
    try:
        unit = crs.axis_info[0].unit_name.lower()
    except (AttributeError, IndexError):
        unit = ''
    if 'foot' in unit or 'feet' in unit or 'ft' in unit:
        return 43560.0
    elif 'metre' in unit or 'meter' in unit:
        return 4046.86
    else:
        return 43560.0  # default to feet for CT State Plane


def _find_shape_area_col(df):
    """Find the Shape_Area column (may have merge suffix)."""
    for col in ['Shape_Area', 'Shape_Area_x']:
        if col in df.columns:
            return col
    return None


def check_area(merged_df, parcel_crs, ratio):
    """Compare parcel Shape_Area (converted to acres) with CAMA Land_Acres."""
    shape_col = _find_shape_area_col(merged_df)
    if shape_col is None:
        print("  Area check: Shape_Area column not found — SKIPPED")
        return None
    if 'Land_Acres' not in merged_df.columns:
        print("  Area check: Land_Acres column not found — SKIPPED")
        return None

    if ratio > 2.0:
        print(f"  ⚠ Ratio {ratio:.1f} is very high (many-to-one). Area check may be unreliable.")

    divisor = _detect_area_unit(parcel_crs)
    unit_name = "sq ft" if divisor == 43560.0 else "sq m"

    shape_acres = pd.to_numeric(merged_df[shape_col], errors='coerce') / divisor
    land_acres = pd.to_numeric(merged_df['Land_Acres'], errors='coerce')

    valid = (shape_acres > 0) & (land_acres > 0)
    shape_valid = shape_acres[valid]
    land_valid = land_acres[valid]

    if len(shape_valid) == 0:
        print("  Area check: no valid rows with both Shape_Area and Land_Acres > 0")
        return None

    pct_diff = ((shape_valid - land_valid).abs() / land_valid * 100)

    within_5 = (pct_diff <= 5).sum() / len(pct_diff) * 100
    within_20 = (pct_diff <= 20).sum() / len(pct_diff) * 100
    median_diff = pct_diff.median()

    stats = {
        'valid_rows': len(pct_diff),
        'total_rows': len(merged_df),
        'within_5pct': round(within_5, 1),
        'within_20pct': round(within_20, 1),
        'median_pct_diff': round(median_diff, 1),
        'unit': unit_name,
    }

    print(f"\n  AREA COMPARISON ({unit_name} → acres vs Land_Acres)")
    print(f"  Valid rows: {stats['valid_rows']}/{stats['total_rows']}")
    print(f"  Within 5%:  {stats['within_5pct']}%")
    print(f"  Within 20%: {stats['within_20pct']}%")
    print(f"  Median diff: {stats['median_pct_diff']}%")

    # Show 5 worst mismatches
    worst_idx = pct_diff.nlargest(5).index
    print(f"\n  Worst mismatches:")
    print(f"  {'Shape_Acres':>12}  {'Land_Acres':>12}  {'Diff%':>8}")
    for idx in worst_idx:
        print(f"  {shape_valid[idx]:12.3f}  {land_valid[idx]:12.3f}  {pct_diff[idx]:7.1f}%")

    return stats


def _normalize_addr(s):
    """Normalize address string for comparison."""
    if pd.isna(s):
        return ''
    return re.sub(r'\s+', ' ', str(s).lower().strip())


def check_address(merged_df):
    """Compare parcel and CAMA address fields."""
    parcel_addr_col = None
    cama_addr_col = None

    if 'Location_Parcels' in merged_df.columns:
        parcel_addr_col = 'Location_Parcels'
    if 'Location_CAMA' in merged_df.columns:
        cama_addr_col = 'Location_CAMA'

    if not parcel_addr_col or not cama_addr_col:
        print(f"  Address check: Missing columns (parcel={parcel_addr_col}, cama={cama_addr_col}) — SKIPPED")
        return None

    parcel_norm = merged_df[parcel_addr_col].apply(_normalize_addr)
    cama_norm = merged_df[cama_addr_col].apply(_normalize_addr)

    # Filter out empty addresses
    both_present = (parcel_norm != '') & (cama_norm != '')
    p_valid = parcel_norm[both_present]
    c_valid = cama_norm[both_present]

    if len(p_valid) == 0:
        print("  Address check: no rows with both addresses present")
        return None

    exact_match = (p_valid == c_valid).sum() / len(p_valid) * 100

    # Fuzzy: check if one contains the other (handles abbreviation differences)
    fuzzy_match = sum(
        (p in c) or (c in p)
        for p, c in zip(p_valid, c_valid)
    ) / len(p_valid) * 100

    stats = {
        'valid_rows': len(p_valid),
        'exact_match_pct': round(exact_match, 1),
        'fuzzy_match_pct': round(fuzzy_match, 1),
    }

    print(f"\n  ADDRESS COMPARISON ({parcel_addr_col} vs {cama_addr_col})")
    print(f"  Valid rows:  {stats['valid_rows']}")
    print(f"  Exact match: {stats['exact_match_pct']}%")
    print(f"  Fuzzy match: {stats['fuzzy_match_pct']}%")

    # Show 10 random samples
    sample_n = min(10, len(p_valid))
    sample_idx = p_valid.sample(sample_n, random_state=42).index
    print(f"\n  Sample addresses (Parcel → CAMA):")
    for idx in sample_idx:
        p = merged_df[parcel_addr_col].iloc[merged_df.index.get_loc(idx)] if idx in merged_df.index else ''
        c = merged_df[cama_addr_col].iloc[merged_df.index.get_loc(idx)] if idx in merged_df.index else ''
        match = "✓" if _normalize_addr(p) == _normalize_addr(c) else "✗"
        print(f"    {match} {str(p)[:40]:40s} → {str(c)[:40]}")

    return stats


def render_map(merged_gdf, town_name, map_dir):
    """Render value per acre map with street basemap. Returns path to saved image."""
    os.makedirs(map_dir, exist_ok=True)
    filepath = os.path.join(map_dir, f'{town_name}.png')

    if 'Appraised_Value_Per_Acre_Capped' not in merged_gdf.columns:
        print(f"  Map: Appraised_Value_Per_Acre_Capped not found — SKIPPED")
        return None

    # Reproject to Web Mercator for contextily
    try:
        plot_gdf = merged_gdf.to_crs(epsg=3857)
    except Exception:
        plot_gdf = merged_gdf

    fig, ax = plt.subplots(1, 1, figsize=(20, 20))
    plot_gdf.plot(column='Appraised_Value_Per_Acre_Capped', ax=ax, legend=True, cmap='plasma')
    ax.set_title(f'Appraised Value Per Acre: {town_name}')
    ax.set_axis_off()

    try:
        cx.add_basemap(ax, crs=plot_gdf.crs, zoom='auto')
    except Exception as e:
        print(f"  Map: basemap failed ({e}), saving without basemap")

    plt.savefig(filepath, bbox_inches='tight', dpi=100)
    plt.close(fig)

    print(f"\n  Map saved to: {filepath}")
    return filepath


def load_and_verify_town(town_name, gdbs, towns_df):
    """Run all three verification checks for a single town.
    Returns (area_stats, address_stats, map_path)."""
    norm = normalize_town_name(town_name)
    entry = JOIN_KEYS.get(norm, {})
    ratio = entry.get('ratio', 0)

    print(f"\n{'='*60}")
    print(f"  {town_name.upper()} (ratio={ratio}, keys: {entry.get('parcel_key','?')}↔{entry.get('cama_key','?')})")
    if entry.get('note'):
        print(f"  Note: {entry['note']}")
    print(f"{'='*60}")

    print(f"\n  Loading data...")
    parcel_gdf, cama_gdf, merged_gdf = load_and_join(town_name, gdbs, towns_df)

    if merged_gdf is None or merged_gdf.empty:
        print(f"  FAILED: Could not produce joined data for {town_name}")
        return None, None, None

    print(f"  Joined: {len(merged_gdf)} rows (parcels: {len(parcel_gdf)}, CAMA: {len(cama_gdf)})")

    # Check 1: Area
    area_stats = check_area(merged_gdf, parcel_gdf.crs, ratio)

    # Check 2: Address
    address_stats = check_address(merged_gdf)

    # Check 3: Map
    map_path = render_map(merged_gdf, town_name, MAP_DIR)

    gc.collect()
    return area_stats, address_stats, map_path


def get_towns_to_verify(recheck=False):
    """Get list of towns with ratio > 1.0 that need verification, sorted by ratio desc."""
    with open(JOIN_KEYS_PATH) as f:
        join_keys = json.load(f)

    towns = []
    for name, entry in join_keys.items():
        if name.startswith('_'):
            continue
        if entry.get('no_cama_layer') or entry.get('no_working_join'):
            continue
        ratio = entry.get('ratio', 0)
        if ratio <= 1.0:
            continue
        if not recheck and 'verified' in entry:
            continue
        towns.append((name, ratio))

    towns.sort(key=lambda x: -x[1])
    return towns


def save_verdict(town_name, verified, note=None):
    """Save verification verdict to join_keys.json."""
    with open(JOIN_KEYS_PATH) as f:
        join_keys = json.load(f)

    norm = normalize_town_name(town_name)
    if norm in join_keys:
        join_keys[norm]['verified'] = verified
        if note:
            join_keys[norm]['verify_note'] = note

    with open(JOIN_KEYS_PATH, 'w') as f:
        json.dump(join_keys, f, indent=2)
        f.write('\n')


def main():
    parser = argparse.ArgumentParser(description='Verify town joins with ratio > 1.0')
    parser.add_argument('--town', type=str, help='Verify a single town')
    parser.add_argument('--recheck', action='store_true', help='Re-verify already-done towns')
    args = parser.parse_args()

    gdbs = list_cog_gdbs(COG_DIR)
    towns_df = read_towns_df(METADATA_PATH)

    if args.town:
        towns = [(args.town.lower(), JOIN_KEYS.get(normalize_town_name(args.town), {}).get('ratio', 0))]
    else:
        towns = get_towns_to_verify(recheck=args.recheck)

    print(f"\n{len(towns)} towns to verify")
    if towns:
        print(f"Highest ratio: {towns[0][0]} ({towns[0][1]})")

    for i, (town_name, ratio) in enumerate(towns):
        print(f"\n[{i+1}/{len(towns)}]", end='')
        area_stats, addr_stats, map_path = load_and_verify_town(town_name, gdbs, towns_df)

        while True:
            verdict = input(f"\n  Verdict for {town_name}? [ok/reject/skip/quit]: ").strip().lower()
            if verdict in ('ok', 'reject', 'skip', 'quit'):
                break
            print("  Please enter ok, reject, skip, or quit")

        if verdict == 'ok':
            save_verdict(town_name, True)
            print(f"  → {town_name}: VERIFIED OK")
        elif verdict == 'reject':
            note = input("  Optional note: ").strip() or None
            save_verdict(town_name, False, note)
            print(f"  → {town_name}: REJECTED")
        elif verdict == 'quit':
            print("Quitting.")
            break
        # skip: do nothing


if __name__ == '__main__':
    main()
