# This module is used to group CAMA and Parcel data layers together for each town in a GDB file.

import fiona
import re
from town_name import normalize_town_name

def list_layers_in_gdb(gdb_path):
    try:
        # List the layers in the GDB
        layers = fiona.listlayers(gdb_path)
    except Exception as e:
        print(f"An error occurred while listing layers: {e}")
        layers = []
    return layers

cama_layer_re = re.compile(r'^([\w\s_]+)_\d{4}_CAMA$', re.IGNORECASE)
parcels_layer_re = re.compile(r'^([\w\s_]+)_Parcels$', re.IGNORECASE)

def first_group(pattern, string):
    match = pattern.match(string)
    return match.group(1) if match else None

class TownLayers:
  def __init__(self, cama_layer_name, parcels_layer_name):
    self.cama_layer_name = cama_layer_name
    self.parcels_layer_name = parcels_layer_name
    name_from_cama = first_group(cama_layer_re, cama_layer_name)
    name_from_parcels = first_group(parcels_layer_re, parcels_layer_name)
    if name_from_cama and name_from_parcels:
      self.town_name = name_from_parcels if normalize_town_name(name_from_cama) == normalize_town_name(name_from_parcels) else None
    else:
      self.town_name = None
    if self.town_name:
      self.town_name = self.town_name.replace('_', ' ')

  def __str__(self):
    return f"Town: {self.town_name}, CAMA Layer: {self.cama_layer_name}, Parcels Layer: {self.parcels_layer_name}"

def layer_list_to_town_layers(layers):
  cama_layers = { normalize_town_name(first_group(cama_layer_re, layer)): layer
                 for layer in layers if cama_layer_re.match(layer) }
  parcels_layers = { normalize_town_name(first_group(parcels_layer_re, layer)): layer
                    for layer in layers if parcels_layer_re.match(layer) }
  town_layers = [TownLayers(cama_layers[name], parcels_layers[name])
                  for name in cama_layers if name in parcels_layers]
  if len(layers) != len(town_layers) * 2:
    print(f'layers != town_layers * 2. layers: {len(layers)} town_layers: {len(town_layers)}')
    print_missing_layers(layers, town_layers)
  return town_layers

def print_missing_layers(layers, town_layers):
  found_layers = []
  found_layers.extend(
      [town_layer.cama_layer_name for town_layer in town_layers]
  )
  found_layers.extend(
      [town_layer.parcels_layer_name for town_layer in town_layers]
  )
  missing_layers = [layer for layer in layers if layer not in found_layers]
  print(f'Missing layers: {missing_layers}')


def gdb_to_town_layers(gdb_path):
  layers = list_layers_in_gdb(gdb_path)
  return layer_list_to_town_layers(layers)