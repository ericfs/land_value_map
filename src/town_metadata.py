# Reads and updates town metadata.

import pandas as pd

# Reads Town metadata from a Metadata CSV file.
# This expects metadata from
# https://data.ct.gov/Local-Government/2024-Connecticut-Parcel-and-CAMA-Data/pqrn-qghw/about_data
def read_towns_df(csv_file_path):
  csv_file_path = "/content/drive/MyDrive/ct_land_value/Metadata_2024.csv"

  towns_df = pd.read_csv(csv_file_path)
  towns_df.columns = towns_df.columns.str.replace(' ', '_')
  return towns_df