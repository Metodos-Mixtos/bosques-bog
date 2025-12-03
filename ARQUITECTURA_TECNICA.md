# Documento de Arquitectura Técnica
## Sistema de Monitoreo de Bosques y Páramos de Bogotá (SIMBYP)

**Versión:** 2.0  
**Fecha:** Diciembre 2025  
**Autores:** Métodos Mixtos (Daniel Wiesner, Javier Guerra, Laura Tamayo)

---

## 1. Resumen Ejecutivo

El Sistema de Monitoreo de Bosques y Páramos de Bogotá (SIMBYP) es una plataforma de análisis geoespacial automatizado que integra múltiples fuentes de datos satelitales para el monitoreo continuo de cobertura terrestre, deforestación y expansión urbana en el área metropolitana de Bogotá.

### 1.1 Alcance del Sistema
- **Cobertura geográfica:** Área metropolitana de Bogotá y zonas de páramo
- **Frecuencia de operación:** Trimestral (alertas), semestral (expansión urbana), anual (reportes históricos)
- **Volumen de datos:** ~50-100 GB anuales (imágenes satelitales, capas vectoriales, reportes)
- **Usuarios:** Analistas GIS, funcionarios SDP (Secretaría Distrital de Planeación)

---

## 2. Arquitectura General del Sistema

### 2.1 Stack Tecnológico

#### Lenguajes y Frameworks
- **Python 3.13.9:** Lenguaje principal
- **Google Earth Engine (GEE):** Procesamiento de imágenes satelitales en la nube
- **Conda:** Gestión de entornos virtuales

#### Librerías Principales
```python
# Procesamiento Geoespacial
earthengine-api      # API de Google Earth Engine
geopandas 1.1.1      # Operaciones vectoriales (CRS, buffer, envelope)
geemap               # Interfaz Python-GEE
shapely              # Geometrías (Point, Polygon, box, convex_hull)
rasterio             # Lectura/escritura de rasters
rasterstats          # Estadísticas zonales

# Visualización
folium               # Mapas interactivos web
matplotlib           # Gráficos estáticos
seaborn              # Visualización estadística
contextily           # Mapas base

# Datos y Reportes
pandas               # Manipulación de datos tabulares
jinja2               # Templates HTML para reportes
openpyxl             # Generación de Excel
python-dotenv        # Variables de entorno
```

#### APIs Externas
- **Google Earth Engine API:** Catálogo de imágenes satelitales (Sentinel-2, Dynamic World, Hansen)
- **Global Forest Watch API:** Alertas integradas de deforestación (GLAD-L, GLAD-S2, RADD)
- **Sentinel Hub API (Copernicus):** Descarga directa de imágenes Sentinel-2

### 2.2 Arquitectura de Componentes

```
bosques-bog/
├── gfw_alerts/              # Módulo 1: Alertas de Deforestación
├── urban_sprawl/            # Módulo 2: Expansión Urbana
├── dynamic_world/           # Módulo 3: Cobertura Terrestre
├── deforestation_reports/   # Módulo 4: Reportes Históricos
├── sentinel-images-download/ # Librería compartida
└── notebooks_de_referencia/ # Scripts de desarrollo
```

**Patrón arquitectónico:** Microservicios modulares con pipelines independientes

---

## 3. Módulos del Sistema

### 3.1 Módulo GFW Alerts (Alertas de Deforestación)

#### 3.1.1 Propósito
Detectar y reportar eventos de deforestación reciente mediante alertas satelitales integradas de Global Forest Watch.

#### 3.1.2 Arquitectura Interna
```
gfw_alerts/
├── main.py                      # Pipeline principal
├── area_estudio_dissolved.geojson  # AOI (Área de Interés)
├── src/
│   ├── download_gfw_data.py     # Descarga desde API GFW
│   ├── process_gfw_alerts.py    # Clustering y procesamiento
│   ├── download_sentinel_images.py  # Descarga imágenes Sentinel-2
│   ├── maps.py                  # Generación de mapas Folium
│   ├── create_final_json.py     # Estructura JSON de reporte
│   ├── regenerate_maps.py       # Sistema de regeneración
│   └── check_tiles_status.py    # Validación de tiles
└── reporte/
    ├── render_report.py         # Motor de plantillas Jinja2
    └── report_template.html     # Template HTML
```

#### 3.1.3 Flujo de Datos

**Fase 1: Descarga de Alertas**
```mermaid
API GFW → CSV → GeoDataFrame (EPSG:4326) → Filtrado por confianza → GeoJSON
```

**Fase 2: Clustering Espacial**
```python
# Algoritmo DBSCAN ajustado por área
def cluster_alerts_by_section(alerts_gdf, eps_km=2.5):
    """
    - Proyecta a UTM para cálculos métricos
    - DBSCAN con eps variable según densidad
    - Asigna cluster_id (-1 = noise)
    """
    utm_crs = alerts_gdf.estimate_utm_crs()
    alerts_proj = alerts_gdf.to_crs(utm_crs)
    clustering = DBSCAN(eps=eps_km*1000, min_samples=3)
    return alerts_gdf
```

**Fase 3: Generación de Bounding Boxes**
```python
def get_cluster_bboxes(alerts_clusters_gdf, buffer_m=2000):
    """
    1. Estima CRS UTM dinámico
    2. Buffer de 2000m alrededor de alertas
    3. unary_union.envelope para bbox rectangular
    4. Retorna en EPSG:4326
    """
    utm_crs = alerts_clusters_gdf.estimate_utm_crs()
    alerts_proj = alerts_clusters_gdf.to_crs(utm_crs)
    cluster_geom = group.geometry.buffer(buffer_m).unary_union.envelope
    return bboxes_gdf.to_crs(epsg=4326)
```

**Fase 4: Descarga de Imágenes Sentinel-2**
```python
# Via Google Earth Engine
collection = ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
    .filterBounds(bbox_ee)
    .filterDate(alert_date - 30d, alert_date + 30d)
    .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 30))
    .median()  # Composite mediano
```

**Fase 5: Visualización con Folium**
```python
# Crítico: Basemap como TileLayer explícito
m = folium.Map(location=[lat, lon], zoom_start=12, tiles=None)
folium.TileLayer(tiles="CartoDB positron", overlay=False).add_to(m)
folium.TileLayer(tiles=tile_url, name="Sentinel-2", overlay=True).add_to(m)
```

#### 3.1.4 Estructura de Salida
```
ONEDRIVE_PATH/outputs/Trimestre_I_trim_2025/
├── alertas_gfw_processed.geojson     # Alertas con cluster_id
├── cluster_bboxes.geojson            # Bounding boxes
├── reporte_definitivo_I_2025.html    # Reporte final
├── sentinel_imagenes/
│   ├── cluster_1_map_sentinel.html
│   ├── cluster_2_map_sentinel.html
│   └── ...
└── summary.json                      # Estadísticas agregadas
```

#### 3.1.5 Sistema de Regeneración de Tiles

**Problema:** Tiles de Earth Engine expiran después de 3-7 días

**Solución:** Sistema automático de detección y regeneración
```python
# check_tiles_status.py
def check_tile_status(tile_url: str) -> dict:
    response = requests.head(tile_url, timeout=10)
    return {
        "url": tile_url,
        "status": response.status_code,
        "accessible": response.status_code == 200
    }

# regenerate_maps.py
# Reutiliza clusters y bboxes existentes
# Regenera solo imágenes Sentinel y mapas HTML
# Mantiene 100% consistencia visual con main.py
```

**Ventajas:**
- No recalcula alertas ni clusters (costoso)
- Regenera solo tiles expirados
- Validación con check_tiles_status.py

---

### 3.2 Módulo Urban Sprawl (Expansión Urbana)

#### 3.2.1 Propósito
Cuantificar y mapear la expansión de áreas urbanas sobre zonas de protección ambiental mediante análisis temporal de Dynamic World.

#### 3.2.2 Arquitectura Interna
```
urban_sprawl/
├── main.py
├── src/
│   ├── config.py               # Rutas y parámetros
│   ├── aux_utils.py            # Autenticación GEE, geometrías
│   ├── pipeline_utils.py       # Orquestación de pipeline
│   ├── stats_utils.py          # Cálculo de áreas, intersecciones
│   ├── maps_utils.py           # Mapas con overlays
│   ├── regenerate_maps.py      # Sistema de regeneración
│   └── check_tiles_status.py   # Validación de tiles
└── reporte/
    ├── render_report.py
    └── report_template.html
```

#### 3.2.3 Flujo de Procesamiento

**1. Parámetros Temporales**
```python
# Comparación T1 (6 meses atrás) vs T2 (actual)
T1 = último_día_mes_anterior  # e.g., 2024-06-30
T2 = último_día_mes_actual     # e.g., 2024-12-31
```

**2. Procesamiento Dynamic World**
```python
# Clasificación de cobertura (0-8)
# 0: Water, 1: Trees, 2: Grass, 3: Flooded vegetation
# 4: Crops, 5: Shrub & scrub, 6: Built area, 7: Bare ground, 8: Snow & ice

dw_t1 = ee.ImageCollection("GOOGLE/DYNAMICWORLD/V1")
    .filterBounds(aoi)
    .filterDate(t1, t1)
    .mode()  # Clase más frecuente

dw_t2 = similar para T2

# Extracción de clase 6 (Built area)
urban_t1 = dw_t1.select('label').eq(6)
urban_t2 = dw_t2.select('label').eq(6)

# Cálculo de expansión
new_urban = urban_t2.And(urban_t1.Not())
```

**3. Análisis de Intersecciones**
```python
# Capas de protección
SAC: Estructura Ecológica Principal - Área de Manejo Especial del Suelo Rural
RESERVA: Reserva Forestal Protectora Bosque Oriental
EEP: Estructura Ecológica Principal del Suelo Urbano
UPL: Unidades de Planeamiento Local (urbano)

# Cálculo de áreas afectadas
for capa in [SAC, RESERVA, EEP, UPL]:
    intersection = gpd.overlay(new_urban_gdf, capa, how='intersection')
    area_ha = intersection.to_crs(utm_crs).area.sum() / 10000
```

**4. Métricas de Salida**
- Hectáreas de nueva urbanización total
- Hectáreas en cada capa de protección
- Porcentaje de afectación por zona
- Mapas de cambio (T1 → T2)

#### 3.2.4 Estructura de Salida
```
BASE_PATH/urban_sprawl/outputs/2025_01/
├── dynamic_world/
│   ├── built_area_prev.tif
│   ├── built_area_curr.tif
│   └── new_urban.geojson
├── intersections/
│   ├── urban_SAC.geojson
│   ├── urban_RESERVA.geojson
│   ├── urban_EEP.geojson
│   └── urban_UPL.geojson
├── mapas/
│   ├── mapa_expansion.html
│   └── mapa_intersecciones.html
└── reporte_enero_2025.html
```

---

### 3.3 Módulo Dynamic World (Cobertura Terrestre)

#### 3.3.1 Propósito
Análisis multi-temporal de cambios en cobertura terrestre usando el dataset Dynamic World de Google, con enfoque en transiciones de vegetación.

#### 3.3.2 Arquitectura Interna
```
dynamic_world/
├── main.py
├── src/
│   ├── config.py
│   ├── aux_utils.py          # Grilla de análisis, logging
│   ├── dw_utils.py           # Descarga DW, cálculo transiciones
│   ├── maps_utils.py         # Generación de mapas
│   └── reports/
│       ├── render_report.py
│       └── report_template.html
```

#### 3.3.3 Metodología de Grilla

**Problema:** Análisis pixel-by-pixel es costoso y difícil de interpretar

**Solución:** Grilla de análisis de 100m × 100m
```python
def create_grid(aoi_path: str, grid_size: int = 100) -> gpd.GeoDataFrame:
    """
    Crea grilla regular sobre AOI
    - grid_size: 100m (ajustable)
    - CRS: UTM para precisión métrica
    - Output: GeoDataFrame con cell_id
    """
    aoi = gpd.read_file(aoi_path)
    utm_crs = aoi.estimate_utm_crs()
    aoi_utm = aoi.to_crs(utm_crs)
    
    # Crear polígonos de grilla
    grid_cells = []
    for x in range(xmin, xmax, grid_size):
        for y in range(ymin, ymax, grid_size):
            cell = box(x, y, x+grid_size, y+grid_size)
            grid_cells.append(cell)
    
    return gpd.GeoDataFrame(geometry=grid_cells, crs=utm_crs)
```

#### 3.3.4 Cálculo de Transiciones
```python
def compute_transitions(dw_before, dw_current, grid_path):
    """
    Por cada celda de grilla:
    1. Cuenta píxeles de cada clase en T1 y T2
    2. Calcula transiciones clave:
       - Trees (1) → Other: Pérdida de bosque
       - Other → Built (6): Urbanización
       - Grass/Crops → Trees: Regeneración
    3. Retorna DataFrame con estadísticas por celda
    """
    results = []
    for idx, cell in grid.iterrows():
        stats_before = zonal_stats(cell.geometry, dw_before, stats=['count'])
        stats_current = zonal_stats(cell.geometry, dw_current, stats=['count'])
        
        transitions = {
            'cell_id': idx,
            'n_1_a_otro': loss_trees,    # Deforestación
            'n_otro_a_6': new_urban,     # Urbanización
            'pct_cambio': (curr - prev) / prev * 100
        }
        results.append(transitions)
    
    return pd.DataFrame(results)
```

#### 3.3.5 Casos de Uso
- Monitoreo trimestral de páramos (Sumapaz, Altiplano)
- Detección de regeneración natural post-incendio
- Validación de políticas de restauración ecológica

---

### 3.4 Módulo Deforestation Reports (Reportes Históricos)

#### 3.4.1 Propósito
Generación de reportes anuales de pérdida de cobertura arbórea utilizando el dataset Hansen Global Forest Change (2000-2024).

#### 3.4.2 Características Clave
- **Dataset:** Hansen Global Forest Change v1.12
- **Resolución:** 30m por píxel
- **Período:** 2000-2024 (actualización anual)
- **Output:** Reportes HTML por predio con mapas y gráficos temporales

#### 3.4.3 Flujo Simplificado
```python
# Hansen dataset en GEE
hansen = ee.Image("UMD/hansen/global_forest_change_2024_v1_12")
tree_cover_2000 = hansen.select('treecover2000')  # Cobertura inicial
loss_year = hansen.select('lossyear')             # Año de pérdida (00-24)

# Por cada predio
for predio in predios_gdf.iterrows():
    loss_stats = extract_loss_by_year(predio.geometry, loss_year)
    # loss_stats = {2010: 2.3 ha, 2015: 1.8 ha, ...}
    
    plot_temporal_series(loss_stats)
    generate_predio_report(predio, loss_stats)
```

---

## 4. Gestión de Configuración y Credenciales

### 4.1 Archivo .env (dot_env_content.env)
```dotenv
# Ubicación: bosques-bog/../dot_env_content.env
# Cargado por python-dotenv

# === Google Earth Engine ===
GCP_PROJECT=bosques-bogota-416214

# === Global Forest Watch ===
GFW_USERNAME=vmetodosmixtos@gmail.com
GFW_PASSWORD=Vestigium2025!
EMAIL=vmetodosmixtos@gmail.com
ORG=SDP

# === Sentinel Hub (Copernicus) ===
COPERNICUS_CLIENTID=sh-e86da746-2170-45be-8c53-4fad15a8d7fb
COPERNICUS_CLIENT_SECRET=sjL3AusySIBPtDaPTfJZPjMA48qzPzWZ
COPERNICUS_USERID=dwiesner@metodosmixtos.com
COPERNICUS_PASSWORD=kehruM-nynjy2-siqhoj

# === Rutas de Datos (OneDrive) ===
ONEDRIVE_PATH=C:/Users/Laura Tamayo/OneDrive - Vestigium Métodos Mixtos Aplicados SAS/Archivos de Daniel Wiesner - simbyp_data/gfw
INPUTS_PATH=C:/Users/Laura Tamayo/OneDrive - Vestigium Métodos Mixtos Aplicados SAS/Archivos de Daniel Wiesner - simbyp_data
```

### 4.2 Patrón de Carga
```python
# En cada main.py
from pathlib import Path
from dotenv import load_dotenv

# Ruta relativa desde módulo a raíz del proyecto
env_path = Path(__file__).parent.parent.parent / "dot_env_content.env"
load_dotenv(env_path)

# Uso
import os
project = os.getenv("GCP_PROJECT")
```

---

## 5. Sistemas de Regeneración de Mapas

### 5.1 Problema de Tiles Efímeros
**Google Earth Engine tiles:** URLs temporales válidas por 3-7 días
```
https://earthengine.googleapis.com/v1/projects/.../thumbnails/a1b2c3d4...
→ Expira después de 7 días (HTTP 404)
```

### 5.2 Arquitectura de Solución

#### Componente 1: Detección de Estado
```python
# check_tiles_status.py (gfw_alerts, urban_sprawl, dynamic_world)
def check_all_maps(trimestre: str, anio: int):
    """
    1. Lee HTMLs de mapas existentes
    2. Extrae URLs de tiles (regex)
    3. Valida con requests.head()
    4. Reporte: tiles_ok, tiles_expirados
    """
    expired_maps = []
    for html_file in output_dir.glob("*.html"):
        tile_urls = extract_tile_urls(html_file)
        for url in tile_urls:
            if requests.head(url).status_code != 200:
                expired_maps.append(html_file.stem)
    
    return expired_maps
```

#### Componente 2: Regeneración Inteligente
```python
# regenerate_maps.py (cada módulo)
def regenerate_expired_maps(trimestre: str, anio: int):
    """
    NO recalcula:
    - Alertas / clusters / bboxes (ya guardados en GeoJSON)
    - Estadísticas (summary.json)
    
    SÍ recalcula:
    - Tiles de Earth Engine (nueva descarga)
    - Archivos HTML (regeneración completa)
    
    Garantía: Visualización 100% idéntica a main.py
    """
    # Cargar datos pre-procesados
    alerts = gpd.read_file("alertas_gfw_processed.geojson")
    bboxes = gpd.read_file("cluster_bboxes.geojson")
    
    # Regenerar solo mapas
    for cluster_id, bbox in bboxes.iterrows():
        tile_url = download_sentinel_image(bbox.geometry, date)
        create_folium_map(bbox, tile_url, output_html)
```

#### Componente 3: Consistencia Visual
**Clave:** `regenerate_maps.py` debe replicar **exactamente** la lógica de `main.py`

**Ejemplo GFW Alerts:**
```python
# main.py usa:
clusters_bboxes = get_cluster_bboxes(alerts_with_clusters, buffer_m=2000)

# regenerate_maps.py DEBE usar:
utm_crs = cluster_alerts.estimate_utm_crs()
cluster_alerts_utm = cluster_alerts.to_crs(utm_crs)
cluster_geom_utm = cluster_alerts_utm.geometry.buffer(2000).unary_union.envelope
cluster_geom = gpd.GeoDataFrame(geometry=[cluster_geom_utm], crs=utm_crs).to_crs("EPSG:4326").iloc[0].geometry

# ❌ INCORRECTO (genera bboxes más pequeños):
buffer_deg = 500 / 111000  # Aproximación en grados
cluster_geom = box(minx, miny, maxx, maxy)
```

### 5.3 Workflow de Mantenimiento
```bash
# 1. Verificar estado (cada semana)
python gfw_alerts/src/check_tiles_status.py --trimestre I --anio 2025

# Output:
# ✅ Tiles accesibles: 8/10
# ❌ Tiles expirados: 2/10
#    - cluster_3_map_sentinel.html
#    - cluster_7_map_sentinel.html

# 2. Regenerar solo los expirados
python gfw_alerts/src/regenerate_maps.py --trimestre I --anio 2025

# Output:
# 🔄 Regenerando 2 mapas...
# ✅ Regenerados exitosamente: 2/2 mapas Sentinel
```

---

## 6. Patrones de Diseño y Best Practices

### 6.1 Gestión de Sistemas de Coordenadas (CRS)

#### Principio: CRS apropiado por tipo de operación
```python
# ✅ CORRECTO
# 1. Operaciones métricas → UTM dinámico
utm_crs = gdf.estimate_utm_crs()  # e.g., EPSG:32618 para Bogotá
gdf_utm = gdf.to_crs(utm_crs)
buffer_2km = gdf_utm.geometry.buffer(2000)  # 2000 metros reales

# 2. Visualización web → WGS84 (EPSG:4326)
gdf_wgs84 = gdf_utm.to_crs("EPSG:4326")
folium.GeoJson(gdf_wgs84)

# ❌ INCORRECTO
# Buffer en grados (impreciso, varía con latitud)
buffer_deg = 2000 / 111000  # Aproximación cruda
gdf.geometry.buffer(buffer_deg)  # ❌ Círculo distorsionado
```

#### Conversiones Críticas
```python
# estimate_utm_crs() → Selección inteligente de zona UTM
# - Bogotá: EPSG:32618 (UTM Zone 18N)
# - Calcula centroide, determina zona automáticamente

# Workflow estándar:
# EPSG:4326 (input) → UTM (procesar) → EPSG:4326 (output)
```

### 6.2 Geometrías Shapely

| Operación | Método | Uso |
|-----------|--------|-----|
| **Bbox rectangular** | `.envelope` | Bounding box mínimo alineado a ejes |
| **Bbox mínimo** | `.minimum_rotated_rectangle` | Bbox rotado óptimo |
| **Forma ajustada** | `.convex_hull` | Polígono convexo mínimo (puede ser no rectangular) |
| **Buffer circular** | `.buffer(dist)` | Expandir geometría (círculo/polígono) |
| **Bbox desde coords** | `box(minx, miny, maxx, maxy)` | Crear rectángulo explícito |

**Caso práctico GFW:**
```python
# Cluster de 5 alertas → bbox para imagen Sentinel
geoms = [Point(x1,y1), Point(x2,y2), ..., Point(x5,y5)]

# ❌ convex_hull: Puede dar forma irregular
hull = MultiPoint(geoms).convex_hull  

# ✅ buffer + envelope: Siempre rectangular
buffered = MultiPoint(geoms).buffer(2000)  # En CRS métrico
bbox = buffered.envelope  # Rectángulo alineado N-S, E-W
```

### 6.3 Folium: Overlay de Tiles

**Problema:** TileLayers no se muestran si el basemap está en el constructor de `Map()`

```python
# ❌ NO FUNCIONA
m = folium.Map(tiles="CartoDB positron", ...)
folium.TileLayer(tiles=sentinel_url, overlay=True).add_to(m)
# → Sentinel tiles invisibles

# ✅ SOLUCIÓN
m = folium.Map(tiles=None, ...)  # Sin basemap inicial
folium.TileLayer(tiles="CartoDB positron", overlay=False).add_to(m)  # Basemap explícito
folium.TileLayer(tiles=sentinel_url, overlay=True, show=True).add_to(m)  # Overlay visible
folium.LayerControl().add_to(m)
```

### 6.4 Imports de Módulos Python

#### Patrón 1: Ejecución Directa de Scripts
```python
# urban_sprawl/src/regenerate_maps.py
# Ejecutado como: python urban_sprawl/src/regenerate_maps.py

from urban_sprawl.src.config import AOI_PATH, BASE_PATH  # ✅ Ruta absoluta desde raíz
from urban_sprawl.src.aux_utils import authenticate_gee  # ✅
```

#### Patrón 2: Imports Relativos Intra-paquete
```python
# urban_sprawl/src/maps_utils.py
# Importado por otros módulos del mismo paquete

from .config import LOGO_PATH  # ✅ Relativo dentro de src/
from ..reporte.render_report import render  # ✅ Sube un nivel
```

#### Regla General
- **Scripts ejecutables directamente:** Imports absolutos con nombre del paquete
- **Módulos internos:** Imports relativos (`.` y `..`)

### 6.5 Manejo de Errores Geométricos

```python
# Problema: convex_hull de un solo punto retorna Point (no Polygon)
cluster_geom = alerts.union_all().convex_hull

if cluster_geom.geom_type == "Point":
    # Solución: Crear bbox explícito
    utm_crs = alerts.estimate_utm_crs()
    alerts_utm = alerts.to_crs(utm_crs)
    buffered = alerts_utm.geometry.buffer(2000)
    cluster_geom = buffered.unary_union.envelope
    cluster_geom = gpd.GeoDataFrame(geometry=[cluster_geom], crs=utm_crs).to_crs("EPSG:4326").iloc[0].geometry
```

---

## 7. Modelo de Datos

### 7.1 Formato GeoJSON - Alertas GFW
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Point",
        "coordinates": [-74.123, 4.567]
      },
      "properties": {
        "alert_id": "uuid-1234",
        "alert_date": "2025-01-15",
        "confidence": "highest",
        "alert_type": "glad_l",
        "cluster_id": 3,
        "area_ha": 0.27
      }
    }
  ]
}
```

### 7.2 Estructura JSON - Summary
```json
{
  "periodo": "Trimestre I 2025",
  "fecha_generacion": "2025-03-31",
  "area_estudio_ha": 123456.78,
  "total_alertas": 342,
  "alertas_por_tipo": {
    "glad_l": 245,
    "glad_s2": 67,
    "radd": 30
  },
  "alertas_por_confianza": {
    "highest": 180,
    "high": 120,
    "nominal": 42
  },
  "clusters": {
    "total": 28,
    "con_imagen_sentinel": 28
  },
  "area_afectada_ha": 156.34
}
```

### 7.3 Esquema de Base de Datos (Propuesto)

**Nota:** Actualmente el sistema usa archivos (CSV/GeoJSON). Para escalabilidad futura, considerar PostgreSQL + PostGIS:

```sql
-- Tabla de alertas
CREATE TABLE gfw_alerts (
    id SERIAL PRIMARY KEY,
    geometry GEOMETRY(Point, 4326),
    alert_date DATE,
    confidence VARCHAR(20),
    alert_type VARCHAR(20),
    cluster_id INTEGER,
    area_ha NUMERIC(10, 2),
    trimestre VARCHAR(20),
    anio INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Índices espaciales
CREATE INDEX idx_alerts_geom ON gfw_alerts USING GIST(geometry);
CREATE INDEX idx_alerts_date ON gfw_alerts(alert_date);
CREATE INDEX idx_alerts_cluster ON gfw_alerts(cluster_id);

-- Tabla de tiles (caché)
CREATE TABLE tile_cache (
    id SERIAL PRIMARY KEY,
    tile_url TEXT UNIQUE,
    bbox GEOMETRY(Polygon, 4326),
    generated_at TIMESTAMP,
    expires_at TIMESTAMP,
    status VARCHAR(20)  -- 'active', 'expired'
);
```

---

## 8. Despliegue y Operación

### 8.1 Requisitos del Sistema

#### Hardware
- **CPU:** 4 núcleos (recomendado 8+)
- **RAM:** 16 GB mínimo (32 GB recomendado para procesamiento paralelo)
- **Disco:** 200 GB SSD (datos + imágenes temporales)
- **Internet:** Conexión estable (descargas de GEE/GFW: 50-500 MB por sesión)

#### Software
- **OS:** Windows 10/11, macOS 11+, o Linux Ubuntu 20.04+
- **Python:** 3.9+ (desarrollado en 3.13.9)
- **Conda/Miniconda:** Para gestión de entornos
- **Git:** Control de versiones

### 8.2 Instalación

```bash
# 1. Clonar repositorio
git clone https://github.com/Metodos-Mixtos/bosques-bog.git
cd bosques-bog

# 2. Crear entorno Conda
conda create -n bosques-bog python=3.13
conda activate bosques-bog

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar credenciales
cp dot_env_content.env.example dot_env_content.env
# Editar dot_env_content.env con credenciales reales

# 5. Autenticar Google Earth Engine
earthengine authenticate
# Seleccionar proyecto: bosques-bogota-416214

# 6. Verificar instalación
python -c "import ee; ee.Initialize(project='bosques-bogota-416214'); print('✅ GEE OK')"
```

### 8.3 Ejecución de Pipelines

#### GFW Alerts (Trimestral)
```bash
cd gfw_alerts
python main.py --start-date 2025-01-01 --end-date 2025-03-31 --trimestre I --anio 2025

# Output: ONEDRIVE_PATH/outputs/Trimestre_I_trim_2025/
```

#### Urban Sprawl (Semestral)
```bash
cd urban_sprawl
python main.py --anio 2025 --mes 1  # Enero

# Output: BASE_PATH/urban_sprawl/outputs/2025_01/
```

#### Dynamic World (Trimestral)
```bash
cd dynamic_world
python main.py --anio 2025 --mes 3 --lookback 90

# Output: INPUTS_PATH/dynamic_world/outputs/2025_3/
```

### 8.4 Mantenimiento de Tiles

```bash
# Verificación semanal (automatizar con cron/Task Scheduler)
python gfw_alerts/src/check_tiles_status.py --trimestre I --anio 2025
python urban_sprawl/src/check_tiles_status.py --anio 2025 --mes 1
python dynamic_world/src/check_tiles_status.py --anio 2025 --mes 3

# Regeneración bajo demanda
python gfw_alerts/src/regenerate_maps.py --trimestre I --anio 2025
python urban_sprawl/src/regenerate_maps.py --anio 2025 --mes 1
python dynamic_world/src/regenerate_maps.py --anio 2025 --mes 3
```

### 8.5 Automatización con Cron (Linux/macOS)

```cron
# Verificación de tiles cada domingo a las 8 AM
0 8 * * 0 /home/user/bosques-bog/scripts/check_all_tiles.sh

# Alertas trimestrales (1 de abril, julio, octubre, enero)
0 2 1 1,4,7,10 * /home/user/bosques-bog/scripts/run_gfw_alerts.sh

# Urban sprawl semestral (1 de enero y julio)
0 3 1 1,7 * /home/user/bosques-bog/scripts/run_urban_sprawl.sh
```

### 8.6 Monitoreo y Logging

```python
# Implementar logging estándar en todos los módulos
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'logs/{module_name}_{datetime.now():%Y%m%d}.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)
logger.info("Pipeline iniciado")
logger.error("Error al descargar datos de GFW", exc_info=True)
```

---

## 9. Seguridad y Privacidad

### 9.1 Gestión de Credenciales

**Buenas prácticas implementadas:**
- ✅ Variables de entorno (`.env`) fuera del repositorio
- ✅ `.gitignore` incluye `dot_env_content.env`
- ✅ Credenciales no hardcodeadas en código

**Mejoras recomendadas:**
- 🔄 Rotación trimestral de contraseñas GFW y Copernicus
- 🔄 Uso de Google Secret Manager para producción
- 🔄 Autenticación OAuth2 en lugar de contraseñas

### 9.2 Control de Acceso

**Niveles de permisos:**
1. **Administrador:** Acceso completo a credenciales, ejecución de pipelines
2. **Analista:** Lectura de outputs, ejecución de regeneración de mapas
3. **Visualizador:** Solo acceso a reportes HTML finales

### 9.3 Datos Sensibles

- **Alertas de deforestación:** Coordenadas exactas pueden revelar actividades ilegales
- **Recomendación:** Agregar opción de anonimización (desplazar coordenadas ±100m) para compartir públicamente

---

## 10. Limitaciones y Trabajo Futuro

### 10.1 Limitaciones Actuales

#### Técnicas
- **Dependencia de APIs externas:** GEE, GFW, Sentinel Hub (vulnerables a cambios/discontinuación)
- **Tiles efímeros:** Requiere regeneración periódica (no hay caché permanente)
- **Procesamiento secuencial:** No hay paralelización (ej., descargar múltiples clusters simultáneamente)
- **Sin base de datos:** Dependencia de archivos dificulta consultas históricas complejas

#### Operativas
- **Ejecución manual:** Requiere intervención humana para cada período
- **Sin validación automática:** No hay tests unitarios ni CI/CD
- **Documentación dispersa:** READMEs en cada módulo, falta visión unificada (este documento mitiga esto)

### 10.2 Roadmap de Mejoras

#### Corto plazo (3 meses)
- [ ] **Tests automatizados:** Pytest para funciones críticas (clustering, bbox generation)
- [ ] **Caché de tiles persistente:** S3/Google Cloud Storage para tiles regenerados
- [ ] **Pipeline orchestration:** Airflow o Prefect para automatización

#### Mediano plazo (6 meses)
- [ ] **API REST:** Endpoint para consulta de alertas (`GET /api/alerts?date=2025-01-15`)
- [ ] **Dashboard interactivo:** Streamlit/Dash para exploración de datos en tiempo real
- [ ] **Base de datos:** Migración a PostgreSQL + PostGIS

#### Largo plazo (12 meses)
- [ ] **Machine Learning:** Predicción de zonas de alto riesgo de deforestación
- [ ] **Alertas en tiempo real:** Integración con webhook de GFW para notificaciones inmediatas
- [ ] **Aplicación móvil:** App para verificación en campo de alertas

---

## 11. Referencias Técnicas

### 11.1 Datasets y APIs

| Recurso | URL | Documentación |
|---------|-----|---------------|
| Google Earth Engine | https://earthengine.google.com | https://developers.google.com/earth-engine |
| Dynamic World | https://www.dynamicworld.app | https://developers.google.com/earth-engine/datasets/catalog/GOOGLE_DYNAMICWORLD_V1 |
| Global Forest Watch | https://www.globalforestwatch.org | https://data.globalforestwatch.org/documents/gfw::integrated-deforestation-alerts/about |
| Hansen Global Forest Change | https://glad.earthengine.app/view/global-forest-change | https://developers.google.com/earth-engine/datasets/catalog/UMD_hansen_global_forest_change_2024_v1_12 |
| Sentinel-2 | https://sentinel.esa.int/web/sentinel/missions/sentinel-2 | https://developers.google.com/earth-engine/datasets/catalog/COPERNICUS_S2_SR_HARMONIZED |

### 11.2 Librerías Clave

- **GeoPandas:** https://geopandas.org/
- **Shapely:** https://shapely.readthedocs.io/
- **Folium:** https://python-visualization.github.io/folium/
- **Earth Engine Python API:** https://developers.google.com/earth-engine/guides/python_install

### 11.3 Artículos Científicos

- Brown, C. F., et al. (2022). *Dynamic World, Near real-time global 10 m land use land cover mapping*. Scientific Data, 9(1), 251.
- Hansen, M. C., et al. (2013). *High-resolution global maps of 21st-century forest cover change*. Science, 342(6160), 850-853.
- Tyukavina, A., et al. (2022). *Global trends of forest loss due to fire from 2001 to 2019*. Frontiers in Remote Sensing, 3, 825190.

---

## 12. Contacto y Soporte

**Equipo de Desarrollo:**
- **Daniel Wiesner:** Arquitecto Principal - dwiesner@metodosmixtos.com
- **Javier Guerra:** Desarrollador Senior - jguerra@metodosmixtos.com
- **Laura Tamayo:** Analista GIS - ltamayo@metodosmixtos.com

**Organización:**  
Métodos Mixtos Aplicados SAS  
https://metodosmixtos.com

**Repositorio:**  
https://github.com/Metodos-Mixtos/bosques-bog

**Issues y Pull Requests:**  
https://github.com/Metodos-Mixtos/bosques-bog/issues

---

## Apéndice A: Glosario de Términos

| Término | Definición |
|---------|------------|
| **AOI** | Area of Interest - Área de estudio geográfica |
| **Bbox** | Bounding Box - Rectángulo envolvente mínimo de geometrías |
| **CRS** | Coordinate Reference System - Sistema de coordenadas espaciales |
| **DBSCAN** | Density-Based Spatial Clustering - Algoritmo de clustering por densidad |
| **DW** | Dynamic World - Dataset de cobertura terrestre de Google |
| **GEE** | Google Earth Engine - Plataforma de procesamiento geoespacial |
| **GFW** | Global Forest Watch - Sistema de monitoreo de bosques |
| **GLAD** | Global Land Analysis & Discovery - Sistema de alertas de UMD |
| **RADD** | Radar for Detecting Deforestation - Alertas por radar SAR |
| **Tile** | Imagen rasterizada servida como mapa web (formato XYZ o TMS) |
| **UTM** | Universal Transverse Mercator - Proyección métrica por zonas |
| **WGS84** | World Geodetic System 1984 - Datum global (EPSG:4326) |

---

## Apéndice B: Comandos de Diagnóstico

```bash
# Verificar instalación de dependencias
conda list | grep -E 'geopandas|earthengine|folium'

# Estado de autenticación GEE
earthengine authenticate --authorization-code=YOUR_CODE

# Test de conectividad APIs
python -c "
import requests
from dotenv import load_dotenv
import os

load_dotenv('../dot_env_content.env')

# Test GFW
gfw_user = os.getenv('GFW_USERNAME')
print(f'GFW User: {gfw_user}')

# Test GEE
import ee
ee.Initialize(project=os.getenv('GCP_PROJECT'))
print('✅ GEE initialized')
"

# Verificar espacio en disco (outputs grandes)
du -sh $ONEDRIVE_PATH/outputs/*
df -h  # Espacio disponible
```

---

**Fin del Documento de Arquitectura Técnica**  
*Última actualización: Diciembre 2025*  
*Versión: 2.0*
