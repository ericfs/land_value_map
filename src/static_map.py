import matplotlib.pyplot as plt
import contextily as cx

def render_map(df, town_name, filename):
  fig, ax = plt.subplots(1, 1, figsize=(30, 30))

  # Use a color map (cmap) and specify the column to color by
  # 'legend=True' will display a color bar
  df.plot(column='Appraised_Value_Per_Acre_Capped', ax=ax, legend=True, cmap='plasma')

  # Optional: Add a title
  ax.set_title(f'Appraised Value Per Acre by Parcel: {town_name}')

  # Optional: Turn off axis
  ax.set_axis_off()
  cx.add_basemap(ax, crs=df.crs, zoom=14)

  plt.savefig(filename)