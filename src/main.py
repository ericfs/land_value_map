import os
from cog import list_cog_gdb_files, process_gdb
from concurrent.futures import ProcessPoolExecutor
from multiprocessing import cpu_count
from town_metadata import read_towns_df

BASE_PATH = '..'
COG_DIRECTORY_PATH = os.path.join(BASE_PATH, 'Parcel Collection 2024/Parcel_By_COG')
METADATA_FILE_PATH = os.path.join(BASE_PATH, 'Metadata_2024.csv')

def exec_process_gdb(gdb):
  towns_df = read_towns_df(METADATA_FILE_PATH)
  return process_gdb(gdb, BASE_PATH, towns_df)

if __name__ == '__main__':
  print('CPUs:', cpu_count())
  e = ProcessPoolExecutor(cpu_count() * 3)

  COG_GDBS = list_cog_gdb_files(COG_DIRECTORY_PATH)
  missing_join = list(e.map(exec_process_gdb, COG_GDBS))
  missing_join = [item for sublist in missing_join for item in sublist]
  print(missing_join)