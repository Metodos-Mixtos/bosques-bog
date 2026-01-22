
from pathlib import Path
import os
import argparse

from dotenv import load_dotenv

# Cargar .env desde la raíz del proyecto (tres niveles arriba desde deforestation_PSA)
env_path = Path(__file__).parent.parent.parent.parent / "dot_env_content.env"
load_dotenv(env_path)

from deforestation_PSAH_functions import (
    select_parcel, context_map, plot_deforestation_map,
    def_anual, pick_column, ensure_dir, download_sentinel_year_pngs, fmt_ha
)

from reporte.render_report import render

#  CENTRALIZED FOLDERS (PATHS)

base_dir_str = os.getenv("BASE_PATH")
if not base_dir_str:
    raise RuntimeError("BASE_PATH no está en .env")

aoi_dir_str = os.getenv("AOI_DIR")
if not aoi_dir_str:
    raise RuntimeError("AOI_DIR no está en .env")

logo_rel_str = os.getenv("LOGO_PATH")
header_img1_rel_str = os.getenv("HEADER_IMG1")
header_img2_rel_str = os.getenv("HEADER_IMG2")
footer_img_rel_str = os.getenv("FOOTER_IMG")

BASE_DIR = Path(base_dir_str)
AOI_DIR = Path(aoi_dir_str)

# Construir rutas absolutas desde AOI_DIR
LOGO_PATH = AOI_DIR / logo_rel_str if logo_rel_str else None
HEADER_IMG1 = AOI_DIR / header_img1_rel_str if header_img1_rel_str else None
HEADER_IMG2 = AOI_DIR / header_img2_rel_str if header_img2_rel_str else None
FOOTER_IMG = AOI_DIR / footer_img_rel_str if footer_img_rel_str else None

SHP_PATH    = AOI_DIR / r"area_estudio\deforestation_reports\Shapes PSA\areas_priorizadas_psah.shp"
AOI_PATH    = AOI_DIR / r"area_estudio\deforestation_reports\bog-area-estudio.shp" 
RASTER_PATH = AOI_DIR / r"area_estudio\deforestation_reports\Hansen Colombia 2024\hansen_treecover_SDP_2024.tif"

OUTPUT_BASE_DIR = BASE_DIR / r"output"

if __name__ == "__main__":
    # === Argumentos de ejecución ===
    parser = argparse.ArgumentParser(description="Generación de reportes de deforestación - PSAH")
    parser.add_argument("--year-start", type=int, required=True, help="Año inicial del período de análisis (ej: 2018)")
    parser.add_argument("--year-end", type=int, required=True, help="Año final del período de análisis (ej: 2024)")
    parser.add_argument("--objectid", type=float, required=True, help="OBJECT ID del predio en el shapefile")
    parser.add_argument("--lot-codigo", type=str, required=True, help="Código de lote del predio")
    args = parser.parse_args()

    YEAR_START = args.year_start
    YEAR_END = args.year_end
    OBJECTID = args.objectid
    LOT_CODIGO = args.lot_codigo

    # === Carpetas de salida específicas para este reporte ===
    reporte_id = f"OBJ_{OBJECTID}_LOT_{LOT_CODIGO}_{YEAR_START}_{YEAR_END}"
    OUTPUT_DIR = OUTPUT_BASE_DIR / reporte_id
    HTML_OUTPUT = OUTPUT_DIR / "html"
    CONTEXT_OUTPUT = OUTPUT_DIR / "contexto"
    DEFMAP_OUTPUT = OUTPUT_DIR / "deforestacion"
    SENTINEL_OUTPUT = OUTPUT_DIR / "sentinel"

    for p in (OUTPUT_DIR, HTML_OUTPUT, CONTEXT_OUTPUT, DEFMAP_OUTPUT, SENTINEL_OUTPUT):
        ensure_dir(p)

    print(f"\n{'='*60}")
    print(f"🌳 GENERACIÓN DE REPORTE DE DEFORESTACIÓN - PSAH")
    print(f"{'='*60}")
    print(f"📍 OBJECT ID: {OBJECTID}")
    print(f"📍 Código de lote: {LOT_CODIGO}")
    print(f"📅 Período: {YEAR_START} - {YEAR_END}")
    print(f"📁 Carpeta de salida: {OUTPUT_DIR}")
    print(f"{'='*60}\n")

    # Seleccionar el predio
    print("1️⃣  Seleccionando predio...")
    parcel = select_parcel(SHP_PATH, OBJECTID, LOT_CODIGO)

    # Leer PREDIRECC y Area_ha del shapefile
    pred_col = pick_column(parcel, ["PREDIRECC", "PreDirecc", "predirecc", "Nombre", "NOMBRE", "nombre"])
    area_col = pick_column(parcel, ["Area_ha", "AREA_HA", "area_ha", "area", "AREA"])

    pred_name = str(parcel.iloc[0][pred_col]) if pred_col else "Predio seleccionado"
    area_val  = float(parcel.iloc[0][area_col]) if area_col else None
    print(f"   ✓ Predio: {pred_name}")
    print(f"   ✓ Área: {fmt_ha(area_val) if area_val else '—'} ha\n")

    # Cadena de identificación concatenada del predio
    lotname = f"OBJECTID={parcel.iloc[0]['OBJECTID']}, lotCodigo={parcel.iloc[0]['lotCodigo']}"

    # Mapa de contexto
    print("2️⃣  Generando mapa de contexto...")
    context_html_path = CONTEXT_OUTPUT / f"context_{OBJECTID}_{LOT_CODIGO}.html"
    context_map(parcel, str(AOI_PATH), str(context_html_path), legend_name=pred_name, scale_position="bottomleft")
    print(f"   ✓ Mapa guardado en: {context_html_path}\n")

    # Imagen mapa de deforestación
    print("3️⃣  Generando mapa de deforestación...")
    defo_png_path = plot_deforestation_map(
        str(RASTER_PATH), parcel,
        names_column="lotCodigo",
        name_of_area=lotname,
        year_start=YEAR_START, year_end=YEAR_END,
        output_folder=str(DEFMAP_OUTPUT)
    )
    print(f"   ✓ Mapa guardado en: {defo_png_path}\n")

    # Tabla de deforestación anual
    print("4️⃣  Calculando deforestación anual...")
    df_loss = def_anual(parcel, str(RASTER_PATH), year_min=YEAR_START, year_max=YEAR_END)
    if df_loss is not None and len(df_loss) > 0:
        print(f"   ✓ Se detectó pérdida de cobertura en {len(df_loss)} año(s)\n")
    else:
        print(f"   ℹ️  No se detectó pérdida de cobertura en el período\n")

    # Descargar imágenes Sentinel-2
    print("5️⃣  Descargando imágenes Sentinel-2...")
    s2_png_start, s2_png_end = download_sentinel_year_pngs(
        parcel_gdf=parcel,
        year_start=YEAR_START,
        year_end=YEAR_END,
        out_dir=str(SENTINEL_OUTPUT),
        dim=1024  # you can use 768 or 1536 if you want
    )
    print(f"   ✓ Imagen {YEAR_START}: {s2_png_start}")
    print(f"   ✓ Imagen {YEAR_END}: {s2_png_end}\n")

    # Preparar datos para el template HTML
    print("6️⃣  Generando reporte HTML...")
    title = f"Reporte de deforestación: {pred_name}"
    out_html = HTML_OUTPUT / f"reporte_{OBJECTID}_{LOT_CODIGO}_{YEAR_START}_{YEAR_END}.html"
    
    # Calcular pérdida total
    total_loss = float(df_loss["deforestation_ha"].sum()) if df_loss is not None and len(df_loss) > 0 else 0.0
    
    # Preparar datos anuales para el template
    yearly_data = []
    if df_loss is not None and len(df_loss) > 0:
        for _, row in df_loss.iterrows():
            yearly_data.append({
                "year": int(row["year"]),
                "loss_ha": fmt_ha(row["deforestation_ha"])
            })
    
    # Función auxiliar para paths relativos
    def _relpath_for_html(target_path, out_html_path):
        return os.path.relpath(str(target_path), start=os.path.dirname(str(out_html_path))).replace("\\", "/")
    
    # Construir diccionario de datos para el template
    template_data = {
        "TITLE": title,
        "PERIOD": f"{YEAR_START}–{YEAR_END}",
        "PRED_NAME": pred_name,
        "OBJECTID": str(OBJECTID),
        "LOT_CODIGO": str(LOT_CODIGO),
        "AREA_HA": fmt_ha(area_val) if area_val else "—",
        "TOTAL_LOSS": fmt_ha(total_loss),
        "YEAR_START": str(YEAR_START),
        "YEAR_END": str(YEAR_END),
        "CONTEXT_MAP": _relpath_for_html(context_html_path, out_html),
        "DEFO_MAP": _relpath_for_html(defo_png_path, out_html),
        "SENTINEL_START": _relpath_for_html(s2_png_start, out_html),
        "SENTINEL_END": _relpath_for_html(s2_png_end, out_html),
        "YEARLY_DATA": yearly_data
    }
    
    # Agregar imágenes del header y footer si existen
    if HEADER_IMG1 and HEADER_IMG1.exists():
        template_data["HEADER_IMG1"] = _relpath_for_html(HEADER_IMG1, out_html)
    else:
        template_data["HEADER_IMG1"] = ""
        
    if HEADER_IMG2 and HEADER_IMG2.exists():
        template_data["HEADER_IMG2"] = _relpath_for_html(HEADER_IMG2, out_html)
    else:
        template_data["HEADER_IMG2"] = ""
        
    if FOOTER_IMG and FOOTER_IMG.exists():
        template_data["FOOTER_IMG"] = _relpath_for_html(FOOTER_IMG, out_html)
    else:
        template_data["FOOTER_IMG"] = ""
    
    # Renderizar el template
    template_path = Path(__file__).parent / "reporte" / "report_template.html"
    render(template_path, template_data, Path(out_html))

    print(f"   ✓ Reporte HTML generado\n")
    print(f"{'='*60}")
    print(f"✅ PROCESO COMPLETADO EXITOSAMENTE")
    print(f"{'='*60}")
    print(f"📄 Reporte HTML: {out_html}")
    print(f"📁 Todos los archivos en: {OUTPUT_DIR}")
    print(f"{'='*60}\n")




