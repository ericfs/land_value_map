#!/usr/bin/env python3

import json
import argparse
import os

def merge_tilejson_data(tilejson_path, metadata_path, scheme, hostname, version, output_path):
    """
    Reads a base tile.json file, merges bounds and center from a metadata
    file, adds additional predefined data, and writes to a new file.

    Args:
        tilejson_path (str): Path to the input tile.json file.
        metadata_path (str): Path to the JSON file with bounds and center.
        output_path (str): Path for the output merged JSON file.
    """
    # --- 1. Read the input JSON files ---
    try:
        with open(tilejson_path, "r") as f:
            tile_data = json.load(f)
        print(f"Successfully read base tile data from '{tilejson_path}'")

        with open(metadata_path, "r") as f:
            metadata = json.load(f)
        print(f"Successfully read metadata from '{metadata_path}'")

    except FileNotFoundError as e:
        print(f"Error: {e}. Please check your file paths.")
        return
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON: {e}")
        return

    # --- 2. Merge data ---
    
    # Update bounds and center from the metadata file
    if "bounds" in metadata:
        tile_data["bounds"] = metadata["bounds"]
    if "center" in metadata:
        tile_data["center"] = metadata["center"]
    if "minzoom" in metadata:
        tile_data["minzoom"] = metadata["minzoom"]
    if "maxzoom" in metadata:
        tile_data["maxzoom"] = metadata["maxzoom"]

    # Get vector_layers
    if not "json" in metadata:
        print("Error: missing layer json in metadata file.")
    inner_json = json.loads(metadata["json"])
    tile_data["vector_layers"] = inner_json["vector_layers"]

    # Define and merge additional data.
    # You can customize this dictionary with any other data you want to add
    # or overwrite in the final tile.json.
    additional_data = {
        "version": version,
        "tiles": [
            f"{scheme}://{hostname}/{version}/tiles/{{z}}/{{x}}/{{y}}.pbf"
        ]
    }

    # Merge the additional data into the main tile data dictionary
    tile_data.update(additional_data)
    print("Successfully merged data.")

    # --- 3. Write to the output file ---
    try:
        # Create parent directories if they don't exist
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(tile_data, f, indent=2)
        print(f"Successfully wrote merged tile.json to '{output_path}'")
    except IOError as e:
        print(f"Error writing to file: {e}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Merge data into a tile.json file.')
    parser.add_argument("--tilejson", help="Path to the input tile.json file (e.g., templates/tile.json).")
    parser.add_argument("--metadata", help="Path to the metadata JSON file containing bounds and center.")
    parser.add_argument("--output", help="Path for the output merged tile.json file.")
    parser.add_argument("--scheme", help="Scheme to use in tile URL template.", default="https")
    parser.add_argument("--hostname", help="Hostname to use in tile URL template.")
    parser.add_argument("--version", help="Version number to use in tile URL template.")
    
    args = parser.parse_args()
    
    merge_tilejson_data(args.tilejson, args.metadata, args.scheme, args.hostname, args.version, args.output)