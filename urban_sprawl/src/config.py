import os
from dotenv import load_dotenv
from pathlib import Path

# Load .env file from the root of the project (3 levels up from this file: src -> urban_sprawl -> bosques-bog -> root)
env_path = Path(__file__).parent.parent.parent.parent / "dot_env_content.env"

# Check if the .env file exists
if not env_path.exists():
    raise FileNotFoundError(f"Environment file not found at: {env_path}")

load_dotenv(env_path)

# === Paths base ===
BASE_PATH = os.getenv("INPUTS_PATH")
if BASE_PATH is None:
    raise ValueError(f"INPUTS_PATH not found in environment file: {env_path}")

GOOGLE_CLOUD_PROJECT = os.getenv("GCP_PROJECT")
if GOOGLE_CLOUD_PROJECT is None:
    raise ValueError(f"GCP_PROJECT not found in environment file: {env_path}")

# === Archivos de entrada ===
AOI_PATH = os.path.join(BASE_PATH, "area_estudio", "urban_sprawl", "aestudio_bogota.geojson")
LOGO_PATH = os.path.join(BASE_PATH, "Logo_SDP.jpeg")
SAC_PATH = os.path.join(BASE_PATH, "area_estudio", "urban_sprawl", "situacion_amb_conflictiva.geojson")
RESERVA_PATH = os.path.join(BASE_PATH, "area_estudio", "urban_sprawl", "reserva_cerrosorientales.geojson")
EEP_PATH = os.path.join(BASE_PATH, "area_estudio", "urban_sprawl", "estructuraecologicaprincipal", "EstructuraEcologicaPrincipal.shp")
UPL_PATH = os.path.join(BASE_PATH, "area_estudio", "urban_sprawl", "unidadplaneamientolocal", "UnidadPlaneamientoLocal.shp")

