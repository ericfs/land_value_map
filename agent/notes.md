# Town Join Challenge Notes

## Overview
The challenge is to correctly join CAMA and Parcel tables for each Connecticut town.
A correct join should produce close to a 1:1 match between the two tables.

## Data Sources
- `inputs/Parcel Collection 2024/Parcel_By_COG/` - Contains one directory per COG (Council of Government)
- `inputs/Metadata_2024.csv` - Contains "Link Field for CAMA" and "Link field for Parcels" columns
- Note: Some metadata entries appear incorrect (e.g., ".", "N/A", "Unknown", URLs in join field)

## Notable Issues in Metadata CSV

### Clearly Invalid Entries
- West Hartford: "." for both link fields - likely misconfigured
- Darien: "HTTPS://GIS.VGSI.COM/DARIEN/PARCEL.ASPX?PID=04000" as CAMA join - URL, not a field name
- Bridgeport: "EC" as cama and URL "https://gis.vgsi.com/bridgeportct/" as parcels join
- Hartford: "Unknown" for both - unknown
- Stafford: "Unknown" for both - unknown
- South Windsor: CAMA "GIS_Tag" but Parcels "Unknown" - partial info
- Vernon: "Unknown" for CAMA, "LSRN" for Parcels - partial info
- Enfield: CAMA "GIS_ID" but Parcels "Unknown"
- Wethersfield: both "Unknown"
- Andover: CAMA field appears to be an email address `assistantassessor@andoverct.org`

### Non-Standard Entries Needing Special Handling
- Windsor: CAMA "REM_PIN", Parcels "FILECODE" 
- Rocky Hill: CAMA "PID", Parcels "Unique_ID" - different field names
- Southington: CAMA "REM_ID", Parcels "CAMA_ID" - direct cross join?
- East Haddam, Chester, Deep River, Durham: compound "Append Map-Lot-Unit" 
- New London: compound "Concatenate Map+Block+Lot+LotCut+Unit"
- Ledyard: compound "Map+Block+Lot(and sometimes+unit or lot cut)"
- Groton: compound "Map + Map Cut +Block + Lot"

## Existing Join Logic in town_join.py
- Tries parcel candidate: ['Link'] first, then metadata value, then 'UNQ_CARD', 'REALESTATE', 'GIS_PIN'
- Tries CAMA candidates: metadata value first, then fallbacks: 'Parcel_ID', 'Parcel ID', 'PID', 'Link', 'GIS_Tag', 'GIS Tag', 'Account_Number'
- Success threshold: len(merged) * 2 > len(parcel_gdf) (50% match) or len(merged) * 20 > len(parcel_gdf) (5% match for numeric)

## Investigation Script Results

All 159 CT towns have been analyzed. Results stored in `agent/join_keys.json`.
`src/town_join.py` now reads this file and applies the correct strategy per town.

### Summary
- **Good joins (>50% match)**: 125 towns — direct key match (Link↔PID, Link↔GIS_Tag, etc.)
- **Weak joins (5–50%)**: a few towns where best available match is partial
- **No working join**: 5 towns — Durham, Groton, Deep River, Thomaston, Roxbury
- **No CAMA layer in GDB**: 10 towns — Bolton, Columbia, Granby, Hebron, Rocky Hill, Stafford, Willington (CRCOG); Cornwall, New Hartford, North Canaan (NHCOG)

### Special Join Strategies Implemented
| Transform | Towns | Description |
|-----------|-------|-------------|
| `strip_both` | Bethel | Strip whitespace from both keys before join |
| `strip_cama_prefix` | East Haddam, Old Lyme | CAMA link has `XXXXX-` prefix; strip N+1 chars |
| `cama_compound_strip` | Barkhamsted | Build CAMA `Map-Block-Lot` with strip() on each part |
| `cama_int_compound` | Ledyard | Build CAMA `Map-Block-Lot` casting each to int |
| `cama_zeropad_compound` | Sprague | Build CAMA `Map-Block-Lot` with zero-padding |
| `cama_int_compound_newlondon` | New London | CAMA Map is string (e.g. 'F27'); Block/Lot as int |
| `normalize_cama_map_oxford` | Oxford | CAMA Map has spaces; replace with hyphens |
| `normalize_cama_gistag_montville` | Montville | CAMA GIS_Tag uses `/`; replace with `-` |
| `truncate_parcel_key` | Sherman | Use first 7 chars of JWS_PID |
| `bridgewater_compound` | Bridgewater | CAMA: Map+' '+Block compound; parcel MBL stripped |
| `winchester_compound` | Winchester | Parcel: Map+' '+Block+' '+Lot; CAMA PROP_ID split on `\|\|` |
| `as_number` | Hartford, Wethersfield, Lebanon | Numeric join to handle leading zeros / float storage |

### Non-Standard Parcel Keys
Some towns don't use `Link` as their parcel identifier:
- Avon: `PARNO`, Canaan/Colebrook/Harwinton/Morris/Norfolk: `UniqueID`
- Bristol: lowercase `link`, Bridgewater: `MBL`, Darien: `REALESTATE`
- Derby: `Parcel_ID`, Easton/Ridgefield: `Parcel_ID`, Enfield/Norwalk/Redding: `GIS_ID`
- Glastonbury: `PropertyID`, Greenwich: `CAMALINK`, Hartford: `GIS_PIN`
- Hartland: `F_O_PIN`, Kent: `MAP_BL1`, Lebanon: `AV_PID`
- Middletown: `CAMA_ID`, Monroe: `Parcel_ID`, New Britain: `PID`
- Sharon: `MAP_LOT1`, Stamford: `UNQ_CARD`, Torrington: `PID`
- Warren: `UNIQUE_ID`, Westport: `MAP_BK_LOT`, Wethersfield: `GISID`
- Windsor: `FILECODE`

## Join Verification (ratio > 1.0)

47 towns have join ratio > 1.0 (more merged rows than parcel rows). Verification utility: `agent/verify_joins.py`. Maps saved to `agent/verify_maps/`.

### Verified Towns
| Town | Ratio | Area ≤5% | Area ≤20% | Address | Notes |
|------|-------|----------|-----------|---------|-------|
| Hartford | 25.9 | 88.3% | 96.9% | No parcel Location col | Condos: 140 CAMA rows per parcel for condo buildings. Join correct. |
| Putnam | 8.19 | 60.7% | 91.9% | No CAMA Location col | Actual ratio 0.89. CAMA has duplicate rows (e.g. hospital with 10 identical entries). |
| Mansfield | 6.38 | 54.9% | 86.1% | No parcel Location col | Actual ratio 0.92. CAMA duplicates (157 identical rows for one commercial property). |
| Stamford | 1.5 | 66.6% | 96.7% | No Location cols | Actual ratio 0.97. Map shows expected downtown/waterfront premium. |
| Norwalk | 1.34 | 61.8% | 92.2% | No Location cols | Actual ratio 0.98. Spatially coherent. |
| Ellington | 1.04 | 79.7% | 97.1% | 99.9% exact | Best quality join. Addresses nearly perfect match. |

### Key Observations
- **Reported ratio vs actual ratio**: The ratios in `join_keys.json` were computed during initial investigation (CAMA rows / parcel rows before join). The actual post-join ratio is often much lower because not all CAMA rows match a parcel.
- **Many-to-one is mostly condos**: Hartford, Stamford, Norwalk all have condos where multiple CAMA assessment records share one parcel polygon.
- **CAMA data quality**: Putnam and Mansfield have duplicated CAMA rows (identical data repeated), inflating the ratio.
- **Address comparison often unavailable**: Many parcel layers lack a `Location` column, and some CAMA layers also lack it after the column rename (`Location` → `Location_CAMA`).
- **Area comparison reliable**: Even for high-ratio towns, Shape_Area vs Land_Acres typically agrees within 20% for >90% of rows. The worst mismatches are condo units where CAMA Land_Acres reflects the unit's share, not the full parcel.

