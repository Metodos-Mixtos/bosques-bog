# 🔄 Regeneración de Mapas - Urban Sprawl

Los mapas HTML de Urban Sprawl usan tiles de Earth Engine que expiran después de algunos días. Este sistema permite regenerarlos sin recalcular las estadísticas.

## 📋 Uso Rápido

### Verificar estado de tiles
```bash
python urban_sprawl/src/check_tiles_status.py
```

### Regenerar un mes específico
```bash
python urban_sprawl/src/regenerate_maps.py --anio 2025 --mes 10
```

### Regenerar todos los meses
```bash
python urban_sprawl/src/regenerate_maps.py --all
```

### Forzar regeneración (sin verificar)
```bash
python urban_sprawl/src/regenerate_maps.py --anio 2025 --mes 10 --force
```

## 🛠️ Opciones

- `--anio YYYY`: Año a regenerar
- `--mes M`: Mes a regenerar (1-12)
- `--all`: Regenerar todos los meses disponibles
- `--force`: Forzar regeneración sin verificar si los tiles están expirados

## 📝 Notas

- Solo regenera los mapas HTML, **NO recalcula** las estadísticas
- Requiere autenticación con Earth Engine
- Los datos de intersecciones deben existir (generados en análisis original)
