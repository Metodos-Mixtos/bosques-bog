#!/usr/bin/env python3
"""
Script para regenerar mapas HTML de GFW cuando los tiles de Earth Engine o Sentinel han expirado.
Este script NO recalcula datos de alertas, solo regenera los mapas interactivos con nuevos tokens.

Uso:
    python gfw_alerts/src/regenerate_maps.py --trimestre II --anio 2025
    python gfw_alerts/src/regenerate_maps.py --trimestre II --anio 2025 --force
    python gfw_alerts/src/regenerate_maps.py --all  # Regenerar todos los trimestres
"""

import argparse
import os
import sys
from pathlib import Path
import re
import requests
import geopandas as gpd
import ee

# Agregar directorio raíz al path
SCRIPT_DIR = Path(__file__).parent
ROOT_DIR = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from dotenv import load_dotenv

# Cargar .env
env_path = SCRIPT_DIR.parent.parent.parent / "dot_env_content.env"
load_dotenv(dotenv_path=env_path)

from gfw_alerts.src.maps import plot_alerts_interactive, plot_sentinel_cluster_interactive
from gfw_alerts.reporte.render_report import render


def check_tile_expiration(html_path: str) -> bool:
    """
    Verifica si los tiles de un mapa HTML han expirado intentando acceder a una URL de tile.
    
    Returns:
        True si los tiles han expirado o no se puede verificar
        False si los tiles aún son válidos
    """
    if not os.path.exists(html_path):
        print(f"  ⚠️ El archivo {html_path} no existe")
        return True
    
    try:
        with open(html_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Buscar URLs de tiles de Earth Engine
        pattern = r'https://earthengine[^"\']*googleapis\.com/[^"\']*'
        tile_urls = re.findall(pattern, content)
        
        if not tile_urls:
            print("  ℹ️ No se encontraron URLs de Earth Engine tiles")
            return True
        
        # Probar la primera URL encontrada
        test_url = tile_urls[0]
        # Modificar para probar un tile específico (zoom/x/y)
        test_url = test_url.replace('{z}', '10').replace('{x}', '285').replace('{y}', '490')
        
        print(f"  🔍 Verificando validez de tiles...")
        response = requests.head(test_url, timeout=10)
        
        if response.status_code == 200:
            print("  ✅ Los tiles aún son válidos")
            return False
        else:
            print(f"  ⚠️ Los tiles han expirado (código: {response.status_code})")
            return True
            
    except Exception as e:
        print(f"  ⚠️ Error al verificar tiles: {e}")
        return True


def get_trimestre_dates(trimestre: str, anio: int):
    """Obtiene el rango de fechas para un trimestre."""
    trimestres = {
        "I": ("01-01", "03-31"),
        "II": ("04-01", "06-30"),
        "III": ("07-01", "09-30"),
        "IV": ("10-01", "12-31")
    }
    
    if trimestre.upper() not in trimestres:
        raise ValueError(f"Trimestre inválido: {trimestre}. Use I, II, III o IV")
    
    inicio, fin = trimestres[trimestre.upper()]
    return f"{anio}-{inicio}", f"{anio}-{fin}"


def regenerate_for_trimestre(trimestre: str, anio: int, force: bool = False):
    """
    Regenera mapas y reporte para un trimestre específico.
    
    Args:
        trimestre: Trimestre en formato I, II, III o IV
        anio: Año (YYYY)
        force: Si True, regenera sin verificar expiración
    """
    print(f"\n{'='*60}")
    print(f"🗓️  Regenerando mapas para Trimestre {trimestre} de {anio}")
    print(f"{'='*60}\n")
    
    # Obtener variables de entorno
    ONEDRIVE_PATH = os.getenv("ONEDRIVE_PATH")
    INPUTS_PATH = os.getenv("INPUTS_PATH")
    GCP_PROJECT = os.getenv("GCP_PROJECT")
    
    if not all([ONEDRIVE_PATH, INPUTS_PATH, GCP_PROJECT]):
        print("❌ Error: Variables de entorno no configuradas correctamente")
        print("   Asegúrate de tener ONEDRIVE_PATH, INPUTS_PATH y GCP_PROJECT en .env")
        return False
    
    # Construir rutas
    fecha_rango = f"{trimestre}_trim_{anio}"
    OUTPUT_FOLDER = os.path.join(ONEDRIVE_PATH, "outputs", fecha_rango)
    SENTINEL_IMAGES_PATH = os.path.join(OUTPUT_FOLDER, "sentinel_imagenes")
    MAP_OUTPUT_PATH = os.path.join(OUTPUT_FOLDER, f"alertas_mapa_{fecha_rango}.html")
    JSON_FINAL_PATH = os.path.join(OUTPUT_FOLDER, "reporte_final.json")
    REPORT_HTML_PATH = Path(OUTPUT_FOLDER) / "reporte_final.html"
    
    # Rutas de inputs
    POLYGON_PATH = os.path.join(INPUTS_PATH, "area_estudio", "gfw", "area_estudio_mpios", "bog-area-estudio.shp")
    ALERTS_GEOJSON_PATH = os.path.join(OUTPUT_FOLDER, f"alertas_gfw_{fecha_rango}.geojson")  # Todas las alertas
    DF_ANALYSIS_PATH = os.path.join(OUTPUT_FOLDER, f"alertas_gfw_analisis_{fecha_rango}.geojson")  # Solo highest con clusters
    TEMPLATE_PATH = SCRIPT_DIR.parent / "reporte" / "report_template.html"
    
    # Verificar que existen los datos necesarios
    if not os.path.exists(OUTPUT_FOLDER):
        print(f"❌ Error: No se encontró el directorio de salidas")
        print(f"   Primero debes ejecutar el análisis completo con:")
        print(f"   python gfw_alerts/main.py --trimestre {trimestre} --anio {anio}")
        return False
    
    if not os.path.exists(ALERTS_GEOJSON_PATH):
        print(f"❌ Error: No se encontró el archivo de alertas")
        print(f"   Archivo esperado: {ALERTS_GEOJSON_PATH}")
        return False
    
    if not os.path.exists(DF_ANALYSIS_PATH):
        print(f"❌ Error: No se encontró el archivo de análisis de alertas")
        print(f"   Archivo esperado: {DF_ANALYSIS_PATH}")
        return False
    
    # Verificar si necesita regeneración (a menos que se fuerce)
    needs_regen_main = True
    needs_regen_sentinel = True
    
    if not force:
        print("🔍 Verificando estado de los tiles...\n")
        
        # Verificar mapa principal
        if os.path.exists(MAP_OUTPUT_PATH):
            print(f"📍 Mapa principal: {os.path.basename(MAP_OUTPUT_PATH)}")
            needs_regen_main = check_tile_expiration(MAP_OUTPUT_PATH)
        
        # Verificar mapas Sentinel
        if os.path.exists(SENTINEL_IMAGES_PATH):
            sentinel_maps = [f for f in os.listdir(SENTINEL_IMAGES_PATH) if f.endswith('.html')]
            if sentinel_maps:
                print(f"\n📍 Mapas Sentinel: {len(sentinel_maps)} encontrados")
                # Probar el primero
                first_sentinel = os.path.join(SENTINEL_IMAGES_PATH, sentinel_maps[0])
                needs_regen_sentinel = check_tile_expiration(first_sentinel)
        
        if not needs_regen_main and not needs_regen_sentinel:
            print(f"\n✅ Los mapas del Trimestre {trimestre} {anio} aún son válidos")
            print("   Usa --force para regenerar de todas formas")
            return True
    
    print(f"\n🔄 Regenerando mapas con nuevos tokens de autenticación...\n")
    
    # Autenticar con Earth Engine
    try:
        ee.Initialize(project=GCP_PROJECT)
        print("✅ Autenticado con Earth Engine")
    except Exception as e:
        print(f"⚠️ Error al autenticar con Earth Engine: {e}")
        print("   Ejecuta: earthengine authenticate")
        return False
    
    # Cargar GeoDataFrames
    print(f"📂 Cargando datos de alertas...")
    all_alerts_gdf = gpd.read_file(ALERTS_GEOJSON_PATH)  # Todas las alertas para mapa principal
    analysis_gdf = gpd.read_file(DF_ANALYSIS_PATH)  # Alertas highest con clusters para Sentinel
    
    if all_alerts_gdf.empty:
        print("⚠️ No hay alertas en este trimestre, no se puede regenerar mapas")
        return False
    
    print(f"   {len(all_alerts_gdf)} alertas totales encontradas")
    print(f"   {len(analysis_gdf)} alertas de nivel 'highest' con clusters")
    
    # Regenerar mapa principal de alertas (con TODAS las alertas)
    if needs_regen_main or force:
        print(f"\n🗺️  Regenerando mapa principal de alertas...")
        plot_alerts_interactive(all_alerts_gdf, POLYGON_PATH, MAP_OUTPUT_PATH)
        print(f"   ✅ Guardado: {MAP_OUTPUT_PATH}")
    else:
        print(f"\n⏭️  Saltando mapa principal (aún válido)")
    
    # Regenerar mapas Sentinel por cluster
    if needs_regen_sentinel or force:
        print(f"\n🛰️  Regenerando mapas Sentinel por cluster...")
        
        # Usar solo las alertas highest del análisis (ya tienen cluster_id)
        highest_alerts = analysis_gdf
        
        if highest_alerts.empty:
            print("   ℹ️ No hay alertas de nivel 'highest', saltando mapas Sentinel")
        else:
            os.makedirs(SENTINEL_IMAGES_PATH, exist_ok=True)
            
            # Obtener fechas del trimestre
            start_date, end_date = get_trimestre_dates(trimestre, anio)
            
            # Agrupar por cluster_id
            cluster_ids = highest_alerts["cluster_id"].unique()
            print(f"   Clusters a procesar: {len(cluster_ids)}")
            
            success_count = 0
            for cluster_id in cluster_ids:
                try:
                    cluster_alerts = highest_alerts[highest_alerts["cluster_id"] == cluster_id]
                    # Crear bbox igual que en main.py: buffer 2000m + envelope
                    # Primero convertir a UTM para buffer en metros
                    utm_crs = cluster_alerts.estimate_utm_crs()
                    cluster_alerts_utm = cluster_alerts.to_crs(utm_crs)
                    
                    # Buffer de 2000m y luego envelope (bbox rectangular)
                    cluster_geom_utm = cluster_alerts_utm.geometry.buffer(2000).unary_union.envelope
                    
                    # Convertir de vuelta a EPSG:4326
                    cluster_gdf = gpd.GeoDataFrame(geometry=[cluster_geom_utm], crs=utm_crs)
                    cluster_geom = cluster_gdf.to_crs("EPSG:4326").iloc[0].geometry
                    
                    output_path = os.path.join(SENTINEL_IMAGES_PATH, f"sentinel_cluster_{cluster_id}.html")
                    
                    plot_sentinel_cluster_interactive(
                        cluster_geom=cluster_geom,
                        cluster_id=cluster_id,
                        start_date=start_date,
                        end_date=end_date,
                        output_path=output_path,
                        alerts_gdf=cluster_alerts,
                        cloudy=30,
                        project=GCP_PROJECT
                    )
                    success_count += 1
                    
                except Exception as e:
                    print(f"   ⚠️ Error en cluster {cluster_id}: {e}")
            
            print(f"   ✅ Regenerados exitosamente: {success_count}/{len(cluster_ids)} mapas Sentinel")
    else:
        print(f"\n⏭️  Saltando mapas Sentinel (aún válidos)")
    
    # Regenerar reporte HTML
    print(f"\n📄 Regenerando reporte HTML...")
    if not os.path.exists(JSON_FINAL_PATH):
        print(f"   ⚠️ No se encontró {JSON_FINAL_PATH}")
        print("   No se puede regenerar el reporte sin el JSON de datos")
        return False
    
    try:
        render(
            template_path=TEMPLATE_PATH,
            data_path=Path(JSON_FINAL_PATH),
            out_path=REPORT_HTML_PATH
        )
        print(f"   ✅ Reporte guardado: {REPORT_HTML_PATH}")
    except Exception as e:
        print(f"   ⚠️ Error al regenerar reporte: {e}")
    
    print(f"\n{'='*60}")
    print(f"✅ Regeneración completada para Trimestre {trimestre} {anio}")
    print(f"{'='*60}")
    print(f"\n📁 Archivos actualizados:")
    print(f"   - Mapa principal: {MAP_OUTPUT_PATH}")
    print(f"   - Mapas Sentinel: {SENTINEL_IMAGES_PATH}")
    print(f"   - Reporte HTML: {REPORT_HTML_PATH}")
    
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Regenerar mapas HTML de GFW cuando los tiles de Earth Engine han expirado",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python gfw_alerts/src/regenerate_maps.py --trimestre II --anio 2025
  python gfw_alerts/src/regenerate_maps.py --trimestre III --anio 2024 --force
  python gfw_alerts/src/regenerate_maps.py --all  # Regenerar todos los trimestres disponibles
        """
    )
    parser.add_argument("--trimestre", type=str, help="Trimestre (I, II, III, IV)")
    parser.add_argument("--anio", type=int, help="Año en formato YYYY")
    parser.add_argument("--all", action="store_true", help="Regenerar todos los trimestres disponibles")
    parser.add_argument("--force", action="store_true", help="Forzar regeneración sin verificar expiración")
    
    args = parser.parse_args()
    
    if args.all:
        # Buscar todas las carpetas de salida
        ONEDRIVE_PATH = os.getenv("ONEDRIVE_PATH")
        if not ONEDRIVE_PATH:
            print("❌ Error: Variable ONEDRIVE_PATH no configurada")
            sys.exit(1)
        
        output_base = os.path.join(ONEDRIVE_PATH, "outputs")
        if not os.path.exists(output_base):
            print("❌ No se encontró el directorio de outputs")
            sys.exit(1)
        
        # Buscar carpetas con formato I_trim_YYYY, II_trim_YYYY, etc.
        folders = [f for f in os.listdir(output_base) if re.match(r'(I|II|III|IV)_trim_\d{4}', f)]
        folders.sort()
        
        if not folders:
            print("❌ No se encontraron carpetas de salida")
            sys.exit(1)
        
        print(f"📊 Se encontraron {len(folders)} análisis previos")
        success_count = 0
        
        for folder in folders:
            # Extraer año y trimestre del nombre de carpeta
            match = re.match(r'(I|II|III|IV)_trim_(\d{4})', folder)
            if match:
                trimestre = match.group(1)
                anio = int(match.group(2))
                
                if regenerate_for_trimestre(trimestre, anio, args.force):
                    success_count += 1
        
        print(f"\n{'='*60}")
        print(f"✅ Regenerados exitosamente: {success_count}/{len(folders)}")
        print(f"{'='*60}")
        
    elif args.trimestre and args.anio:
        success = regenerate_for_trimestre(args.trimestre.upper(), args.anio, args.force)
        sys.exit(0 if success else 1)
    
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
