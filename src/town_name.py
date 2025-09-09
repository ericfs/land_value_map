LAYER_MISPELLINGS = {
  'startford': 'stratford',
  'barkhamstead': 'barkhamsted',
}

def normalize_town_name(town_name):
  town_name = town_name.lower()
  if town_name in LAYER_MISPELLINGS:
    return LAYER_MISPELLINGS[town_name]
  return town_name