#!/usr/bin/env python3
"""
Script para verificar el estado de los tiles de todos los reportes de Dynamic World generados.
Muestra qué meses tienen tiles expirados y necesitan regeneración.

Uso:
    python dynamic_world/src/check_tiles_status.py
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

from dynamic_world.src.config import OUTPUTS_BASE


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
        pattern = r'https://earthengine[^"\']*googleapis\.com/[^"\']*'
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
    print("🔍 VERIFICACIÓN DE ESTADO DE TILES DE EARTH ENGINE - DYNAMIC WORLD")
    print("="*80 + "\n")
    
    if not os.path.exists(OUTPUTS_BASE):
        print(f"❌ No se encontró el directorio de outputs: {OUTPUTS_BASE}")
        return
    
    # Buscar todas las carpetas con formato YYYY_M o YYYY_MM
    folders = [f for f in os.listdir(OUTPUTS_BASE) if re.match(r'\d{4}_\d{1,2}', f)]
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
        
        folder_path = os.path.join(OUTPUTS_BASE, folder)
        
        # Buscar un mapa HTML de ejemplo (dw_mes.html o sentinel_mes.html)
        example_map = None
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                if file in ['dw_mes.html', 'sentinel_mes.html']:
                    example_map = os.path.join(root, file)
                    break
            if example_map:
                break
        
        if not example_map:
            is_valid = False
            message = "⚠️ No se encontraron mapas"
            status_icon = "⚠️"
            error_count += 1
        else:
            is_valid, message = check_tile_url(example_map)
            
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
            anio, mes = map(int, folder.split('_'))
            print(f"  python dynamic_world/src/regenerate_maps.py --anio {anio} --mes {mes}")
        elif len(expired) <= 3:
            for result in expired:
                folder = result["folder"]
                anio, mes = map(int, folder.split('_'))
                print(f"  python dynamic_world/src/regenerate_maps.py --anio {anio} --mes {mes}")
        else:
            print("  python dynamic_world/src/regenerate_maps.py --all")
        
        print("\n" + "="*80)
    else:
        print("\n✅ Todos los tiles están válidos o no hay mapas expirados")
    
    print()


if __name__ == "__main__":
    main()
