# Dynamic World Land Cover Analysis

Este repositorio permite generar mapas de clasificación de cobertura terrestre utilizando datos de Dynamic World (Google Earth Engine) para dos trimestres dados y una geometría definida por el usuario.

## Estructura del proyecto

```
project-root/
├── data/
│   ├── input/
│   │   └── AOI.geojson                # Archivo GeoJSON del área de interés
│   └── output/
│       ├── images/                    # Imágenes .tif descargadas desde GEE
│       ├── maps/                      # Mapas PNG generados para cada trimestre y comparación
│       └── comparison/                # CSV con comparación por celdas y clases
├── full_process_main/
│   └── main.py                        # Script principal automatizado
├── src/
│   ├── download_utils.py             # Descarga de datos desde GEE
│   ├── grid_utils.py                 # Creación de grilla sobre AOI
│   ├── map_utils.py                  # Generación de mapas
│   └── zonal_utils.py                # Estadísticas por celdas y comparación
└── README.md
```

## Requisitos

- Python 3.8+
- Earth Engine Python API
- rasterio
- geopandas
- rioxarray
- contextily
- matplotlib
- xarray

Instalación recomendada:
```bash
conda create -n dw-env python=3.9
conda activate dw-env
pip install -r requirements.txt
```

## Uso

### 1. Ejecutar el pipeline completo:
```bash
python full_process_main/main.py
```
Esto realiza:
- Autenticación con GEE
- Creación de grilla sobre AOI
- Descarga de imágenes de Dynamic World para dos trimestres
- Cálculo de estadísticas por celda y comparación
- Generación de mapas comparativos y por trimestre

### 2. Visualizar mapas
Los mapas se guardan como `.png` en `data/output/maps/`.

## Autores
Desarrollado por Javier Guerra con apoyo de modelos de inteligencia artificial para automatización geoespacial y visualización de datos.

---

Este proyecto hace uso de datos públicos de Dynamic World publicados por Google y el World Resources Institute (WRI).
