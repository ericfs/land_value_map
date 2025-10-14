import argparse
import os
from itertools import repeat
from cog import list_cog_gdb_files, process_gdb
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import cpu_count
from town_metadata import read_towns_df

def exec_process_gdb(gdb, metadata_file_path, output_dir):
  towns_df = read_towns_df(metadata_file_path)
  return process_gdb(gdb, output_dir, towns_df)

if __name__ == '__main__':
  parser = argparse.ArgumentParser(description='Generate GeoJSON files for all input towns.')
  parser.add_argument('--input_dir', help='Path to the input directory containing GDB and metadata.')
  parser.add_argument('--output_dir', help='Path to the output directory.')

  args = parser.parse_args()

  print('CPUs:', cpu_count())
  e = ProcessPoolExecutor(cpu_count() * 3)

  input_dir = args.input_dir
  output_dir = args.output_dir

  cog_directory_path = os.path.join(input_dir, 'Parcel Collection 2024/Parcel_By_COG')
  metadata_file_path = os.path.join(input_dir, 'Metadata_2024.csv')

  cog_gdbs = list_cog_gdb_files(cog_directory_path)
  missing_join = list(e.map(exec_process_gdb, cog_gdbs, repeat(metadata_file_path), repeat(output_dir)))
  missing_join = [item for sublist in missing_join for item in sublist]
  print(missing_join)