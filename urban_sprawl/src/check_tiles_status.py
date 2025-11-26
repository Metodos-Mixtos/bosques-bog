#!/usr/bin/env python3
"""
Script para verificar el estado de los tiles de todos los reportes de urban sprawl generados.
Muestra qué meses tienen tiles expirados y necesitan regeneración.

Uso:
    python urban_sprawl/src/check_tiles_status.py
"""

import os
import sys
import re
import requests
from datetime import datetime
from pathlib import Path

# Agregar directorio raíz al path
SCRIPT_DIR = Path(__file__).parent
ROOT_DIR = SCRIPT_DIR.parent.parent
sys.path.insert(0, str(ROOT_DIR))

from urban_sprawl.src.config import BASE_PATH


def check_tile_url(html_path: str) -> tuple[bool, str]:
    """
    Verifica si los tiles de un mapa HTML aún son válidos.
    
    Returns:
        (is_valid, message)
    """
    if not os.path.exists(html_path):
        return False, "❌ Archivo no encontrado"
    
    try:
        with open(html_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Buscar URLs de tiles de Earth Engine
        pattern = r'https://earthengine-highvolume\.googleapis\.com/[^"\']*'
        tile_urls = re.findall(pattern, content)
        
        if not tile_urls:
            return False, "⚠️ No se encontraron tiles"
        
        # Probar la primera URL
        test_url = tile_urls[0]
        test_url = test_url.replace('{z}', '10').replace('{x}', '285').replace('{y}', '490')
        
        response = requests.head(test_url, timeout=5)
        
        if response.status_code == 200:
            return True, "✅ Válidos"
        else:
            return False, f"❌ Expirados ({response.status_code})"
            
    except requests.exceptions.Timeout:
        return False, "⏱️ Timeout"
    except Exception as e:
        return False, f"⚠️ Error: {str(e)[:30]}"


def main():
    print("\n" + "="*80)
    print("🔍 VERIFICACIÓN DE ESTADO DE TILES DE EARTH ENGINE - URBAN SPRAWL")
    print("="*80 + "\n")
    
    output_base = os.path.join(BASE_PATH, "urban_sprawl", "outputs")
    
    if not os.path.exists(output_base):
        print(f"❌ No se encontró el directorio de outputs: {output_base}")
        return
    
    # Buscar todas las carpetas con formato YYYY_MM
    folders = [f for f in os.listdir(output_base) if re.match(r'\d{4}_\d{2}', f)]
    folders.sort()
    
    if not folders:
        print("❌ No se encontraron análisis previos")
        return
    
    print(f"📊 Análisis encontrados: {len(folders)}\n")
    
    # Verificar cada mes
    valid_count = 0
    expired_count = 0
    error_count = 0
    
    results = []
    
    for folder in folders:
        anio, mes = map(int, folder.split('_'))
        month_name = datetime(anio, mes, 1).strftime("%B %Y")
        
        map_path = os.path.join(output_base, folder, "maps", "map_expansion.html")
        
        is_valid, message = check_tile_url(map_path)
        
        if is_valid:
            valid_count += 1
            status_icon = "✅"
        elif "Expirados" in message or "❌" in message:
            expired_count += 1
            status_icon = "❌"
        else:
            error_count += 1
            status_icon = "⚠️"
        
        results.append({
            "folder": folder,
            "month": month_name,
            "status": message,
            "icon": status_icon,
            "needs_regen": not is_valid
        })
        
        print(f"{status_icon} {month_name:20s} - {message}")
    
    # Resumen
    print("\n" + "="*80)
    print("📊 RESUMEN")
    print("="*80)
    print(f"  ✅ Tiles válidos:           {valid_count}")
    print(f"  ❌ Tiles expirados:         {expired_count}")
    print(f"  ⚠️  Errores/No encontrados:  {error_count}")
    print(f"  📊 Total:                   {len(folders)}")
    
    # Comandos sugeridos
    expired = [r for r in results if r["needs_regen"] and "Expirados" in r["status"]]
    
    if expired:
        print("\n" + "="*80)
        print("🔧 REGENERACIÓN RECOMENDADA")
        print("="*80)
        print("\nPara regenerar los mapas expirados, ejecuta:\n")
        
        if len(expired) == 1:
            folder = expired[0]["folder"]
            anio, mes = folder.split('_')
            print(f"  python urban_sprawl/src/regenerate_maps.py --anio {anio} --mes {int(mes)}")
        elif len(expired) <= 3:
            for result in expired:
                folder = result["folder"]
                anio, mes = folder.split('_')
                print(f"  python urban_sprawl/src/regenerate_maps.py --anio {anio} --mes {int(mes)}")
        else:
            print("  python urban_sprawl/src/regenerate_maps.py --all")
        
        print("\n" + "="*80)
    else:
        print("\n✅ Todos los tiles están válidos o no hay mapas expirados")
    
    print()


if __name__ == "__main__":
    main()
