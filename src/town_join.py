# This module joins a CAMA DataFrame to a Parcel GeoDataFrame.

import geopandas as gpd
import json
import os
import re
import pandas as pd
from town_name import normalize_town_name

# Load precomputed join strategies discovered by agent/investigate_joins.py
_JOIN_KEYS_PATH = os.path.join(os.path.dirname(__file__), '..', 'agent', 'join_keys.json')
with open(_JOIN_KEYS_PATH) as _f:
    JOIN_KEYS = {k: v for k, v in json.load(_f).items() if not k.startswith('_')}

FALLBACK_COLUMNS = [
    'Parcel_ID',
    'Parcel ID',
    'PID',
    'Link',
    'GIS_Tag',
    'GIS Tag',
    'Account_Number',
]


def add_int_column(df, column_name):
    df[f'{column_name}_numeric'] = pd.to_numeric(df[column_name], errors='coerce')


def inner_join(gdf_left, gdf_right, left_on, right_on, town_name, as_number=False):
    try:
        if left_on in gdf_left.columns and right_on in gdf_right.columns:
            if as_number:
                add_int_column(gdf_left, left_on)
                add_int_column(gdf_right, right_on)
                left_on = f'{left_on}_numeric'
                right_on = f'{right_on}_numeric'
                gdf_left = gdf_left.dropna(subset=[left_on])
                gdf_right = gdf_right.dropna(subset=[right_on])
            else:
                gdf_left[left_on] = gdf_left[left_on].astype(str)
                gdf_right[right_on] = gdf_right[right_on].astype(str)

            merged_df = pd.merge(gdf_left, gdf_right, left_on=left_on, right_on=right_on, how='inner')
            return merged_df
        else:
            print(f"Join keys not found: Parcels='{left_on}' (exists: {left_on in gdf_left.columns}), "
                  f"CAMA='{right_on}' (exists: {right_on in gdf_right.columns})")
            return pd.DataFrame()
    except Exception as e:
        print(f"Error during inner join for {town_name}: {e}")
        return pd.DataFrame()


def add_column_suffix(df, old_name, suffix):
    df.rename(columns={old_name: f'{old_name}_{suffix}'}, inplace=True)


def camel_to_capital_snake(name):
    return re.sub('([a-z0-9])([A-Z])', r'\1_\2', name)


def normalize_column_names(df):
    df.columns = [col.replace(' ', '_') for col in df.columns]
    df.columns = [camel_to_capital_snake(col) for col in df.columns]


def read_town_layers(gdb_path, town_layer_info, towns_df):
    town_name = town_layer_info.town_name
    parcel_gdf = gpd.read_file(gdb_path, layer=town_layer_info.parcels_layer_name)
    add_column_suffix(parcel_gdf, 'Location', 'Parcels')
    cama_gdf = gpd.read_file(gdb_path, layer=town_layer_info.cama_layer_name)
    add_column_suffix(cama_gdf, 'Location', 'CAMA')
    normalize_column_names(cama_gdf)
    town_info = towns_df[towns_df['Town'].str.lower() == town_name.lower()]
    return parcel_gdf, cama_gdf, town_info


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


def _safe_int(v):
    try:
        return str(int(float(v)))
    except (ValueError, TypeError):
        return str(v)


def apply_transform(parcel_gdf, cama_gdf, entry):
    """Apply transform preprocessing to parcel/cama dataframes.
    Returns (parcel_key, cama_key) after any derived columns are created."""
    parcel_key = entry['parcel_key']
    cama_key = entry['cama_key']
    transform = entry.get('transform')

    if transform is None:
        return parcel_key, cama_key

    if transform == 'strip_both':
        parcel_gdf[parcel_key] = parcel_gdf[parcel_key].astype(str).str.strip()
        cama_gdf[cama_key] = cama_gdf[cama_key].astype(str).str.strip()

    elif transform == 'strip_cama_prefix':
        # Strip leading digits (e.g. '22280') plus a hyphen from CAMA key
        n = entry['cama_prefix_digits'] + 1  # digits + the '-' separator
        cama_gdf[cama_key] = cama_gdf[cama_key].astype(str).str[n:]

    elif transform == 'cama_compound_strip':
        # Build CAMA compound key from multiple columns with whitespace stripping
        cols = entry['cama_cols']
        sep = entry['sep']
        compound_col = '_'.join(cols) + '_compound'
        cama_gdf[compound_col] = cama_gdf[cols].apply(
            lambda r: sep.join(str(v).strip() for v in r), axis=1)
        cama_key = compound_col

    elif transform == 'cama_int_compound':
        # Build CAMA compound key casting each component to integer
        cols = entry['cama_cols']
        sep = entry['sep']
        compound_col = '_'.join(cols) + '_compound'
        cama_gdf[compound_col] = cama_gdf[cols].apply(
            lambda r: sep.join(_safe_int(v) for v in r), axis=1)
        cama_key = compound_col

    elif transform == 'cama_int_compound_newlondon':
        # New London: Map is a string (e.g. 'F27'), Block and Lot as integers
        cols = entry['cama_cols']  # ['Map', 'Block', 'Lot']
        sep = entry['sep']
        compound_col = '_'.join(cols) + '_compound'
        def _newlondon_join(r):
            vals = list(r)
            parts = [str(vals[0]).strip()] + [_safe_int(v) for v in vals[1:]]
            return sep.join(parts)
        cama_gdf[compound_col] = cama_gdf[cols].apply(_newlondon_join, axis=1)
        cama_key = compound_col

    elif transform == 'cama_zeropad_compound':
        # Build CAMA compound key with zero-padded integer components
        cols = entry['cama_cols']
        sep = entry['sep']
        pad_widths = entry['pad_widths']
        compound_col = '_'.join(cols) + '_compound'
        def _zeropad_join(r):
            return sep.join(_safe_int(v).zfill(w) for v, w in zip(r, pad_widths))
        cama_gdf[compound_col] = cama_gdf[cols].apply(_zeropad_join, axis=1)
        cama_key = compound_col

    elif transform == 'normalize_cama_map_oxford':
        # Oxford: CAMA Map has spaces (e.g. '35 80 41'); replace with hyphens
        cama_gdf[cama_key] = cama_gdf[cama_key].astype(str).str.replace(' ', '-')

    elif transform == 'normalize_cama_gistag_montville':
        # Montville: CAMA GIS_Tag uses '/' separator; replace with '-'
        cama_gdf[cama_key] = cama_gdf[cama_key].astype(str).str.replace('/', '-')

    elif transform == 'truncate_parcel_key':
        # Sherman: use first N characters of parcel key
        n = entry['parcel_key_length']
        parcel_gdf[parcel_key] = parcel_gdf[parcel_key].astype(str).str[:n]

    elif transform == 'bridgewater_compound':
        # Bridgewater: CAMA compound is Map+' '+Block; parcel MBL is already formatted
        compound_col = 'Map_Block_compound'
        cama_gdf[compound_col] = (
            cama_gdf['Map'].astype(str).str.strip() + ' ' +
            cama_gdf['Block'].astype(str).str.strip()
        )
        cama_key = compound_col
        parcel_gdf[parcel_key] = parcel_gdf[parcel_key].astype(str).str.strip()

    elif transform == 'winchester_compound':
        # Winchester: parcel compound Map+' '+Block+' '+Lot; CAMA PROP_ID split on '||'
        parcel_compound = 'Map_Block_Lot_compound'
        parcel_gdf[parcel_compound] = (
            parcel_gdf['Map'].astype(str).str.strip() + ' ' +
            parcel_gdf['Block'].astype(str).str.strip() + ' ' +
            parcel_gdf['Lot'].astype(str).str.strip()
        )
        parcel_key = parcel_compound
        cama_gdf[cama_key] = cama_gdf[cama_key].astype(str).apply(
            lambda v: ' '.join(v.split('||')))

    else:
        print(f"Warning: unknown transform '{transform}'")

    return parcel_key, cama_key


def _join_from_entry(parcel_gdf, cama_gdf, entry, town_name):
    as_number = entry.get('as_number', False)
    parcel_key, cama_key = apply_transform(parcel_gdf, cama_gdf, entry)
    merged = inner_join(parcel_gdf, cama_gdf, parcel_key, cama_key, town_name, as_number=as_number)
    if not merged.empty:
        print(f"Joined {town_name}: {parcel_key}↔{cama_key} ({len(merged)} rows, ratio={len(merged)/len(parcel_gdf):.2f})")
    return merged


def attempt_join(gdb_path, town_layer_info, towns_df, town_name):
    try:
        norm_name = normalize_town_name(town_name)
        entry = JOIN_KEYS.get(norm_name)

        # Skip towns with no CAMA layer or no discoverable join before reading data
        if entry and entry.get('no_cama_layer'):
            print(f"Skipping {town_name}: no CAMA layer in GDB")
            return pd.DataFrame()
        if entry and entry.get('no_working_join'):
            print(f"Skipping {town_name}: no working join found ({entry.get('note', '')})")
            return pd.DataFrame()

        parcel_gdf, cama_gdf, town_info = read_town_layers(gdb_path, town_layer_info, towns_df)
        parcel_gdf = drop_rows(parcel_gdf, town_name)

        if entry:
            return _join_from_entry(parcel_gdf, cama_gdf, entry, town_name)

        # Fallback heuristic for any towns not covered by join_keys.json
        print(f"Warning: {town_name} not in join_keys.json, using heuristic fallback")
        cama_join_key_candidates = []
        if not town_info.empty:
            cama_join_key_candidates.append(town_info['Link_Field_for_CAMA'].iloc[0])
        cama_join_key_candidates.extend(FALLBACK_COLUMNS)

        parcel_join_key_candidates = ['Link']
        if not town_info.empty:
            parcel_join_key_candidates.append(town_info['Link_field_for_Parcels'].iloc[0])

        for parcels_join_key in parcel_join_key_candidates:
            if parcels_join_key not in parcel_gdf.columns:
                continue
            for cama_join_key in cama_join_key_candidates:
                if cama_join_key not in cama_gdf.columns:
                    continue
                merged_df = inner_join(parcel_gdf, cama_gdf, parcels_join_key, cama_join_key, town_name)
                if not merged_df.empty and len(merged_df) * 2 > len(parcel_gdf):
                    print(f"Fallback joined {town_name} using {cama_join_key}. Shape: {merged_df.shape}")
                    return merged_df
                merged_df = inner_join(parcel_gdf, cama_gdf, parcels_join_key, cama_join_key, town_name, as_number=True)
                if not merged_df.empty and len(merged_df) * 20 > len(parcel_gdf):
                    print(f"Fallback joined {town_name} using {cama_join_key} as numbers. Shape: {merged_df.shape}")
                    return merged_df

    except Exception as e:
        print(f"An error occurred while processing {town_name}: {e}")

    return pd.DataFrame()
