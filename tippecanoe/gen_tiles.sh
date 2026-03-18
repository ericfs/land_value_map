#! /bin/bash

set -euo pipefail

GEOJSON_DIR="${GEOJSON_DIR:?GEOJSON_DIR must be set}"
TILES_DIR="${TILES_DIR:?TILES_DIR must be set}"

tippecanoe -z12 \
  --no-tile-compression \
  --force \
  --simplification=3 \
  --minimum-detail=6 \
  --low-detail=11 \
  --maximum-tile-bytes=3200000 \
  --no-feature-limit \
  --coalesce-densest-as-needed \
  --extend-zooms-if-still-dropping \
  -x Location_Parcels \
  -x Appraised_Value_Per_Acre \
  -x Zone \
  -l parcels \
  --accumulate-attribute=Appraised_Total:sum \
  --accumulate-attribute=Land_Acres:sum \
  --accumulate-attribute=Tax_Exempt:min \
  --output-to-directory="${TILES_DIR}" \
"${GEOJSON_DIR}"/*.geojson
