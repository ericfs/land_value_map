#! /bin/bash

set -euo pipefail

GEOJSON_DIR="${GEOJSON_DIR:?GEOJSON_DIR must be set}"
TILES_DIR="${TILES_DIR:?TILES_DIR must be set}"

tippecanoe -zg \
  --no-tile-compression \
  --force \
  --simplification=2 \
  --minimum-detail=6 \
  --low-detail=11 \
  --maximum-tile-bytes=2100000 \
  --coalesce-densest-as-needed \
  --extend-zooms-if-still-dropping \
  -x Location_Parcels \
  -x Appraised_Value_Per_Acre \
  -x Zone \
  -l parcels \
  --accumulate-attribute=Appraised_Total:sum \
  --accumulate-attribute=Land_Acres:sum \
  --output-to-directory="${TILES_DIR}" \
"${GEOJSON_DIR}"/*.geojson

gzip -fk9 "${TILES_DIR}"/*/*/*.pbf