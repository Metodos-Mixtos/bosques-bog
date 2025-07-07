import os
import json
import requests
import geopandas as gpd
import pandas as pd
from shapely.geometry import Point
import planet_functions as pf

# Load the GeoJSON file
geojson_path = '/Users/Daniel/Library/CloudStorage/OneDrive-VestigiumMétodosMixtosAplicadosSAS/MMC - General - SDP - Monitoreo de Bosques/monitoreo_bosques/temp_data/alertas_gfw.geojson'

with open(geojson_path) as f:
    geojson_data = json.load(f)

# Convert GeoJSON to GeoDataFrame
features = geojson_data['features']
alert_data = []

for feature in features:
    properties = feature['properties']
    geometry = feature['geometry']['coordinates']
    alert_data.append({
        'latitude': properties['latitude'],
        'longitude': properties['longitude'],
        'date': properties['gfw_integrated_alerts__date'],
        'confidence': properties['gfw_integrated_alerts__confidence'],
        'geometry': Point(geometry[0], geometry[1])
    })

# Create a GeoDataFrame from the alerts
alerts_gdf = gpd.GeoDataFrame(alert_data, geometry='geometry', crs="EPSG:4326")

# Folder for saving downloaded images
data_folder = '/Users/Daniel/Library/CloudStorage/OneDrive-VestigiumMétodosMixtosAplicadosSAS/geoinfo/Colombia/Bogotá/bosques_bogota/planet/imagenes_temporal/'

# Iterate through each alert and download Sentinel imagery
for index, row in alerts_gdf.iterrows():
    asset_name = f"sentinel_image_{index}"  # Placeholder for asset name
    year = row['date'][:4]  # Extract year from date
    month = row['date'][5:7]  # Extract month from date
    save_dir = os.path.join(data_folder, f'{year}_{month}/')
    
    # Create directory if it doesn't exist
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    
    # Define the filename
    file_name = f'{year}_{month}_{row["latitude"]}_{row["longitude"]}'
    
    # Download the Sentinel images
    pf.download_planet_images(asset_name, 
                              row['geometry'], 
                              save_dir, 
                              file_name, 
                              'EPSG:4326', 
                              session)

    print(f"Downloaded images for alert at {row['latitude']}, {row['longitude']} on {row['date']}")