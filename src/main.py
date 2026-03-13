import argparse
from statewide import process_statewide_gdb

if __name__ == '__main__':
  parser = argparse.ArgumentParser(description='Generate GeoJSON files for all CT towns.')
  parser.add_argument('--input_dir', help='Path to the input directory.')
  parser.add_argument('--output_dir', help='Path to the output directory.')

  args = parser.parse_args()

  failed = process_statewide_gdb(args.input_dir, args.output_dir)
  if failed:
    print(f"\nFailed towns: {failed}")
  else:
    print("\nAll towns processed successfully.")
