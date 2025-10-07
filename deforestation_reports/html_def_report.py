
from pathlib import Path
import os

from dotenv import load_dotenv

# load .env 
load_dotenv()

from deforestation_PSAH_functions import (
    select_parcel, context_map, plot_deforestation_map,
    def_anual, build_html_report, pick_column, ensure_dir, download_sentinel_year_pngs
)

#  CENTRALIZED FOLDERS (PATHS)

base_dir_str = os.getenv("BASE_DIR")
if not base_dir_str:
    raise RuntimeError("BASE_DIR no está en .env")

BASE_DIR = Path(base_dir_str)

SHP_PATH    = BASE_DIR / r"Shapes PSA\areas_priorizadas_psah.shp"
AOI_PATH    = BASE_DIR / r"AOI-Bogota-Colombia\bog-area-estudio.shp"  # optional
RASTER_PATH = BASE_DIR / r"Hansen Colombia 2024\hansen_treecover_SDP_2024.tif"
LOGO_PATH   = BASE_DIR / r"Logo_SDP.jpeg"

OUTPUT_DIR      = BASE_DIR / r"output"
HTML_OUTPUT     = OUTPUT_DIR / r"reportes_html"
CONTEXT_OUTPUT  = OUTPUT_DIR / r"Mapas\Mapas_contexto"
DEFMAP_OUTPUT   = OUTPUT_DIR / r"Mapas\Mapas_deforestación"
SENTINEL_OUTPUT = OUTPUT_DIR / r"Sentinel"

for p in (OUTPUT_DIR, HTML_OUTPUT, CONTEXT_OUTPUT, DEFMAP_OUTPUT, SENTINEL_OUTPUT):
    ensure_dir(p)

# INPUTS
YEAR_START       = 2018
YEAR_END         = 2024
OBJECTID         = 138.0
LOT_CODIGO       = "102114000029"

if __name__ == "__main__":

    # Seleccionar el predio
    parcel = select_parcel(SHP_PATH, OBJECTID, LOT_CODIGO)

    # Leer PREDIRECC y Area_ha del shapefile
    pred_col = pick_column(parcel, ["PREDIRECC", "PreDirecc", "predirecc", "Nombre", "NOMBRE", "nombre"])
    area_col = pick_column(parcel, ["Area_ha", "AREA_HA", "area_ha", "area", "AREA"])

    pred_name = str(parcel.iloc[0][pred_col]) if pred_col else "Predio seleccionado"
    area_val  = float(parcel.iloc[0][area_col]) if area_col else None

    # Cadena de identificación concatenada del predio
    lotname = f"OBJECTID={parcel.iloc[0]['OBJECTID']}, lotCodigo={parcel.iloc[0]['lotCodigo']}"

    # Mapa de contexto
    context_html_path = CONTEXT_OUTPUT / f"context_{OBJECTID}_{LOT_CODIGO}.html"
    context_map(parcel, str(AOI_PATH), str(context_html_path), legend_name=pred_name, scale_position="bottomleft")



    # Imagen mapa de deforestación
    defo_png_path = plot_deforestation_map(
        str(RASTER_PATH), parcel,
        names_column="lotCodigo",
        name_of_area=lotname,
        year_start=YEAR_START, year_end=YEAR_END,
        output_folder=str(DEFMAP_OUTPUT)
    )

    # Tabla de deforestación anual
    df_loss = def_anual(parcel, str(RASTER_PATH), year_min=YEAR_START, year_max=YEAR_END)

    # Descargar imágenes Sentinel-2
    s2_png_start, s2_png_end = download_sentinel_year_pngs(
    parcel_gdf=parcel,
    year_start=YEAR_START,
    year_end=YEAR_END,
    out_dir=str(SENTINEL_OUTPUT),
    dim=1024  # you can use 768 or 1536 if you want
    )

    # HTML final

    title = f"{pred_name} (OBJECT ID: {OBJECTID} - Código de lote: {LOT_CODIGO})"
    out_html = HTML_OUTPUT / f"reporte_{OBJECTID}_{LOT_CODIGO}_{YEAR_START}_{YEAR_END}.html"

    build_html_report(
        title_text=title,
        logo_path=str(LOGO_PATH),          
        red_hex="#E40F2E",
        context_map_html=str(context_html_path),
        defo_png=str(defo_png_path),
        df_yearly=df_loss,
        out_html=str(out_html),
        period_text=f"{YEAR_START}–{YEAR_END}",
        summary_area_ha=area_val,
        pred_name=pred_name,
        objectid_val=OBJECTID,
        lotcodigo_val=LOT_CODIGO,
        sentinel_png_start=s2_png_start,
        sentinel_png_end=s2_png_end
    )

    print(f"\n✓ Done. Open:\n{out_html}\n")



