# This module joins a CAMA DataFrame to a Parcel GeoDataFrame.

import geopandas as gpd
import fiona
import re
import pandas as pd
from town_name import normalize_town_name

FALLBACK_COLUMNS = [
    'Parcel_ID',
    'Parcel ID',
    'PID',
    'Link',
    'GIS_Tag',
    'GIS Tag',
    'Account_Number'
]

def add_int_column(df, column_name):
  df[f'{column_name}_numeric'] = pd.to_numeric(df[column_name], errors='coerce')

def make_update_for_str(column_name):
  def update_for_str(df):
    if column_name in df.columns:
      df[column_name] = df[column_name].astype(str)
    return column_name
  return update_for_str

def make_update_for_int(column_name):
  def update_for_int_join(df):
    new_col_name = f'{column_name}_numeric'
    if column_name in df.columns:
      add_int_column(df, column_name)
      df = df.dropna(subset=[new_col_name])
    return new_col_name
  return update_for_int_join

def make_update_for_multicolumn(column_names):
  join_column_name = column_names.join('_') + 'key'
  def update_for_multicolumn(df):
    df[join_column_name] = df[column_names].apply(lambda row: '_'.join(row.values.astype(str)), axis=1)
    return join_column_name
  return update_for_multicolumn

def inner_join(gdf_left, gdf_right, left_on, right_on, town_name, as_number=False):
    try:
        # Ensure columns exist and are of string type for robust joining
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
            print(f"Join keys not found in one or both DataFrames: Parcels='{left_on}' (exists: {left_on in gdf_left.columns}), CAMA='{right_on}' (exists: {right_on in gdf_right.columns})")
            return pd.DataFrame() # Return empty if join keys are missing
    except Exception as e:
        print(f"Error during inner join for {town_name}: {e}")
        return pd.DataFrame() # Return an empty DataFrame if join fails

def add_column_suffix(df, old_name, suffix):
  df.rename(columns={old_name: f'{old_name}_{suffix}'}, inplace=True)


def camel_to_capital_snake(name):
  return re.sub('([a-z0-9])([A-Z])', r'\1_\2', name)

def normalize_column_names(df):
  df.columns = [col.replace(' ', '_') for col in df.columns]
  df.columns = [camel_to_capital_snake(col) for col in df.columns]

def read_town_layers(gdb_path, town_layer_info, towns_df):
  town_name = town_layer_info.town_name
  parcels_layer_name = town_layer_info.parcels_layer_name
  cama_layer_name = town_layer_info.cama_layer_name
  # Read the parcel layer
  parcel_gdf = gpd.read_file(gdb_path, layer=parcels_layer_name)
  add_column_suffix(parcel_gdf, 'Location', 'Parcels')

  # Read the CAMA layer
  cama_gdf = gpd.read_file(gdb_path, layer=cama_layer_name)
  add_column_suffix(cama_gdf, 'Location', 'CAMA')
  normalize_column_names(cama_gdf)

  # Look up join keys from the towns table
  town_info = towns_df[towns_df['Town'].str.lower() == town_name.lower()]
  return parcel_gdf, cama_gdf, town_info

DROP_ROWS = {
  # This is the entire road network in a single parcel
  'shelton': ('Link', '40  40')
}

# Drops problematic rows
def drop_rows(df, town_name):
  town_name = normalize_town_name(town_name)
  if town_name in DROP_ROWS:
    drop_key, drop_value = DROP_ROWS[town_name]
    df = df[df[drop_key] != drop_value]
  return df

def attempt_join(gdb_path, town_layer_info, towns_df, town_name):
  try:
      parcel_gdf, cama_gdf, town_info = read_town_layers(gdb_path, town_layer_info, towns_df)
      parcel_gdf = drop_rows(parcel_gdf, town_name)


      cama_join_key_candidates = []
      if not town_info.empty:
        cama_join_key_candidates.append(
            town_info['Link_Field_for_CAMA'].iloc[0])
      cama_join_key_candidates.extend(FALLBACK_COLUMNS)

      # Prefer to use 'Link' for the parcels join key
      parcel_join_key_candidates = ['Link']
      if not town_info.empty:
        parcel_join_key_candidates.append(
            town_info['Link_field_for_Parcels'].iloc[0])
        parcel_join_key_candidates.append('UNQ_CARD') # Stamford
        parcel_join_key_candidates.append('REALESTATE') # Darien
        parcel_join_key_candidates.extend('GIS_PIN') # Hartford

      for parcels_join_key in parcel_join_key_candidates:
        if not parcels_join_key in parcel_gdf.columns:
          continue
        for cama_join_key in cama_join_key_candidates:
          if not cama_join_key in cama_gdf.columns:
            continue
          merged_df = inner_join(
              parcel_gdf, cama_gdf, parcels_join_key, cama_join_key, town_layer_info.town_name)
          if not merged_df.empty and len(merged_df) * 2 > len(parcel_gdf):
              print(f"Successfully joined using {cama_join_key}. Merged DataFrame shape: {merged_df.shape}")
              return merged_df
          merged_df = inner_join(
              parcel_gdf, cama_gdf, parcels_join_key, cama_join_key, town_layer_info.town_name, as_number=True)
          if not merged_df.empty and len(merged_df) * 20 > len(parcel_gdf):
              print(f"Successfully joined using {cama_join_key} as numbers. Merged DataFrame shape: {merged_df.shape}")
              return merged_df

  except Exception as e:
      print(f"An error occurred while processing data for {town_name}: {e}")

  return pd.DataFrame()