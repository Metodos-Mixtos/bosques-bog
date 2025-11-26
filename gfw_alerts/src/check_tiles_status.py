#!/usr/bin/env python3
"""
Script para verificar el estado de todos los tiles en los reportes de GFW generados.
Identifica qué trimestres necesitan regeneración de mapas.

Uso:
    python gfw_alerts/src/check_tiles_status.py
"""

import os
import sys
import re
import requests
from pathlib import Path
from dotenv import load_dotenv

# Cargar .env
SCRIPT_DIR = Path(__file__).parent
env_path = SCRIPT_DIR.parent.parent.parent / "dot_env_content.env"
load_dotenv(dotenv_path=env_path)


def check_html_tiles(html_path: str) -> tuple[bool, str]:
    """
    Verifica si los tiles de un archivo HTML están válidos.
    
    Returns:
        (tiles_valid, status_message)
    """
    if not os.path.exists(html_path):
        return False, "Archivo no encontrado"
    
    try:
        with open(html_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Buscar URLs de tiles de Earth Engine
        pattern = r'https://earthengine[^"\']*googleapis\.com/[^"\']*'
        tile_urls = re.findall(pattern, content)
        
        if not tile_urls:
            return True, "Sin tiles EE (mapa estático)"
        
        # Probar la primera URL
        test_url = tile_urls[0].replace('{z}', '10').replace('{x}', '285').replace('{y}', '490')
        
        response = requests.head(test_url, timeout=10)
        
        if response.status_code == 200:
            return True, "✅ Válidos"
        else:
            return False, f"❌ Expirados ({response.status_code})"
            
    except requests.exceptions.Timeout:
        return False, "⏱️ Timeout"
    except Exception as e:
        return False, f"⚠️ Error: {str(e)[:30]}"


def scan_outputs():
    """
    Escanea todos los outputs de GFW y verifica el estado de los tiles.
    """
    ONEDRIVE_PATH = os.getenv("ONEDRIVE_PATH")
    
    if not ONEDRIVE_PATH:
        print("❌ Error: Variable ONEDRIVE_PATH no configurada en .env")
        sys.exit(1)
    
    output_base = os.path.join(ONEDRIVE_PATH, "outputs")
    
    if not os.path.exists(output_base):
        print(f"❌ No se encontró el directorio de outputs: {output_base}")
        sys.exit(1)
    
    # Buscar carpetas con formato I_trim_YYYY, II_trim_YYYY, etc.
    folders = [f for f in os.listdir(output_base) if re.match(r'(I|II|III|IV)_trim_\d{4}', f)]
    folders.sort()
    
    if not folders:
        print(f"❌ No se encontraron carpetas de reportes GFW en: {output_base}")
        sys.exit(1)
    
    print(f"\n{'='*80}")
    print(f"🔍 VERIFICACIÓN DE TILES EN REPORTES GFW")
    print(f"{'='*80}\n")
    print(f"📂 Directorio base: {output_base}")
    print(f"📊 Trimestres encontrados: {len(folders)}\n")
    
    results = []
    
    for folder in folders:
        folder_path = os.path.join(output_base, folder)
        
        # Extraer año y trimestre del formato I_trim_2025
        match = re.match(r'(I|II|III|IV)_trim_(\d{4})', folder)
        if not match:
            continue
        
        trimestre = match.group(1)
        anio = match.group(2)
        
        print(f"{'─'*80}")
        print(f"📅 Trimestre {trimestre} de {anio} ({folder})")
        print(f"{'─'*80}")
        
        # Verificar mapa principal
        main_map = os.path.join(folder_path, f"alertas_mapa_{folder}.html")
        main_valid, main_status = check_html_tiles(main_map)
        print(f"  📍 Mapa principal: {main_status}")
        
        # Verificar mapas Sentinel
        sentinel_dir = os.path.join(folder_path, "sentinel_imagenes")
        sentinel_count = 0
        sentinel_expired = 0
        
        if os.path.exists(sentinel_dir):
            sentinel_maps = [f for f in os.listdir(sentinel_dir) if f.endswith('.html')]
            sentinel_count = len(sentinel_maps)
            
            if sentinel_maps:
                # Verificar algunos mapas Sentinel (máximo 3)
                sample_maps = sentinel_maps[:min(3, len(sentinel_maps))]
                for map_file in sample_maps:
                    map_path = os.path.join(sentinel_dir, map_file)
                    valid, status = check_html_tiles(map_path)
                    if not valid:
                        sentinel_expired += 1
                
                if sentinel_expired > 0:
                    print(f"  🛰️  Mapas Sentinel: ❌ {sentinel_expired}/{len(sample_maps)} muestras expiraron")
                    sentinel_valid = False
                else:
                    print(f"  🛰️  Mapas Sentinel: ✅ {len(sample_maps)}/{len(sample_maps)} muestras válidas")
                    sentinel_valid = True
            else:
                print(f"  🛰️  Mapas Sentinel: ℹ️ Sin mapas")
                sentinel_valid = True
        else:
            print(f"  🛰️  Mapas Sentinel: ℹ️ Directorio no encontrado")
            sentinel_valid = True
        
        # Verificar reporte HTML
        report_html = os.path.join(folder_path, "reporte_final.html")
        report_exists = os.path.exists(report_html)
        print(f"  📄 Reporte HTML: {'✅ Existe' if report_exists else '❌ No encontrado'}")
        
        # Determinar si necesita regeneración
        needs_regen = not main_valid or not sentinel_valid
        
        results.append({
            "folder": folder,
            "anio": anio,
            "trimestre": trimestre,
            "main_valid": main_valid,
            "sentinel_valid": sentinel_valid,
            "sentinel_count": sentinel_count,
            "needs_regen": needs_regen
        })
        
        if needs_regen:
            print(f"\n  ⚠️  REQUIERE REGENERACIÓN")
        else:
            print(f"\n  ✅ Estado: OK")
        
        print()
    
    # Resumen final
    print(f"\n{'='*80}")
    print(f"📊 RESUMEN")
    print(f"{'='*80}\n")
    
    total = len(results)
    needs_regen_count = sum(1 for r in results if r["needs_regen"])
    valid_count = total - needs_regen_count
    
    print(f"  Total de trimestres: {total}")
    print(f"  ✅ Válidos: {valid_count}")
    print(f"  ⚠️  Requieren regeneración: {needs_regen_count}")
    
    if needs_regen_count > 0:
        print(f"\n{'─'*80}")
        print(f"🔧 COMANDOS PARA REGENERAR")
        print(f"{'─'*80}\n")
        
        for r in results:
            if r["needs_regen"]:
                print(f"  python gfw_alerts/src/regenerate_maps.py --trimestre {r['trimestre']} --anio {r['anio']}")
        
        print(f"\n  # O regenerar todos a la vez:")
        print(f"  python gfw_alerts/src/regenerate_maps.py --all")
    
    print(f"\n{'='*80}\n")


if __name__ == "__main__":
    scan_outputs()
