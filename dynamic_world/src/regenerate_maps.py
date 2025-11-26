#!/usr/bin/env python3
"""
Script para regenerar mapas HTML de Dynamic World cuando los tiles de Earth Engine han expirado.
Este script NO recalcula transiciones, solo regenera los mapas interactivos con nuevos tokens.

Uso:
    python dynamic_world/src/regenerate_maps.py --anio 2025 --mes 6
    python dynamic_world/src/regenerate_maps.py --anio 2025 --mes 6 --force
    python dynamic_world/src/regenerate_maps.py --all
"""

import argparse
import os
import sys
from pathlib import Path
from datetime import datetime
import locale
import re
import requests
import ee

# Agregar directorio raíz al path
SCRIPT_DIR = Path(__file__).parent
ROOT_DIR = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from dynamic_world.src.config import AOI_DIR, OUTPUTS_BASE, LOGO_PATH
from dynamic_world.src.dw_utils import get_dynamic_world_image
from dynamic_world.src.maps_utils import generate_maps
from dynamic_world.src.reports.render_report import render
from dynamic_world.src.aux_utils import save_json

# Configurar idioma español
try:
    locale.setlocale(locale.LC_TIME, "es_ES.UTF-8")
except:
    try:
        locale.setlocale(locale.LC_TIME, "es_CO.UTF-8")
    except:
        pass


def check_tile_expiration(html_path: str) -> bool:
    """
    Verifica si los tiles de un mapa HTML han expirado.
    
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
        
        # Probar la primera URL
        test_url = tile_urls[0].replace('{z}', '10').replace('{x}', '285').replace('{y}', '490')
        
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


def regenerate_for_month(anio: int, mes: int, force: bool = False):
    """
    Regenera mapas para un mes específico.
    
    Args:
        anio: Año (YYYY)
        mes: Mes (1-12)
        force: Si True, regenera sin verificar expiración
    """
    month_str = datetime(anio, mes, 1).strftime("%B").capitalize()
    
    print(f"\n{'='*60}")
    print(f"🗓️  Regenerando mapas para {month_str} {anio}")
    print(f"{'='*60}\n")
    
    # Construir rutas
    period_dir = os.path.join(OUTPUTS_BASE, f"{anio}_{mes}")
    
    if not os.path.exists(period_dir):
        print(f"❌ Error: No se encontró el directorio de salidas")
        print(f"   Primero debes ejecutar el análisis completo con:")
        print(f"   python dynamic_world/main.py --anio {anio} --mes {mes}")
        return False
    
    # Verificar si necesita regeneración (a menos que se fuerce)
    needs_regen = True
    
    if not force:
        print("🔍 Verificando estado de los tiles...\n")
        
        # Buscar un mapa HTML de ejemplo para verificar
        example_map = None
        for root, dirs, files in os.walk(period_dir):
            for file in files:
                if file.endswith('.html') and 'map' in file.lower():
                    example_map = os.path.join(root, file)
                    break
            if example_map:
                break
        
        if example_map:
            print(f"📍 Verificando mapa: {os.path.basename(example_map)}")
            needs_regen = check_tile_expiration(example_map)
        
        if not needs_regen:
            print(f"\n✅ Los mapas de {month_str} {anio} aún son válidos")
            print("   Usa --force para regenerar de todas formas")
            return True
    
    print(f"\n🔄 Regenerando mapas con nuevos tokens de autenticación...\n")
    
    # Autenticar con Earth Engine
    try:
        GCP_PROJECT = os.getenv("GCP_PROJECT")
        ee.Initialize(project=GCP_PROJECT)
        print("✅ Autenticado con Earth Engine")
    except Exception as e:
        print(f"⚠️ Error al autenticar con Earth Engine: {e}")
        print("   Ejecuta: earthengine authenticate")
        return False
    
    # Obtener fechas
    current_date = datetime(anio, mes, 1).strftime("%Y-%m-%d")
    date_before = datetime(anio - 1, mes, 1).strftime("%Y-%m-%d")
    
    print(f"📆 Comparando {month_str} {anio - 1} ↔ {month_str} {anio}\n")
    
    # Obtener lista de AOIs
    geojson_files = [os.path.join(AOI_DIR, f) for f in os.listdir(AOI_DIR) if f.startswith("paramo_")]
    
    if not geojson_files:
        print("❌ No se encontraron archivos de páramos en el directorio de AOI")
        return False
    
    print(f"🏔️  Páramos a procesar: {len(geojson_files)}\n")
    
    results = []
    success_count = 0
    
    for aoi_path in geojson_files:
        aoi_name = os.path.splitext(os.path.basename(aoi_path))[0]
        print(f"  Procesando: {aoi_name}")
        
        try:
            # Rutas
            aoi_dir = os.path.join(period_dir, aoi_name)
            grid_path = os.path.join(aoi_dir, "grilla", f"grid_{aoi_name}_10000m.geojson")
            maps_dir = os.path.join(aoi_dir, "mapas")
            
            if not os.path.exists(grid_path):
                print(f"    ⚠️ No se encontró grilla para {aoi_name}, saltando...")
                continue
            
            # Cargar estadísticas previas del CSV
            csv_path = os.path.join(aoi_dir, "comparacion", f"{aoi_name}_transiciones.csv")
            if not os.path.exists(csv_path):
                print(f"    ⚠️ No se encontró CSV de transiciones para {aoi_name}, saltando...")
                continue
            
            import pandas as pd
            df_trans = pd.read_csv(csv_path)
            
            # Calcular estadísticas agregadas
            total_perdida_bosque = df_trans["n_1_a_otro"].sum()
            total_perdida_matorral = df_trans["n_5_a_otro_no1"].sum()
            
            if total_perdida_bosque > 0:
                fila_bosque_max = df_trans.loc[df_trans["n_1_a_otro"].idxmax()]
                grilla_max_bosque = int(fila_bosque_max["grid_id"])
                perdida_bosque_max = round(fila_bosque_max["n_1_a_otro"] * 0.01, 2)
            else:
                grilla_max_bosque, perdida_bosque_max = None, 0
            
            if total_perdida_matorral > 0:
                fila_mat_max = df_trans.loc[df_trans["n_5_a_otro_no1"].idxmax()]
                grilla_max_mat = int(fila_mat_max["grid_id"])
                perdida_mat_max = round(fila_mat_max["n_5_a_otro_no1"] * 0.01, 2)
            else:
                grilla_max_mat, perdida_mat_max = None, 0
            
            # Regenerar imágenes de Dynamic World
            dw_before = get_dynamic_world_image(aoi_path, date_before)
            dw_current = get_dynamic_world_image(aoi_path, current_date)
            
            # Regenerar mapas
            from dynamic_world.src.config import LOOKBACK_DAYS
            maps_info = generate_maps(
                aoi_path,
                grid_path,
                maps_dir,
                date_before,
                current_date,
                anio,
                month_str,
                LOOKBACK_DAYS,
                dw_before=dw_before,
                dw_current=dw_current
            )
            
            # Rutas relativas
            relative_maps = {
                k: os.path.relpath(v, start=period_dir)
                for k, v in maps_info.items()
            }
            
            result = {
                "NOMBRE_PARAMO": aoi_name.replace("_", " ").title(),
                "PERDIDA_BOSQUE_PARAMOS": round(total_perdida_bosque * 0.01, 2),
                "GRILLA_CON_MAS_PERDIDA": grilla_max_bosque,
                "PERDIDA_BOSQUE_GRILLA_1": perdida_bosque_max,
                "PERDIDA_MATORRAL_PARAMOS": round(total_perdida_matorral * 0.01, 2),
                "GRILLA_CON_MAS_CAMBIO_5": grilla_max_mat,
                "PERDIDA_MATORRAL_GRILLA_1": perdida_mat_max,
                **relative_maps
            }
            
            results.append(result)
            success_count += 1
            print(f"    ✅ Completado")
            
        except Exception as e:
            print(f"    ⚠️ Error: {e}")
    
    if results:
        # Regenerar JSON y reporte
        print(f"\n📄 Regenerando reporte HTML...")
        
        logo_rel = os.path.relpath(LOGO_PATH, start=period_dir)
        json_final = {
            "MES": month_str,
            "ANIO": anio,
            "LOGO": logo_rel,
            "PARAMOS": results
        }
        
        json_path = os.path.join(period_dir, f"reporte_paramos_{anio}_{mes}.json")
        save_json(json_final, json_path)
        
        tpl_path = SCRIPT_DIR / "reports" / "report_template.html"
        html_path = os.path.join(period_dir, f"reporte_paramos_{anio}_{mes}.html")
        
        render(Path(tpl_path), Path(json_path), Path(html_path))
        print(f"   ✅ Reporte guardado: {html_path}")
    
    print(f"\n{'='*60}")
    print(f"✅ Regeneración completada para {month_str} {anio}")
    print(f"{'='*60}")
    print(f"\n📁 Páramos procesados exitosamente: {success_count}/{len(geojson_files)}")
    
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Regenerar mapas HTML de Dynamic World cuando los tiles han expirado",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python dynamic_world/src/regenerate_maps.py --anio 2025 --mes 6
  python dynamic_world/src/regenerate_maps.py --anio 2024 --mes 12 --force
  python dynamic_world/src/regenerate_maps.py --all
        """
    )
    parser.add_argument("--anio", type=int, help="Año en formato YYYY")
    parser.add_argument("--mes", type=int, help="Mes en formato 1-12")
    parser.add_argument("--all", action="store_true", help="Regenerar todos los meses disponibles")
    parser.add_argument("--force", action="store_true", help="Forzar regeneración sin verificar expiración")
    
    args = parser.parse_args()
    
    if args.all:
        # Buscar todas las carpetas de salida
        if not os.path.exists(OUTPUTS_BASE):
            print("❌ No se encontró el directorio de outputs")
            sys.exit(1)
        
        # Buscar carpetas con formato YYYY_M o YYYY_MM
        folders = [f for f in os.listdir(OUTPUTS_BASE) if re.match(r'\d{4}_\d{1,2}', f)]
        folders.sort()
        
        if not folders:
            print("❌ No se encontraron carpetas de salida")
            sys.exit(1)
        
        print(f"📊 Se encontraron {len(folders)} análisis previos")
        success_count = 0
        
        for folder in folders:
            anio, mes = map(int, folder.split('_'))
            if regenerate_for_month(anio, mes, args.force):
                success_count += 1
        
        print(f"\n{'='*60}")
        print(f"✅ Regenerados exitosamente: {success_count}/{len(folders)}")
        print(f"{'='*60}")
        
    elif args.anio and args.mes:
        if args.mes < 1 or args.mes > 12:
            print("❌ Error: El mes debe estar entre 1 y 12")
            sys.exit(1)
        
        success = regenerate_for_month(args.anio, args.mes, args.force)
        sys.exit(0 if success else 1)
    
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
