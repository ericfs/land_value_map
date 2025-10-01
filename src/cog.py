import os
from export_geojson import export_geojson
from static_map import render_map
from town_join import attempt_join
from town_layers import gdb_to_town_layers
from town_name import town_name_to_file_name
from value_per_acre import compute_value_per_acre, filter_value_per_acre, compute_capped_value_per_acre

# Lists COGs represented as GDB directories
# This expects data from
# https://data.ct.gov/Local-Government/2024-Connecticut-Parcel-and-CAMA-Data/pqrn-qghw/about_data
def list_cog_gdb_files(cog_directory_path):
  # List all items in the directory
  cog_items = os.listdir(cog_directory_path)

  # Filter for directories (assuming COGs are represented by directories)
  cog_folders = [item for item in cog_items if os.path.isdir(os.path.join(cog_directory_path, item))]

  # map to paths
  return [os.path.join(cog_directory_path, item, f'{item}.gdb') for item in cog_folders]


def process_gdb(gdb_path, base_output_path, towns_df, render_image = False, overwrite = False):
  '''Process COG GDB.
  :param gdb_path: COG GDB to read and process.
  :param base_output_path: Output directory.
  :param towns_df: Dataframe of Town metadata.
  :param render_image: If true, output each town as a map image. If false, output each town as geojson.
  :param overwrite: If true, overwriten existing files.
  '''
  missing_join = []
  print(f"\nProcessing COG at path: {gdb_path}")
  town_layers = gdb_to_town_layers(gdb_path)
  for town_layer_info in town_layers:
    town_name = town_layer_info.town_name
    filename = town_name_to_file_name(base_output_path, town_name, render_image)
    if not overwrite and os.path.exists(filename):
      print(f"\tFile already exists: {filename}")
      continue

    print(f"\n\tAttempting to join data for town: {town_name}")
    attempt_join_df = attempt_join(gdb_path, town_layer_info, towns_df, town_name)

    if attempt_join_df.empty:
      print(f"\t\tNo join found for town: {town_name}")
      missing_join.append(town_name)
      continue

    try:
      compute_value_per_acre(attempt_join_df)
      value_per_acre_df = filter_value_per_acre(attempt_join_df)
      compute_capped_value_per_acre(value_per_acre_df)
      if render_image:
        render_map(value_per_acre_df, town_name, filename)
      else:
        export_geojson(value_per_acre_df, filename)
    except Exception as e:
      print(f"An error occurred while processing data for {town_name}: {e}")
      missing_join.append(town_name)
      continue
  return missing_join

