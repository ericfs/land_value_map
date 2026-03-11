import os
import geopandas as gpd
from shapely import force_2d

# GeoJSON Export

def df_for_geojson(df):
  df = df[[
    'Appraised_Total',
    'Land_Acres',
    'geometry'
  ]]

  # Filter out extremely small parcels which are probably an error
  # or a building without land.
  df = df[df['Land_Acres'] > 0.02]

  # Deduplicate parcels that share identical geometry (e.g., condo units
  # where multiple CAMA records join to one parcel). Sum appraised values;
  # land acres are shared across units so take max.
  crs = df.crs
  df['_geom_wkb'] = df.geometry.apply(lambda g: g.wkb)
  df = df.groupby('_geom_wkb').agg({
      'Appraised_Total': 'sum',
      'Land_Acres': 'max',
      'geometry': 'first',
  }).reset_index(drop=True)
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

  return df

def export_geojson(df, filename):
  '''Export the DataFrame to a GeoJSON file that can be used with Tippecanoe.'''
  df = df_for_geojson(df)

  # Ensure directory exists
  os.makedirs(os.path.dirname(filename), exist_ok=True)

  # Export to GeoJSON with limited coordinate precision (5 decimal places ≈ 1.1m)
  df.to_file(filename, driver='GeoJSON', coordinate_precision=5)