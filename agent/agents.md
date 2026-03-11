The purpose of this project is compute and map the land value per acre of every parcel in the state of Connecticut. The data is from https://data.ct.gov/Local-Government/2024-Connecticut-Parcel-and-CAMA-Data/pqrn-qghw/about_data and is available in the inputs/ directory.

# Inputs

## inputs/Parcel Collection 2024/Parcel_By_COG

This directory contains a directory for each Council of Government (COG) in Connecticut. Each COG directory contains a Geodatabase directory.
The Geodatabase (GDB) should contain two tables for each town in the COG. One table should contain the parcel data, which includes the geometry.
The other table includes assessment data about the parcels. In order to display the land value per acre on a map, the two tables need to be joined together for each town.

## inputs/Metadata.csv

This file is a table that contains a row for each town in Connecticut. It contains the columns "Link Field for CAMA" and "Link Field for Parcels". This column should contain the name of the field in the CAMA and Parcel tables that can be used to join the two tables, but for some towns, the data is incorrect.

# Challenge

The challenge is to figure out how to correctly join the two tables for each town in Connecticut. A correct join will be close to a 1:1 mapping of the two tables. If there are more than a few multiple matches, the join is definitely incorrect. If few matches are found, it's probably incorrect.

It is important to use heuristics to check whether the join looks correct. For example, there may be an address field in both tables. It may not be suitable as a join key due to formatting differences, but it could be used to validate that the join *looks* correct. Another heuristic could be to find parcel area fields in both tables and check that they are close to equal. There may be other heuristics I have not mentioned.

It may also be necessary to use compound join keys. For example, one table may need to concatenate two fields in order to join with the other table.

# Process

As you evalute the best solution to this problem. Take notes as you go. Also create a file that stores the correct join keys for each town.