import argparse
from statewide import process_statewide

if __name__ == '__main__':
  parser = argparse.ArgumentParser(description='Generate GeoJSON files for all CT towns.')
  parser.add_argument('--output_dir', required=True, help='Path to the output directory.')
  parser.add_argument('--parquet', required=True, help='Path to the statewide GeoParquet file.')
  parser.add_argument('--cama_dir', help='Path to the CAMA CSV directory (for fallback joins).')

  args = parser.parse_args()

  failed = process_statewide(args.output_dir, args.parquet, args.cama_dir)
  if failed:
    print(f"\nFailed towns: {failed}")
  else:
    print("\nAll towns processed successfully.")
