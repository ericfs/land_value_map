import os

PLOT_PATH = 'plot'
GEOJSON_PATH = 'geojson'

LAYER_MISPELLINGS = {
  'startford': 'stratford',
  'barkhamstead': 'barkhamsted',
}

def normalize_town_name(town_name):
  town_name = town_name.lower()
  if town_name in LAYER_MISPELLINGS:
    return LAYER_MISPELLINGS[town_name]
  return town_name

def town_name_to_file_name(base_path, town_name, is_image = False):
  if is_image:
    return os.path.join(base_path, PLOT_PATH, f'{town_name}.png')
  else:
    return os.path.join(base_path, GEOJSON_PATH, f'{town_name}.geojson')