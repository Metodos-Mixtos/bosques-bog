import os
from pathlib import Path
from dotenv import load_dotenv

# Cargar .env desde la raíz del proyecto (2 niveles arriba: src -> dynamic_world -> bosques-bog, luego subir 1 más)
env_path = Path(__file__).parent.parent.parent.parent / "dot_env_content.env"
load_dotenv(dotenv_path=env_path)

# === Paths base ===
INPUTS_PATH = os.getenv("INPUTS_PATH")

# Validar que las variables de entorno se cargaron
if not INPUTS_PATH:
    raise ValueError(
        f"Error: Variable INPUTS_PATH no encontrada en .env\n"
        f"Buscando .env en: {env_path}\n"
        f"Verifica que el archivo existe y contiene INPUTS_PATH"
    )

AOI_DIR = os.path.join(INPUTS_PATH, "area_estudio", "dynamic_world")
OUTPUTS_BASE = os.path.join(INPUTS_PATH, "dynamic_world", "outputs")
LOGO_PATH = os.path.join(INPUTS_PATH, "Logo_SDP.jpeg")

# === Parámetros globales ===
GRID_SIZE = 10000  # metros
LOOKBACK_DAYS = 365
PROJECT_ID = os.getenv("GCP_PROJECT")
