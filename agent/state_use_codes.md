# Connecticut State Use Codes — Research Notes

## Source

**Administrative Abstract Coding System**
Published by the Connecticut Office of Policy and Management (OPM), pursuant to Section 12-27 of the Connecticut General Statutes. Updated September 8, 2025.

PDF: https://portal.ct.gov/-/media/opm/igpp-data-grants-mgmt/igpp-forms/administrative-abstract-coding-system.pdf

## Official OPM Coding System

The official system has **two separate code schemes** for taxable and tax-exempt property.

### Part 1 — Taxable Property Land Use Codes (Numeric, 100–800)

| State Code | Category | Local Codes |
|---|---|---|
| 100 | Residential | 11 Primary Acreage, 12 Excess Acreage, 13 Dwellings, 14 Outbuildings, 15 Condominiums, 16 Mobile Manufactured Homes |
| 200 | Commercial | 21 Land, 22 Buildings, 23 Apartment Buildings, 24 Condominiums, 25 Outbuildings, 26 Apartment Land Only |
| 250 | Income & Expense Penalty | (Prior to Oct 1, 2023 Grand List only) |
| 300 | Industrial | 31 Land, 32 Buildings, 33 Other Improvements, 34 Condominiums |
| 400 | Public Utility | 41 Land, 42 Buildings, 43 Outbuildings |
| 500 | Vacant Land | 51 Residential, 52 Commercial, 53 Industrial, 54 Wetlands, 55 Outbuildings |
| 600 | Use Assessment (PA 490) | 61 Farmland, 62 Forestland, 63 Open Space |
| 700 | 10 Mill Forest | 71 (forest land assessed at $100/acre or less, taxed at 10 mills) |
| 800 | Apartments | (5+ dwelling units, including co-op ownership) |

There is **no code 900** in the official system. Numeric codes stop at 800.

### Part 5 — Tax-Exempt Real Property Codes (Alphabetic)

Tax-exempt property uses a separate **alphabetic** coding system (4-character codes), not numeric codes. The OPM document states: *"Tax exempt property is not required to be coded with a Land Use Code. Only the assessment and the Tax-Exempt Code are required to be listed."*

Key exempt categories:

| State Code | Statute | Description |
|---|---|---|
| AAAX | 12-81(1) | Federal property |
| BAAX | 12-81(4) | Municipal property |
| BBAX | 12-81(67) | Beach Property |
| BDHX | 12-76 | Water supply land |
| BEAX | 12-81(5) | Public purpose by will or trust |
| CAAX | 12-81(6) | Volunteer Fire Company |
| DAAX | 12-81(7) | Scientific |
| DBAX | 12-81(7) | Educational |
| DCAX | 12-81(7) | Literary |
| DDAX | 12-81(7) | Historical |
| DEAX | 12-81(7) | Charitable |
| DFAX | 12-81(75) | Nursing/Rest/Residential Care (federally tax-exempt org) |
| FAAX | 12-81(10) | Agricultural Society |
| GAAX | 12-81(11) | Cemetery |
| HAAX | 12-81(13) | House of Religious Worship |
| IAAX–IGAX | 12-81(14) | Parish house, Church School, Nonprofit camp, Recreational facility, Orphan asylum, Thrift shop, Reformatory, Infirmary |
| JAAX | 12-81(15) | Houses used by officiating clergymen |
| KAAX | 12-81(16) | Hospitals |
| LAAX | 12-81(18) | Veteran's organizations |
| MAAX | 12-81(29) | American National Red Cross |
| OABX–OKMX | 12-81(2) | State Property (Administration, Child Care, Corrections, Education, Hospitals, Public Safety, Recreation, Transportation, Tribal Land, etc.) |
| PABX–PCBX | 12-20a | Private College, General Hospitals, VA Healthcare |
| SAAX/SAHX | 8-58 | Housing Authority property |

### Part 4 — Partial Exemptions on Taxable Property (Letter codes A–U)

Partial exemptions applied to otherwise taxable property (veterans, disabled, blind, economic development, farm/mechanic, renewable energy, manufacturing equipment, etc.). These use letter-based state codes A through U.

## What the Statewide GDB Actually Contains

The statewide GDB (`Connecticut_CAMA_and_Parcel_Layer`) does **not** use the official OPM alphabetic exempt codes in its `State_Use` column. Instead, it contains CAMA vendor codes (e.g., from Vision Government Solutions) where:

- **Numeric codes 100–800** generally correspond to the OPM taxable categories above
- **Numeric codes 900+** are vendor-specific codes mapping to exempt property types (municipal, church, school, cemetery, state land, etc.)
- **Alphanumeric codes** like `903V`, `MDL-01` are vendor model variants
- There are **1,796 distinct State_Use values** and **4,327 distinct State_Use_Description values** across 1,282,833 parcels — significant inconsistency across towns

Because the vendor codes are not standardized, we classify tax-exempt parcels using **keyword matching on `State_Use_Description`** rather than code ranges.

## Classification Approach

We use `State_Use_Description` keyword matching (case-insensitive) to identify exempt parcels. See `src/tax_exempt.py` for the implementation and `src/analyze_state_use.py` for a utility to audit the classification against the full dataset.
