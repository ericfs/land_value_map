"""Convert a statewide GDB layer to GeoParquet for faster repeated reads.

Usage:
    python3 gdb_to_parquet.py --gdb=path/to/file.gdb --output=path/to/output.parquet

Reads the GDB in chunks (skip_features/max_features) to stay within memory
limits, writing per-chunk parquet files that are concatenated at the end.
Skips conversion if the output file already exists.
"""

import argparse
import gc
import json
import os
import tempfile

import geopandas as gpd
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pyogrio

STATEWIDE_LAYER = "Connecticut_CAMA_and_Parcel_Layer"
CHUNK_SIZE = 200_000


def read_chunk_with_retry(gdb_path, offset, size):
    """Read a chunk, retrying with smaller sub-chunks on geometry errors."""
    try:
        return pyogrio.read_dataframe(
            gdb_path, layer=STATEWIDE_LAYER, on_invalid="fix",
            skip_features=offset, max_features=size,
        )
    except pyogrio.errors.FeatureError:
        if size <= 1:
            print(f"    Skipping unreadable feature at offset {offset}")
            return None
        mid = size // 2
        print(f"    Geometry error in chunk at offset {offset}, subdividing...")
        left = read_chunk_with_retry(gdb_path, offset, mid)
        right = read_chunk_with_retry(gdb_path, offset + mid, size - mid)
        parts = [p for p in (left, right) if p is not None and len(p) > 0]
        if not parts:
            return None
        return gpd.GeoDataFrame(pd.concat(parts, ignore_index=True))


def convert(gdb_path, output_path):
    if os.path.exists(output_path):
        print(f"GeoParquet already exists: {output_path}")
        return

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    tmp_dir = tempfile.mkdtemp(prefix="gdb2pq_")

    info = pyogrio.read_info(gdb_path, layer=STATEWIDE_LAYER)
    total_features = info["features"]
    print(f"Converting {gdb_path} ({total_features} features) to GeoParquet...")

    chunk_files = []
    geo_metadata = None
    offset = 0
    i = 0

    while offset < total_features:
        remaining = min(CHUNK_SIZE, total_features - offset)
        gdf = read_chunk_with_retry(gdb_path, offset, remaining)
        offset += remaining

        if gdf is None or len(gdf) == 0:
            continue

        part_path = os.path.join(tmp_dir, f"part_{i:04d}.parquet")
        gdf.to_parquet(part_path)
        chunk_files.append(part_path)
        print(f"  chunk {i}: {len(gdf)} rows (total {offset}/{total_features})")

        # Capture geo metadata from the first chunk
        if geo_metadata is None:
            pf = pq.read_metadata(part_path)
            geo_metadata = pf.metadata[b"geo"]

        del gdf
        gc.collect()
        i += 1

    # Concatenate using pyarrow (lower memory than geopandas concat)
    print(f"Merging {len(chunk_files)} chunks...")

    # Build target schema: first non-null type for each field
    all_schemas = [pq.read_schema(f) for f in chunk_files]
    field_types = {}
    for s in all_schemas:
        for field in s:
            if field.name not in field_types or field_types[field.name] == pa.null():
                field_types[field.name] = field.type
    field_names = [f.name for f in all_schemas[0]]
    target_schema = pa.schema(
        [pa.field(n, field_types[n]) for n in field_names],
        metadata={b"geo": geo_metadata, **{k: v for k, v in all_schemas[0].metadata.items() if k != b"geo"}},
    )

    writer = None
    total_rows = 0
    for f in chunk_files:
        t = pq.read_table(f)
        # Cast mismatched columns
        if t.schema.remove_metadata() != target_schema.remove_metadata():
            columns = []
            for field in target_schema:
                col = t.column(field.name)
                if col.type != field.type:
                    if col.type == pa.null():
                        col = pa.nulls(len(t), type=field.type)
                    else:
                        col = col.cast(field.type)
                columns.append(col)
            t = pa.table(
                {field.name: col for field, col in zip(target_schema, columns)},
                schema=target_schema,
            )
        else:
            t = t.replace_schema_metadata(target_schema.metadata)

        if writer is None:
            writer = pq.ParquetWriter(output_path, target_schema)
        writer.write_table(t)
        total_rows += len(t)
        del t
        gc.collect()

    if writer:
        writer.close()
    print(f"Saved {output_path} ({total_rows} rows)")

    # Clean up temp files
    for f in chunk_files:
        os.remove(f)
    os.rmdir(tmp_dir)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert statewide GDB to GeoParquet")
    parser.add_argument("--gdb", required=True, help="Path to statewide .gdb")
    parser.add_argument("--output", required=True, help="Output .parquet path")
    args = parser.parse_args()
    convert(args.gdb, args.output)
