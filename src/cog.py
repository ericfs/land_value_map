import os

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