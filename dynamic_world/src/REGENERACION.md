# 🔄 Regeneración de Mapas - Dynamic World

Los mapas HTML de Dynamic World usan tiles de Earth Engine que expiran después de algunos días. Este sistema permite regenerarlos sin recalcular las transiciones.

## 📋 Uso Rápido

### Verificar estado de tiles
```bash
python dynamic_world/src/check_tiles_status.py
```

### Regenerar un mes específico
```bash
python dynamic_world/src/regenerate_maps.py --anio 2025 --mes 6
```

### Regenerar todos los meses
```bash
python dynamic_world/src/regenerate_maps.py --all
```

### Forzar regeneración (sin verificar)
```bash
python dynamic_world/src/regenerate_maps.py --anio 2025 --mes 6 --force
```

## 🛠️ Opciones

- `--anio YYYY`: Año a regenerar
- `--mes M`: Mes a regenerar (1-12)
- `--all`: Regenerar todos los meses disponibles
- `--force`: Forzar regeneración sin verificar si los tiles están expirados

## 📝 Notas

- Solo regenera los mapas HTML, **NO recalcula** las transiciones de Dynamic World
- Requiere autenticación con Earth Engine
- Los datos de transiciones (CSV) deben existir (generados en análisis original)
- Compara el mes actual con el mismo mes del año anterior
