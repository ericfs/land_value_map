import os
import geopandas as gpd
import pandas as pd
from shapely import force_2d

# GeoJSON Export

def df_for_geojson(df):
  cols = ['Appraised_Total', 'Land_Acres', 'geometry']
  has_location = 'Location' in df.columns
  has_tax_exempt = 'Tax_Exempt' in df.columns

  # Detect when Location is obviously wrong (e.g., a town code like "93" for
  # every parcel in New Haven) and fall back to Location_1 if available.
  if has_location and 'Location_1' in df.columns:
      unique_vals = df['Location'].dropna().str.strip().replace('', pd.NA).dropna().unique()
      if len(unique_vals) <= 1:
          df = df.drop(columns=['Location']).rename(columns={'Location_1': 'Location'})

  if has_location:
      cols.insert(0, 'Location')
  if has_tax_exempt:
      cols.append('Tax_Exempt')
  df = df[cols]

  # Filter out extremely small parcels which are probably an error
  # or a building without land.
  df = df[df['Land_Acres'] > 0.02]

  # Deduplicate parcels that share identical geometry (e.g., condo units
  # where multiple CAMA records join to one parcel). Sum appraised values;
  # land acres are shared across units so take max.
  crs = df.crs
  df['_geom_wkb'] = df.geometry.apply(lambda g: g.wkb)
  agg_dict = {
      'Appraised_Total': 'sum',
      'Land_Acres': 'max',
      'geometry': 'first',
  }
  if has_location:
      agg_dict['Location'] = 'first'
  if has_tax_exempt:
      agg_dict['Tax_Exempt'] = 'min'
  df = df.groupby('_geom_wkb').agg(agg_dict).reset_index(drop=True)
  df = gpd.GeoDataFrame(df, geometry='geometry', crs=crs)

  # Change to the coordinate system expected by tippecanoe
  df = df.to_crs(epsg=4326)

  # Strip Z coordinates (some towns have 3D coords with Z=0)
  df['geometry'] = df.geometry.apply(force_2d)

  # Simplify geometry — tolerance 0.00005° ≈ 5.5m at CT latitude
  df['geometry'] = df.geometry.simplify(tolerance=0.00005, preserve_topology=True)

  # Round numeric columns to save file bytes
  df['Appraised_Total'] = df['Appraised_Total'].round(0).astype(int, errors='ignore')
  df['Land_Acres'] = df['Land_Acres'].round(3)

  if has_location:
      df['Location'] = df['Location'].fillna('').str.strip().str.title()

  if has_tax_exempt:
      df['Tax_Exempt'] = df['Tax_Exempt'].astype(int)

  return df

def export_geojson(df, filename):
  '''Export the DataFrame to a GeoJSON file that can be used with Tippecanoe.'''
  df = df_for_geojson(df)

  # Ensure directory exists
  os.makedirs(os.path.dirname(filename), exist_ok=True)

  # Export to GeoJSON with limited coordinate precision (5 decimal places ≈ 1.1m)
  df.to_file(filename, driver='GeoJSON', coordinate_precision=5)