import os

# GeoJSON Export

def df_for_geojson(df):
  df = df[[
    'Appraised_Value_Per_Acre',
    'Appraised_Total',
    'Land_Acres',
    'geometry'
  ]]

  # Filter out extremely small parcels which are probably an error
  # or a building without land.
  # Is there a way to filter this at Map rendering time instead?
  df = df[df['Land_Acres'] > 0.02]
  
  # Change to the coordinate system to one expected by tippecanoe
  df = df.to_crs(epsg=4326)

  return df

def export_geojson(df, filename):
  '''Export the DataFrame to a GeoJSON file that can be used with Tippecanoe.'''
  df = df_for_geojson(df)

  # Ensure directory exists
  os.makedirs(os.path.dirname(filename), exist_ok=True)

  # Export to GeoJSON
  df.to_file(filename, driver='GeoJSON')