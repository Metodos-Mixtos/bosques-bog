import geopandas as gpd
import os
import pandas as pd
import requests
import urllib.request


def get_bounding_box_string(input_data, original_crs, output_crs=None):
    """
    Returns the bounding box coordinates of a GeoDataFrame or a raw geometry in string format separated by commas.
    
    Parameters:
    - input_data: GeoDataFrame or raw geometry whose bounding box will be computed.
    - output_crs: (Optional) EPSG code for the desired output CRS. If not provided, the original CRS of the input_data is used.
    
    Returns:
    - str: Bounding box coordinates in the format "minx, miny, maxx, maxy".
    """
    
    # Check if input_data is a GeoDataFrame
    if isinstance(input_data, gpd.GeoDataFrame):
        gdf = input_data
    # Check if input_data is a raw geometry (e.g., shapely geometry)
    elif hasattr(input_data, 'bounds'):
        gdf = gpd.GeoSeries([input_data], crs=original_crs)
    else:
        raise ValueError("The input_data should be a GeoDataFrame or a raw geometry.")
    
    # Reproject the GeoDataFrame if an output CRS is provided
    if output_crs:
        gdf = gdf.to_crs(output_crs)
    
    # Compute the bounding box
    bbox = gdf.total_bounds
    bbox_string = ','.join(map(str, bbox))
    
    return bbox_string

def extract_after_word(text, word, x):
    """
    Extracts x number of characters after a specified word in the given text.
    
    Parameters:
    - text (str): The input string from which characters need to be extracted.
    - word (str): The word after which characters will be extracted.
    - x (int): Number of characters to be extracted after the word.
    
    Returns:
    - str: Extracted characters. If the word isn't found or there aren't enough characters after the word, an appropriate message is returned.
    """
    
    try:
        position = text.index(word) + len(word)
        return text[position: position + x].strip()
    except ValueError:
        return "The word '{}' was not found in the given text.".format(word)
    except:
        return "There aren't enough characters after the word '{}'.".format(word)

def get_mosaic_id(mosaic_name, session):
    """
    Retrieves the mosaic ID, bounding box, and coordinate reference system (CRS) of a mosaic 
    from the Planet Basemaps API based on the mosaic name.
    
    Args:
        mosaic_name (str): The name of the mosaic for which to retrieve the metadata.

    Returns:
        str: The ID of the mosaic.
    
    Raises:
        requests.RequestException: If there is an error in fetching the mosaic data from the API.
        KeyError: If the expected fields are missing from the API response.
    
    Workflow:
        1. Sends a GET request to the Planet Basemaps API using the mosaic name as a search parameter.
        2. Parses the API response to extract the mosaic ID, bounding box, and coordinate system.
        3. Returns the mosaic ID as the output.
    
    Example:
        mosaic_id = get_mosaic_id("analytic_mosaic_name")
    """

    #setup Planet base URL
    API_URL = "https://api.planet.com/basemaps/v1/mosaics"
    
    # Step 1: Set parameters for the API request using the mosaic name
    parameters = {
        "name__is": mosaic_name
    }

    # Step 2: Make a GET request to the Planet Basemaps API to search for the mosaic
    res = session.get(API_URL, params=parameters)
    
    # Step 3: Parse the API response to extract mosaic metadata
    mosaic = res.json()
    
    # Step 4: Extract the mosaic ID, bounding box, and CRS from the response
    mosaic_id = mosaic['mosaics'][0]['id']
    mosaic_bbox = mosaic['mosaics'][0]['bbox']
    mosaic_crs = mosaic['mosaics'][0]['coordinate_system']
    
    # Convert bounding box to a string format (this can be used for further requests if needed)
    string_bbox = ','.join(map(str, mosaic_bbox))
    
    # Step 5: Return the mosaic ID
    return mosaic_id

def download_planet_images(mosaic_name, polygon, save_dir, file_name, original_crs, session):
    """
    Downloads a Planet quad image from a specific mosaic using a polygon (area of interest), 
    saves it to a specified directory.
    
    Args:
        mosaic_name (str): The name of the Planet mosaic from which the quad will be downloaded.
        polygon (object): The polygon (area of interest) used to define the region to download the quad from.
        save_dir (str): The directory where the downloaded image will be saved.
        file_name (str): The base name for the saved file.
        original_crs (str): The coordinate reference system (CRS) of the input polygon.
    
    Returns:
        str: The full path to the saved image file.

    Raises:
        requests.RequestException: If there is an error in fetching the mosaic data from the API.
        KeyError: If the expected fields are missing from the API response.

    Workflow:
        1. Fetches the bounding box string for the polygon in the WGS84 CRS.
        2. Sends a request to the Planet API to retrieve the mosaic quads based on the polygon area.
        3. Downloads the first quad available for the specified mosaic.
        4. Saves the downloaded image to the specified directory with a constructed file name.
        
    Example:
        download_planet_images(
            mosaic_name="analytic_mosaic_name",
            polygon=my_polygon,
            save_dir="/path/to/save",
            file_name="planet_image",
            original_crs="EPSG:4326",
            inicio_fin="inicio"
        )
    """

    #setup Planet base URL
    API_URL = "https://api.planet.com/basemaps/v1/mosaics"
    
    # Step 1: Generate a bounding box string for the area of interest
    bbox = get_bounding_box_string(polygon, original_crs, 'WGS84')
    
    search_parameters = {
        'bbox': bbox,
        'minimal': True
    }
    
    # Step 2: Retrieve the mosaic ID based on the mosaic name
    mosaic_id = get_mosaic_id(mosaic_name, session)

    # Step 3: Construct the URL for accessing the mosaic quads
    quads_url = "{}/{}/quads".format(API_URL, mosaic_id)

    # Step 4: Send a request to the API to fetch mosaic quads
    res = session.get(quads_url, params=search_parameters, stream=True)
    quads = res.json()
    items = quads['items']
    
    # Step 5: Extract the download link for the first quad item
    link = items[0]['_links']['download']
    
    # Step 6: Construct the file name
    name = file_name + '_' + extract_after_word(mosaic_name, 'analytic_', 7) + '_'
    
    name += '.tiff'

    # Step 7: Ensure the save directory exists
    DIR = os.path.join(save_dir, file_name) 
    os.makedirs(DIR, exist_ok=True)
    
    # Step 8: Download and save the image file
    filename = os.path.join(DIR, name)
    urllib.request.urlretrieve(link, filename)
    
    # Return the full path to the saved file
    
    return filename