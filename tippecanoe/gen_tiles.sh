#! /bin/bash

set -euo pipefail

GEOJSON_DIR="${GEOJSON_DIR:?GEOJSON_DIR must be set}"
TILES_DIR="${TILES_DIR:?TILES_DIR must be set}"

tippecanoe -zg \
  --no-tile-compression \
  --force \
  --simplification=3 \
  --minimum-detail=6 \
  --low-detail=11 \
  # TODO: Try using a lower limit
  --maximum-tile-bytes=5000000 \
  --no-feature-limit \
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