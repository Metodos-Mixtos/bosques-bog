import geopandas as gpd


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