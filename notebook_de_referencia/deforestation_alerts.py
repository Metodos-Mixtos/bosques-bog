import requests
import geopandas as gpd
import json
import math
from shapely.geometry import mapping
from datetime import datetime, timedelta


###############################################################################
# 1) CONFIGURATION
###############################################################################

# Path to your AOI shapefile:
SHAPEFILE_PATH = "/Users/Daniel/Library/CloudStorage/OneDrive-VestigiumMétodosMixtosAplicadosSAS/geoinfo/Colombia/Bogotá/bosques_bogota/area_estudio_mpios/bog-area-estudio.shp"

# ArcGIS FeatureServer endpoint for RADD alerts (2024 version):
RADD_ARCGIS_URL = (
    "https://services2.arcgis.com/g8WusZB13b9OegfU/arcgis/rest/services/"
    "wur_radd_alerts_2024/FeatureServer/0/query"
)

# Field name that stores the encoded RADD values (check the layer's fields):
# Often it might be "radd_alert" or simply "PixelValue". Adjust as needed.
RADD_FIELD_NAME = "PixelValue"

# We will fetch only *some* attributes. If you want all, set outFields="*"
# or list specific fields like "PixelValue, some_other_field".
OUT_FIELDS = "*"


###############################################################################
# 2) LOAD & PREP THE SHAPEFILE (AOI)
###############################################################################
def load_aoi(shapefile_path):
    """
    Loads the shapefile with geopandas, projects to EPSG:4326, 
    and returns the unified geometry (MultiPolygon or Polygon).
    """
    gdf = gpd.read_file(shapefile_path)
    # Ensure it's in WGS84 lat/lon
    gdf = gdf.to_crs(epsg=4326)
    # Merge all features into one geometry (union)
    return gdf.unary_union


def shapely_to_arcgis_polygon(shapely_geom):
    """
    Convert a (Multi)Polygon shapely geometry to ArcGIS JSON
    that can be used for the 'geometry' parameter in an ArcGIS REST query.
    """
    # ArcGIS expects a dict with "rings" for polygons:
    # {
    #   "rings": [[[x1, y1], [x2, y2], ...]],
    #   "spatialReference": {"wkid": 4326}
    # }
    #
    # If we have a MultiPolygon, we can just combine all exteriors as separate rings.

    if shapely_geom.geom_type == "Polygon":
        rings = [list(shapely_geom.exterior.coords)]
        return {
            "rings": rings,
            "spatialReference": {"wkid": 4326}
        }

    elif shapely_geom.geom_type == "MultiPolygon":
        # Combine exteriors of each polygon as separate rings
        all_rings = []
        for poly in shapely_geom.geoms:
            all_rings.append(list(poly.exterior.coords))
        return {
            "rings": all_rings,
            "spatialReference": {"wkid": 4326}
        }

    else:
        raise ValueError(f"Geometry type {shapely_geom.geom_type} is not supported.")


###############################################################################
# 3) ARCGIS QUERY FOR RADD ALERTS
###############################################################################
def query_radd_alerts(arcgis_url, aoi_geom, out_fields="*", where="1=1"):
    """
    Query the ArcGIS FeatureServer for RADD alerts intersecting the given geometry.
    
    :param arcgis_url:  The FeatureServer URL
    :param aoi_geom:    ArcGIS JSON geometry dict
    :param out_fields:  e.g. "*" or comma-separated field list
    :param where:       Additional WHERE clause (e.g., "1=1")
    :return:            FeatureCollection (GeoJSON) as a Python dict
    """
    params = {
        "geometry":      json.dumps(aoi_geom),           # geometry in ArcGIS JSON
        "geometryType":  "esriGeometryPolygon",
        "spatialRel":    "esriSpatialRelIntersects",     # returns features that intersect
        "outFields":     out_fields,                     # which fields to retrieve
        "where":         where,                          # basic filter
        "f":             "geojson",                      # return format
        "inSR":          "4326",                         # input geometry sr
        "outSR":         "4326",                         # output geometry sr
    }
    
    response = requests.get(arcgis_url, params=params)
    response.raise_for_status()
    return response.json()


###############################################################################
# 4) DECODE RADD ALERT DATE & CONFIDENCE
###############################################################################
def decode_radd_value(value):
    """
    The RADD pixel encoding is:
      - Leading digit 2 or 3 => confidence (2=low, 3=high).
      - Following digits => days since Dec 31, 2014.
      - 0 => no alert.

    Example: 30055 => '3' => high confidence, '0055' => 55 days after 2014-12-31 
    => 2015-02-24

    Returns a tuple: (date_obj, confidence_str) or (None, None) if value==0.
    """
    if value == 0:
        return (None, None)

    str_val = str(value)
    # Leading digit = 2 or 3
    confidence_digit = str_val[0]
    days_str = str_val[1:]  # all but the first character

    if confidence_digit not in ["2", "3"]:
        # Unexpected format, treat as no alert
        return (None, None)

    confidence_level = "high" if confidence_digit == "3" else "low"

    # Convert days since 2014-12-31
    # If "days_str" has leading zeros, e.g. "0055", int() will handle it.
    days_since = int(days_str)

    base_date = datetime(2014, 12, 31)
    alert_date = base_date + timedelta(days=days_since)

    return (alert_date, confidence_level)


###############################################################################
# 5) MAIN SCRIPT
###############################################################################
if __name__ == "__main__":

    # --------------------------------------------------------------------------
    # A) Load the AOI shapefile and build the ArcGIS geometry
    # --------------------------------------------------------------------------
    print(f"Loading AOI from '{SHAPEFILE_PATH}'...")
    aoi_union = load_aoi(SHAPEFILE_PATH)
    arcgis_geom = shapely_to_arcgis_polygon(aoi_union)

    # --------------------------------------------------------------------------
    # B) Query the server for RADD features that intersect the AOI
    #    (We do not filter date on the server, because RADD date is encoded)
    # --------------------------------------------------------------------------
    print("Querying the RADD ArcGIS FeatureServer... (this may take a moment)")
    geojson_resp = query_radd_alerts(
        arcgis_url=RADD_ARCGIS_URL,
        aoi_geom=arcgis_geom,
        out_fields=OUT_FIELDS,
        where="1=1"
    )

    # The response is a FeatureCollection in GeoJSON format
    features = geojson_resp.get("features", [])
    print(f"Total features returned: {len(features)}")

    # --------------------------------------------------------------------------
    # C) Filter to the last 30 days, decode date & confidence
    # --------------------------------------------------------------------------
    cutoff_date = datetime.utcnow() - timedelta(days=30)
    filtered_features = []

    for feat in features:
        props = feat.get("properties", {})
        encoded_val = props.get(RADD_FIELD_NAME, 0)  # e.g. 30055, 21847, etc.

        alert_date, confidence = decode_radd_value(encoded_val)
        if alert_date is not None and alert_date >= cutoff_date:
            # If you want to keep the decoded date & confidence in the properties:
            props["alert_date"] = alert_date.isoformat()
            props["confidence"] = confidence
            filtered_features.append(feat)

    print(f"Number of alerts in the last 30 days: {len(filtered_features)}")

    # --------------------------------------------------------------------------
    #Convert them to a GeoDataFrame or save to file:
    gdf_radd = gpd.GeoDataFrame.from_features(filtered_features, crs="EPSG:4326")
    gdf_radd.to_file("temp_data/ radd_alerts_last_30_days.shp")

    print("Done!")
