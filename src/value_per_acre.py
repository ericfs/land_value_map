import pandas as pd

AVPA_NAME = 'Appraised_Value_Per_Acre'

def compute_value_per_acre(df):
  df[AVPA_NAME] = df['Appraised_Total'] / df['Land_Acres']
  # Explicitly convert the column to numeric, coercing errors
  df[AVPA_NAME] = pd.to_numeric(df[AVPA_NAME], errors='coerce')

def filter_value_per_acre(df):
  # Filter out rows where 'Appraised_Value_Per_Acre' is NaN or infinity
  # Replace infinite values with NaN first, then drop NaNs
  return df.replace([float('inf'), float('-inf')], pd.NA).dropna(subset=[AVPA_NAME])

def compute_capped_value_per_acre(df):
  capped_column_name = f'{AVPA_NAME}_Capped'
  percentile = df[AVPA_NAME].quantile(0.90)
  # lower_percentile = df[AVPA_NAME].quantile(0.75)
  # if lower_percentile * 10 < percentile:
  #   percentile = df[AVPA_NAME].quantile(0.90)
  df[capped_column_name] = df[AVPA_NAME].clip(upper=percentile)
  df[capped_column_name] = pd.to_numeric(df[capped_column_name], errors='coerce')