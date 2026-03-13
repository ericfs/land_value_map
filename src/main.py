import argparse
from statewide import process_statewide_gdb

if __name__ == '__main__':
  parser = argparse.ArgumentParser(description='Generate GeoJSON files for all CT towns.')
  parser.add_argument('--output_dir', required=True, help='Path to the output directory.')
  parser.add_argument('--statewide_gdb', required=True, help='Path to the statewide GDB file.')
  parser.add_argument('--cama_dir', help='Path to the CAMA CSV directory (for fallback joins).')

  args = parser.parse_args()

  failed = process_statewide_gdb(args.output_dir, args.statewide_gdb, args.cama_dir)
  if failed:
    print(f"\nFailed towns: {failed}")
  else:
    print("\nAll towns processed successfully.")
