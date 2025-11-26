# 🔄 Regeneración de Mapas - GFW Alerts

Los mapas HTML de GFW Alerts usan tiles de Earth Engine que expiran después de algunos días. Este sistema permite regenerarlos sin recalcular los datos de alertas.

## 📋 Uso Rápido

### Verificar estado de tiles
```bash
python gfw_alerts/src/check_tiles_status.py
```

### Regenerar un trimestre específico
```bash
python gfw_alerts/src/regenerate_maps.py --trimestre II --anio 2025
```

### Regenerar todos los trimestres
```bash
python gfw_alerts/src/regenerate_maps.py --all
```

### Forzar regeneración (sin verificar)
```bash
python gfw_alerts/src/regenerate_maps.py --trimestre II --anio 2025 --force
```

## 🛠️ Opciones

- `--trimestre I|II|III|IV`: Trimestre a regenerar
- `--anio YYYY`: Año a regenerar
- `--all`: Regenerar todos los trimestres disponibles
- `--force`: Forzar regeneración sin verificar si los tiles están expirados

## 🗺️ Mapas que se regeneran

1. **Mapa principal de alertas** (`alertas_mapa_YYYY_TI.html`): Mapa interactivo con todas las alertas
2. **Mapas Sentinel por cluster** (`sentinel_imagenes/sentinel_cluster_*.html`): Mapas individuales con imágenes Sentinel-2 para cada cluster de alertas de nivel "highest"
3. **Reporte HTML** (`reporte_final.html`): Reporte completo con los mapas actualizados

## 📝 Notas

- Solo regenera los mapas HTML, **NO vuelve a descargar** datos de GFW ni imágenes Sentinel
- Requiere autenticación con Earth Engine
- Los datos de análisis (`alertas_gfw_analisis_*.geojson`) deben existir
- El JSON de reporte (`reporte_final.json`) debe existir
