import os
from dotenv import load_dotenv
import planet
from planet import Auth
import requests
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import planet_functions as pf

import imageio
import rasterio
import numpy as np

# Load environment variables
load_dotenv()

PLANET_API_KEY = os.getenv("PLANET_API_KEY")
PLANET_USER = os.getenv("PLANET_USER")
PLANET_PASS = os.getenv("PLANET_PASS")

# Folder for data
data_folder = '/Users/Daniel/Library/CloudStorage/OneDrive-VestigiumMétodosMixtosAplicadosSAS/geoinfo/Colombia/Bogotá/bosques_bogota'

# Load alerts from GeoJSON
alerts_path = '/Users/Daniel/Library/CloudStorage/OneDrive-VestigiumMétodosMixtosAplicadosSAS/MMC - General - SDP - Monitoreo de Bosques/monitoreo_bosques/temp_data/alertas_gfw.geojson'
alerts_gdf = gpd.read_file(alerts_path)

# Authenticate with Planet API
planet.Auth.from_login(PLANET_USER, PLANET_PASS)

# Setup session
session = requests.Session()
session.auth = (PLANET_API_KEY, "")

# Function to download Sentinel images based on alert locations
def download_sentinel_images(alerts_gdf, save_dir):
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)

    for index, row in alerts_gdf.iterrows():
        # Extract coordinates and date
        coords = row['geometry']['coordinates']
        alert_date = row['properties']['gfw_integrated_alerts__date']
        
        # Create a point geometry for the alert
        point = Point(coords[0], coords[1])
        
        # Define the area of interest (AOI) as a buffer around the point
        aoi = point.buffer(0.1)  # 0.1 degrees ~ 10 km
        
        # Define parameters for downloading images
        asset_name = 'your_asset_name_here'  # Replace with actual asset name
        year = alert_date.split('-')[0]
        month = alert_date.split('-')[1]
        file_name = f'{year}_{month}_{index}'
        
        # Download the images
        pf.download_planet_images(asset_name, 
                                  aoi, 
                                  save_dir, 
                                  file_name, 
                                  aoi.crs, 
                                  session)

# Download Sentinel images for the alerts
download_sentinel_images(alerts_gdf, os.path.join(data_folder, 'planet/imagenes_temporal/'))

# Continue with the rest of your analysis...