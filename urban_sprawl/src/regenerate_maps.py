#!/usr/bin/env python3
"""
Script para regenerar mapas HTML cuando los tiles de Earth Engine han expirado.
Este script NO recalcula estadísticas, solo regenera los mapas interactivos con nuevos tokens.

Uso:
    python urban_sprawl/src/regenerate_maps.py --anio 2025 --mes 10
    python urban_sprawl/src/regenerate_maps.py --anio 2025 --mes 10 --force
    python urban_sprawl/src/regenerate_maps.py --all
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path
import locale
import re
import requests

# Agregar directorio raíz al path
SCRIPT_DIR = Path(__file__).parent
ROOT_DIR = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from urban_sprawl.src.config import AOI_PATH, SAC_PATH, RESERVA_PATH, EEP_PATH, LOGO_PATH, GOOGLE_CLOUD_PROJECT, BASE_PATH
from urban_sprawl.src.aux_utils import authenticate_gee, set_dates
from urban_sprawl.src.maps_utils import generate_maps
from urban_sprawl.src.pipeline_utils import build_report


# === Configurar idioma español ===
try:
    locale.setlocale(locale.LC_TIME, "es_ES.UTF-8")
except:
    try:
        locale.setlocale(locale.LC_TIME, "es_CO.UTF-8")
    except:
        pass


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
        
        # Buscar URLs de tiles de Earth Engine en el HTML
        pattern = r'https://earthengine-highvolume\.googleapis\.com/[^"\']*'
        tile_urls = re.findall(pattern, content)
        
        if not tile_urls:
            print("  ℹ️ No se encontraron URLs de tiles en el HTML")
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


def regenerate_for_month(anio: int, mes: int, force: bool = False):
    """
    Regenera mapas y reporte para un mes específico.
    
    Args:
        anio: Año (YYYY)
        mes: Mes (1-12)
        force: Si True, regenera sin verificar expiración
    """
    month_str = datetime(anio, mes, 1).strftime("%B").capitalize()
    # Calcular mes anterior correctamente
    if mes > 1:
        previous_month_str = datetime(anio, mes-1, 1).strftime("%B").capitalize()
    else:
        previous_month_str = datetime(anio-1, 12, 1).strftime("%B").capitalize()
    
    print(f"\n{'='*60}")
    print(f"🗓️  Regenerando mapas para {month_str} {anio}")
    print(f"{'='*60}\n")
    
    # Construir rutas
    output_dir = os.path.join(BASE_PATH, "urban_sprawl", "outputs", f"{anio}_{mes:02d}")
    dirs = {
        "base": output_dir,
        "dw": os.path.join(output_dir, "dw"),
        "sentinel": os.path.join(output_dir, "sentinel"),
        "intersections": os.path.join(output_dir, "intersections"),
        "maps": os.path.join(output_dir, "maps"),
        "stats": os.path.join(output_dir, "stats"),
        "reportes": os.path.join(output_dir, "reportes")
    }
    
    # Verificar que existen los datos necesarios
    if not os.path.exists(dirs["intersections"]):
        print(f"❌ Error: No se encontró el directorio de intersecciones")
        print(f"   Primero debes ejecutar el análisis completo con:")
        print(f"   python urban_sprawl/main.py --anio {anio} --mes {mes}")
        return False
    
    map_html = os.path.join(dirs["maps"], "map_expansion.html")
    
    # Verificar si necesita regeneración (a menos que se fuerce)
    if not force:
        print("🔍 Verificando estado de los tiles...")
        if not check_tile_expiration(map_html):
            print(f"\n✅ Los mapas de {month_str} {anio} aún son válidos")
            print("   Usa --force para regenerar de todas formas")
            return True
    
    print(f"\n🔄 Regenerando mapas con nuevos tokens de autenticación...\n")
    
    # Obtener fechas
    last_day_curr, last_day_prev = set_dates(mes, anio)
    
    # Autenticar con GEE
    authenticate_gee(project=GOOGLE_CLOUD_PROJECT)
    
    # Regenerar mapas
    print("🛰️  Generando nuevos tiles de Sentinel...")
    new_map_html = generate_maps(
        AOI_PATH, 
        last_day_prev, 
        last_day_curr, 
        dirs, 
        month_str, 
        previous_month_str,
        SAC_PATH,
        RESERVA_PATH,
        EEP_PATH
    )
    print(f"   ✅ Mapa guardado: {new_map_html}")
    
    # Regenerar reporte HTML
    print("\n📄 Regenerando reporte HTML...")
    df_path = f"{dirs['stats']}/resumen_expansion_upl_ha.csv"
    strict_path = f"{dirs['stats']}/resumen_expansion_upl_ha_strict.csv"
    
    if not os.path.exists(df_path):
        print(f"   ⚠️ No se encontró {df_path}")
        print("   El reporte se generará sin estadísticas")
        df_path = None
    
    build_report(
        df_path=df_path,
        strict_path=strict_path if os.path.exists(strict_path) else None,
        map_html=new_map_html,
        logo_path=LOGO_PATH,
        output_dir=dirs["reportes"],
        month=month_str,
        year=anio
    )
    
    print(f"\n{'='*60}")
    print(f"✅ Regeneración completada para {month_str} {anio}")
    print(f"{'='*60}")
    print(f"\n📁 Archivos actualizados:")
    print(f"   - Mapa: {new_map_html}")
    print(f"   - Reporte: {dirs['reportes']}/reporte_expansion_urbana.html")
    
    return True


def main():
    parser = argparse.ArgumentParser(
        description="Regenerar mapas HTML cuando los tiles de Earth Engine han expirado",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python urban_sprawl/src/regenerate_maps.py --anio 2025 --mes 10
  python urban_sprawl/src/regenerate_maps.py --anio 2025 --mes 9 --force
  python urban_sprawl/src/regenerate_maps.py --all
        """
    )
    parser.add_argument("--anio", type=int, help="Año en formato YYYY")
    parser.add_argument("--mes", type=int, help="Mes en formato numérico (1-12)")
    parser.add_argument("--all", action="store_true", help="Regenerar todos los meses disponibles")
    parser.add_argument("--force", action="store_true", help="Forzar regeneración sin verificar expiración")
    
    args = parser.parse_args()
    
    if args.all:
        # Buscar todas las carpetas de salida
        output_base = os.path.join(BASE_PATH, "urban_sprawl", "outputs")
        if not os.path.exists(output_base):
            print("❌ No se encontró el directorio de outputs")
            sys.exit(1)
        
        # Buscar carpetas con formato YYYY_MM
        folders = [f for f in os.listdir(output_base) if re.match(r'\d{4}_\d{2}', f)]
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
