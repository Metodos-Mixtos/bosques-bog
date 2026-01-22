"""
Funciones de utilidad para generar reportes de deforestación HTML. 
"""

import os
from pathlib import Path
import numpy as np
import pandas as pd
import geopandas as gpd
import folium
import rasterio
from rasterio import mask as rio_mask
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from shapely.geometry import box
import matplotlib.patches as mpatches
from shapely.geometry import mapping
import json
import locale
import warnings
import requests
from branca.element import Element, MacroElement, Template 



def pick_column(gdf: gpd.GeoDataFrame, candidates) -> str | None:
    """
    Devuelve el nombre de la primera columna existente en el GeoDataFrame, buscando de forma insensible a mayúsculas/minúsculas.
    Recorre la lista de nombres candidatos y retorna el nombre de la columna tal como aparece en el GeoDataFrame si existe.
    Si ninguna columna coincide, retorna None.
    Útil para encontrar columnas con nombres variables en diferentes archivos de shapefile.
    """
    if gdf is None or gdf.empty:
        return None
    lower = {c.lower(): c for c in gdf.columns}
    for name in candidates:
        if name.lower() in lower:
            return lower[name.lower()]
    return None

def ensure_dir(p: str | Path):
    Path(p).mkdir(parents=True, exist_ok=True)

def _relpath_for_html(target_path: str | Path, out_html_path: str | Path) -> str:
    """
    Calcula la ruta relativa desde el archivo HTML de salida hasta un recurso objetivo, como un iframe o una imagen.

    Esta función es útil para generar rutas relativas en archivos HTML, facilitando la correcta referencia a recursos estáticos
    cuando se desplazan los archivos o se generan en diferentes ubicaciones.

    Args:
        target_path (str | Path): Ruta al recurso objetivo (por ejemplo, imagen o archivo a incrustar).
        out_html_path (str | Path): Ruta al archivo HTML desde el cual se referenciará el recurso.

    Returns:
        str: Ruta relativa desde el archivo HTML hasta el recurso objetivo.
    """
    """Ruta desde la carpeta del archivo HTML hasta el recurso objetivo (iframe/img)."""
    return os.path.relpath(str(target_path), start=os.path.dirname(str(out_html_path)))


# Helpers

def set_spanish_decimal_locale():
    """Intenta establecer una configuración regional con decimales en coma para mostrar números de forma legible y congruente en el reporte."""
    for loc in ("es_CO.UTF-8", "es_ES.UTF-8", "es_ES", "es_CO", "Spanish_Spain"):
        try:
            locale.setlocale(locale.LC_NUMERIC, loc)
            return
        except Exception:
            continue

def fmt_ha(x: float) -> str:
    """Formatea hectáreas con decimales en coma (a prueba de fallos)."""
    try:
        s = f"{x:,.2f}"
        return s.replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return f"{x:.2f}"


# Elementos en mapas

def add_north_arrow(ax, pos=(0.06, 0.86), length=0.10, color="black"):
    """
    Dibuja una flecha de norte apuntando hacia ARRIBA en coordenadas de fracción de ejes.
    pos = posición de la base de la flecha; length = longitud en unidades de fracción de ejes.
    """
    ax.annotate(
        "", xy=(pos[0], pos[1] + length), xytext=pos,
        xycoords="axes fraction",
        arrowprops=dict(arrowstyle="-|>", color=color, linewidth=1.6,
                        shrinkA=0, shrinkB=0)
    )
    ax.text(pos[0], pos[1] + length + 0.02, "N",
            transform=ax.transAxes, ha="center", va="bottom",
            fontsize=11, color=color)

def _approx_km_per_deg_lon(lat_deg):
    # 1° longitud ≈ 111.320 * cos(latitud) km
    return 111.320 * np.cos(np.deg2rad(lat_deg))

def add_attribution(ax, text="Fuente: Hansen Global Forest Change 2024",
                    loc="lower left", fontsize=9, color="dimgray", alpha=0.8):
    """
    Escribe una pequeña etiqueta de atribución dentro de los ejes, usando coordenadas fraccionarias de los ejes.
    loc: 'lower left' | 'lower right' | 'upper left' | 'upper right' | 'lower center' | 'upper center'
    """
    loc = (loc or "").lower().strip()
    x_map = {
        "lower left": 0.01, "upper left": 0.01,
        "lower right": 0.99, "upper right": 0.99,
        "lower center": 0.50, "upper center": 0.50,
    }
    y_map = {
        "lower left": 0.01, "lower right": 0.01, "lower center": 0.01,
        "upper left": 0.99, "upper right": 0.99, "upper center": 0.99,
    }
    x = x_map.get(loc, 0.01)
    y = y_map.get(loc, 0.01)
    ha = "left" if x < 0.5 else ("center" if x == 0.5 else "right")
    va = "bottom" if y < 0.5 else "top"
    ax.text(x, y, text, transform=ax.transAxes, ha=ha, va=va,
            fontsize=fontsize, color=color, alpha=alpha)

def add_scalebar_lonlat(ax, gdf_wgs, loc="lower center",
                        max_frac=0.28, pad_frac=0.06, segments=4):
    """
    Barra de escala aproximada para mapas en EPSG:4326 (lat/lon).
    Elige una longitud "agradable" en metros/kilómetros (<= max_frac del ancho del bounding box).
    Dibuja en la parte inferior central por defecto; usa metros para barras cortas y kilómetros para largas.
    """
    xmin, ymin, xmax, ymax = gdf_wgs.total_bounds
    lat_mid = (ymin + ymax) / 2.0
    meters_per_deg_lon = 111_320.0 * np.cos(np.deg2rad(lat_mid))
    width_deg = (xmax - xmin)
    height_deg = (ymax - ymin)
    width_m = max(1e-6, width_deg * meters_per_deg_lon)

    # longitud objetivo (<= max_frac del ancho del bounding box)
    target_m = width_m * max_frac
    nice_m = np.array([100, 200, 500, 1000, 2000, 5000, 10_000, 20_000, 50_000, 100_000])
    Lm = nice_m[nice_m <= target_m]
    Lm = Lm[-1] if len(Lm) else nice_m[0]
    Ldeg = Lm / meters_per_deg_lon

    # posición
    x_center = (xmin + xmax) / 2.0
    x0 = x_center - Ldeg / 2.0
    x1 = x_center + Ldeg / 2.0
    y0 = ymin + height_deg * pad_frac

    # dibuja segmentos (alternando negro/blanco)
    seg_w = Ldeg / segments
    for i in range(segments):
        xi0 = x0 + i * seg_w
        xi1 = xi0 + seg_w
        ax.plot([xi0, xi1], [y0, y0], lw=6, solid_capstyle="butt",
                color=("black" if i % 2 == 0 else "white"))
        ax.plot([xi0, xi1], [y0, y0], lw=1.1, color="black")

    # contorno + etiqueta
    ax.plot([x0, x1], [y0, y0], lw=1.2, color="black")

    if Lm >= 1000:
        label = f"{Lm/1000:.1f} km".rstrip("0").rstrip(".") + " km" if (Lm % 1000) else f"{int(Lm/1000)} km"
    else:
        label = f"{int(Lm)} m"
    ax.text(x_center, y0 + height_deg * 0.02, label, ha="center", va="bottom", fontsize=9, color="black")

# Otros helpers

def select_parcel(shp_path, objectid_val=None, lotcodigo_val=None) -> gpd.GeoDataFrame:
    """Devuelve un GeoDataFrame de una sola parcela que coincide con (OBJECTID, LOT_CODIGO)."""
    gdf = gpd.read_file(shp_path)
    mask = pd.Series([True] * len(gdf))
    if objectid_val is not None and "OBJECTID" in gdf.columns:
        mask &= (gdf["OBJECTID"].astype(str) == str(objectid_val))
    if lotcodigo_val is not None and "LOT_CODIGO" in gdf.columns:
        mask &= (gdf["LOT_CODIGO"].astype(str) == str(lotcodigo_val))

    sel = gdf.loc[mask].copy()
    if sel.empty:
        raise ValueError("No se encontró ninguna parcela que coincida con (OBJECTID, LOT_CODIGO). Verifique los valores de entrada.")
    if len(sel) > 1:
        sel = sel.dissolve().reset_index(drop=True)
    return sel

def context_map(parcel_gdf, aoi_path, out_html, legend_name: str | None = None,
                scale_position: str = "bottomleft"):
    """
    Mapa de contexto interactivo con: AOI (Área de Interés) y Predio, popup y tooltip informativos,
    leyenda en la esquina inferior derecha, flecha de norte en la esquina superior derecha,
    y UNA sola barra de escala métrica ubicada sobre los créditos de Esri para evitar superposición.
    Este mapa ayuda a visualizar la ubicación geográfica del predio seleccionado respecto al área de interés,
    mostrando información relevante en los popups y resaltando el predio con color rojo y el AOI en blanco.
    La barra de escala se ajusta dinámicamente y se posiciona para mantener la legibilidad del mapa.
    """
    ensure_dir(Path(out_html).parent)

    # data preparation (predio puntual)
    parcel_wgs = parcel_gdf.to_crs(4326) if (parcel_gdf.crs and parcel_gdf.crs.to_epsg() != 4326) else parcel_gdf
    parcel_wgs = parcel_wgs.copy()
    pred_col = pick_column(parcel_wgs, ["PREDIRECC","predirecc","Nombre","NOMBRE","nombre"])
    obj_col  = pick_column(parcel_wgs, ["OBJECTID","OBJECT_ID","objectid"])
    lot_col  = pick_column(parcel_wgs, ["lotCodigo","Lot_Codigo","lot_codigo","lotcodigo"])
    name_col = "__pred_name__"
    parcel_wgs[name_col] = str(legend_name) if legend_name else (
        parcel_wgs[pred_col].astype(str) if pred_col else "Predio"
    )

    aoi_geojson = None
    if aoi_path and Path(aoi_path).exists():
        aoi = gpd.read_file(aoi_path)
        aoi_wgs = aoi.to_crs(4326) if (aoi.crs and aoi.crs.to_epsg() != 4326) else aoi
        aoi_geojson = aoi_wgs.__geo_interface__

    cx, cy = parcel_wgs.geometry.unary_union.centroid.coords[0]
    m = folium.Map(location=[cy, cx], zoom_start=14, tiles="Esri.WorldImagery")

    if aoi_geojson:
        folium.GeoJson(
            data=aoi_geojson, name="AOI",
            style_function=lambda x: {"color":"white","weight":3,"fill":False}
        ).add_to(m)

    popup_fields = [name_col]; popup_alias = ["Predio: "]
    if obj_col: popup_fields.append(obj_col); popup_alias.append("OBJECT ID: ")
    if lot_col: popup_fields.append(lot_col); popup_alias.append("Lot código: ")
    popup = folium.GeoJsonPopup(fields=popup_fields, aliases=popup_alias,
                                localize=True, labels=True, sticky=False,
                                style="background-color:white;border-radius:6px;padding:8px;")
    tooltip = folium.GeoJsonTooltip(fields=[name_col], aliases=["Predio: "], sticky=False)

    folium.GeoJson(
        data=json.loads(parcel_wgs.to_json()),
        name="Predio",
        style_function=lambda x: {"color":"red","weight":3,"fill":True,"fillOpacity":0.25},
        highlight_function=lambda x: {"weight":4,"color":"#ff5a5a"},
        popup=popup, tooltip=tooltip
    ).add_to(m)

    xmin, ymin, xmax, ymax = parcel_wgs.total_bounds
    padx, pady = (xmax-xmin)*0.10, (ymax-ymin)*0.10
    m.fit_bounds([[ymin-pady, xmin-padx],[ymax+pady, xmax+padx]])

    # Estrella del norte
    m.get_root().html.add_child(Element("""
    <div style="position:absolute;top:16px;right:16px;z-index:9999;pointer-events:none;
                background:rgba(255,255,255,0.9);padding:6px 8px;border:1px solid #999;border-radius:8px;
                font-family:Arial,sans-serif;color:#111;text-align:center;">
      <div style="font-weight:700;margin-bottom:2px;">N</div>
      <div style="width:0;height:0;margin:0 auto;border-left:6px solid transparent;border-right:6px solid transparent;
                  border-bottom:12px solid #111;"></div>
      <div style="width:2px;height:28px;background:#111;margin:0 auto;"></div>
    </div>
    """))

    # Escala - REVISAR porque aún no aparece
    pos = scale_position if scale_position in {"bottomleft","bottomright"} else "bottomleft"

    scale_macro = MacroElement()
    scale_macro._template = Template("""
    {% macro script(this, kwargs) %}
    (function() {
      var map = {{this._parent.get_name()}};

      function addScaleOnce() {
        // Remove any existing scale controls (avoid duplicates / imperial)
        document.querySelectorAll('.leaflet-control-scale').forEach(function(n){
          if (n.parentNode) n.parentNode.removeChild(n);
        });

        // Add fresh metric-only scale at bottom-left
        L.control.scale({ position:'bottomleft', metric:true, imperial:false, maxWidth:120 }).addTo(map);

        // Move to bottom-right if requested
        if ('""" + pos + """' === 'bottomright') {
          var target = document.querySelector('.leaflet-bottom .leaflet-right');
          var el = document.querySelector('.leaflet-control-scale');
          if (target && el && el.parentNode !== target) target.appendChild(el);
        }
        normalize();
      }

      function normalize() {
        var el = document.querySelector('.leaflet-control-scale');
        if (!el) return;

        // Ensure only the metric line is present (if Leaflet injected imperial somehow)
        var lines = el.querySelectorAll('.leaflet-control-scale-line');
        if (lines.length > 1) { for (var i = 1; i < lines.length; i++) lines[i].remove(); }

        // Raise z-index so it's above the attribution; also raise the left/right containers
        var left  = document.querySelector('.leaflet-bottom .leaflet-left');
        var right = document.querySelector('.leaflet-bottom .leaflet-right');
        if (left)  left.style.zIndex  = 1400;
        if (right) right.style.zIndex = 1300;
        el.style.zIndex = 1500;

        // Lift above the credits dynamically
        var attr = document.querySelector('.leaflet-control-attribution');
        var h = (attr && attr.offsetHeight ? attr.offsetHeight : 18) + 18; // padding
        el.style.marginBottom = h + 'px';
        el.style.marginLeft   = '8px';
        el.style.marginRight  = '8px';
      }

      map.on('load', function(){ addScaleOnce(); });
      map.on('moveend', normalize);
      window.addEventListener('resize', normalize);
      setTimeout(addScaleOnce, 0);
    })();
    {% endmacro %}
    """)
    m.get_root().add_child(scale_macro)

    m.get_root().header.add_child(Element("""
    <style>
      .leaflet-control-scale { background: rgba(255,255,255,0.92); padding: 2px 6px; border-radius: 6px; }
      .leaflet-control-scale-line { background: rgba(255,255,255,0.98);
        box-shadow: 0 1px 2px rgba(0,0,0,.25); border: 2px solid #444; border-top: none; }
    </style>
    """))

    # Leyenda (bottom-right)
    name_for_legend = str(parcel_wgs[name_col].iloc[0])
    m.get_root().html.add_child(Element(f"""
    <div style="position:absolute;right:16px;bottom:48px;z-index:1600;background:white;
                padding:8px 10px;border:1px solid #999;border-radius:8px;font-size:12px;
                box-shadow:0 1px 4px rgba(0,0,0,.2);">
      <div style="display:flex;align-items:center;gap:6px;margin-bottom:6px;">
        <span style="display:inline-block;width:18px;height:12px;border:2px solid red;background:rgba(255,0,0,.25);"></span>
        <span>Predio: {name_for_legend}</span>
      </div>
      <div style="display:flex;align-items:center;gap:6px;">
        <span style="display:inline-block;width:18px;height:12px;border:2px solid #fff;background:#fff;
                     box-shadow:inset 0 0 0 1px #aaa;"></span>
        <span>AOI</span>
      </div>
    </div>
    """))

    folium.LayerControl(position="topleft").add_to(m)
    m.save(out_html)
    return out_html

def plot_deforestation_map(
    raster_path, gdf, names_column, name_of_area,
    year_start, year_end, output_folder="."
):
    """
    Mapa PNG estático de bosque (verde) y pérdida (rojo) estrictamente dentro del polígono del predio.

    Funciona con:
      • Stack Hansen de 3 bandas: [treecover2000, loss, lossyear] (uint8)
      • 1 banda lossyear (uint8)
    """
    # Crear carpeta de salida con manejo robusto
    output_folder_path = Path(output_folder)
    output_folder_path.mkdir(parents=True, exist_ok=True)
    
    # Simplificar nombre: solo el año, ya que la carpeta tiene el ID del predio
    output_path = output_folder_path / f"mapa_{year_start}_{year_end}.png"
    
    # Diagnóstico: imprimir información del path
    print(f"   📁 Carpeta de salida: {output_folder_path}")
    print(f"   📁 ¿Existe?: {output_folder_path.exists()}")
    print(f"   📄 Archivo a crear: {output_path.name}")
    
    # Verificar que la carpeta existe antes de continuar
    if not output_folder_path.exists():
        raise RuntimeError(f"No se pudo crear la carpeta: {output_folder_path}")

    with rasterio.open(raster_path) as src:
        # CRS 
        if gdf.crs is None:
            raise ValueError("El GeoDataFrame no tiene CRS.")
        parcel_r = gdf.to_crs(src.crs) if gdf.crs != src.crs else gdf.copy()
        geoms = [mapping(geom) for geom in parcel_r.geometry]

        # Recorta usando la máscara real (el exterior permanece enmascarado)
        clipped, transform = rio_mask.mask(src, geoms, crop=True, filled=False)
        band_count = src.count

        # Máscara "inside": True donde los datos están dentro del polígono
        inside = ~np.ma.getmaskarray(clipped[0])
        rows, cols = inside.shape

        # Códigos Hansen para el periodo solicitado
        start_code = max(1, int(year_start - 2000))  
        end_code   = int(year_end   - 2000)

        # Condiciones para mostrar los pixeles dentro del polígono
        if band_count >= 3:
            tc2000  = clipped[0].filled(0).astype(np.uint8)
            loss    = clipped[1].filled(0).astype(np.uint8)
            lossyer = clipped[2].filled(0).astype(np.uint8)

            valid_forest = (tc2000 > 0)

            loss_bool = (
                inside & valid_forest &
                (loss == 1) &
                (lossyer >= start_code) & (lossyer <= end_code)
            )

            preserved_bool = (
                inside & valid_forest &
                ((loss == 0) | (lossyer > end_code))
            )

        elif band_count == 1:
            lossyer = clipped[0].filled(0).astype(np.uint8)

            loss_bool = (
                inside &
                (lossyer >= start_code) & (lossyer <= end_code)
            )
            # "Preserved" :nunca perdida mediante end_code
            preserved_bool = inside & (lossyer == 0)

        else:
            raise ValueError("El ráster debe tener 3 bandas (tc2000, loss, lossyear).")

        # Extent para imshow
        left, bottom, right, top = rasterio.transform.array_bounds(rows, cols, transform)
        extent = [left, right, bottom, top]

    # Construir RGBA without background 
    rgba = np.zeros((rows, cols, 4), dtype=float)
    green = (0.35, 0.60, 0.45)   # bosque
    red   = (0.85, 0.16, 0.16)   # loss

    if preserved_bool.any():
        r, g, b = green
        rgba[preserved_bool, 0] = r
        rgba[preserved_bool, 1] = g
        rgba[preserved_bool, 2] = b
        rgba[preserved_bool, 3] = 0.45

    if loss_bool.any():
        r, g, b = red
        rgba[loss_bool, 0] = r
        rgba[loss_bool, 1] = g
        rgba[loss_bool, 2] = b
        rgba[loss_bool, 3] = 0.75

    # Plot 
    fig, ax = plt.subplots(figsize=(9, 8), constrained_layout=True)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    if preserved_bool.any() or loss_bool.any():
        ax.imshow(rgba, extent=extent, interpolation="nearest", zorder=1)
    else:
        ax.text(0.5, 0.5, "Sin bosque en 2000 y/o sin pérdida en el periodo",
                transform=ax.transAxes, ha="center", va="center",
                fontsize=11, color="dimgray")

    # Polígono del predio
    parcel_r.boundary.plot(ax=ax, color="black", linewidth=1.1, zorder=2)
    for _, row in parcel_r.iterrows():
        c = row.geometry.centroid
        lab = str(row.get(names_column, "")).strip()
        if lab:
            ax.annotate(text=lab, xy=(c.x, c.y), ha="center", fontsize=6.5, color="black", zorder=3)

    # Leyenda
    legend1 = mpatches.Patch(color="#5a9a73", label=f"Bosque en {year_end}")
    legend2 = mpatches.Patch(color="#d92727", label=f"Pérdida {year_start}–{year_end}")
    ax.legend(handles=[legend1, legend2], loc="upper right", frameon=True)

    ax.set_title(f"Pérdida de bosque {year_start}-{year_end} en {name_of_area}")
    ax.set_xticks([]); ax.set_yticks([])

    # Vista alrededor del predio
    xmin, ymin, xmax, ymax = parcel_r.total_bounds
    dx = (xmax - xmin) * 0.10
    dy = (ymax - ymin) * 0.10
    ax.set_xlim(xmin - dx, xmax + dx)
    ax.set_ylim(ymin - dy, ymax + dy)
    ax.set_aspect("equal", adjustable="datalim")

    # Flecha del norte, escala y demás
    add_north_arrow(ax, pos=(0.06, 0.84), length=0.08, color="black")
    gdf_wgs = gdf.to_crs(4326) if (gdf.crs and gdf.crs.to_epsg() != 4326) else gdf
    add_scalebar_lonlat(ax, gdf_wgs=gdf_wgs, loc="lower center", segments=4)
    add_attribution(ax, "Fuente: Hansen Global Forest Change 2024", fontsize=9, loc="lower left")

    plt.savefig(str(output_path), bbox_inches="tight", dpi=300)
    plt.close()
    return str(output_path)

def def_anual(gdf, raster_path, year_min=2000, year_max=2024) -> pd.DataFrame:
    """
    Devuelve un DataFrame con la deforestación anual (ha) para el predio.
    Maneja el caso de 'sin pérdida' sin generar errores.
    """
    with rasterio.open(raster_path) as src:
        raster_crs = src.crs
        gdf_r = gdf.to_crs(raster_crs) if (gdf.crs and gdf.crs != raster_crs) else gdf
        geoms = [mapping(geom) for geom in gdf_r.geometry]
        clipped, transform = rio_mask.mask(src, geoms, crop=True, filled=True)
        band_count = src.count

        start_code = year_min - 2000
        end_code   = year_max - 2000

        if band_count == 1:
            lossyear = clipped[0]
            mask_lossyear = np.where((lossyear >= start_code) & (lossyear <= end_code), lossyear, 0)
        else:
            tc2000 = clipped[0]; loss = clipped[1]; lossyear = clipped[2]
            valid = (tc2000 > 0) & (loss == 1) & (lossyear >= start_code) & (lossyear <= end_code)
            mask_lossyear = np.where(valid, lossyear, 0)

    # Cuenta píxeles por código de año de pérdida
    vals, counts = np.unique(mask_lossyear, return_counts=True)

    results = []
    for v, c in zip(vals, counts):
        if int(v) == 0:
            continue  # 0 = no hay pérdida
        year = 2000 + int(v)
        area_ha = c * (30 * 30) / 10000.0  # 900 m² por píxel -> ha
        results.append({"year": int(year), "deforestation_ha": float(area_ha)})

    if not results:
        # Retorna un DataFrame vacío con el esquema esperado
        print("No hay pérdida de cobertura arbórea en los años especificados.")
        return pd.DataFrame(columns=["year", "deforestation_ha"])

    df = pd.DataFrame(results)
    df = df.sort_values("year").reset_index(drop=True)
    return df

# Sentinel-2 helpers (Toma de Google Earth Engine y la muestra como PNG en el HTML)

def _ee_init_once():
    """Inicialización GEE (no aparece ningún mensaje si ya está autenticado)."""
    import ee
    import os
    
    project = os.getenv("GCP_PROJECT")
    if not project:
        raise RuntimeError("GCP_PROJECT no está definido en .env")
    
    try:
        ee.Initialize(project=project)
    except Exception:
        ee.Authenticate()  # opens browser 1st time
        ee.Initialize(project=project)
    return ee

def _parcel_to_ee_geometry(parcel_gdf):
    """Devolver ee.Geometry del predio (uno solo) en EPSG:4326."""
    gdf_wgs = parcel_gdf.to_crs(4326)
    gj = json.loads(gdf_wgs.to_json())
    # dissolve in case multipart
    coords = gj["features"][0]["geometry"]["coordinates"]
    geom_type = gj["features"][0]["geometry"]["type"]
    import ee
    if geom_type == "Polygon":
        return ee.Geometry.Polygon(coords[0])
    elif geom_type == "MultiPolygon":
        return ee.Geometry.MultiPolygon(coords)
    else:
        # fallback: use bounds
        poly = gdf_wgs.geometry.unary_union.envelope
        return ee.Geometry.Polygon(list(poly.exterior.coords))

def _s2_cloudmask(image):
    """
    Máscara de nubes simple. Mejora la composición eliminando los píxeles marcados como nubes en QA60 antes de tomar la media anual.
    """
    qa = image.select('QA60')
    cloud_bit = 1 << 10
    cirrus_bit = 1 << 11
    mask = qa.bitwiseAnd(cloud_bit).eq(0).And(qa.bitwiseAnd(cirrus_bit).eq(0))
    return image.updateMask(mask)

def _s2_year_mean_rgb(ee_module, geom, year, max_cloud=60):
    """Devuelve una imagen RGB compuesta promedio (B4,B3,B2) de ee.Image para un año calendario."""
    ee = ee_module
    start = ee.Date.fromYMD(year, 1, 1)
    end   = ee.Date.fromYMD(year, 12, 31).advance(1, 'day')

    col = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
            .filterBounds(geom)
            .filterDate(start, end)
            .filter(ee.Filter.lte('CLOUDY_PIXEL_PERCENTAGE', max_cloud))
            .map(_s2_cloudmask)
            .select(['B4','B3','B2']))  # RGB - 10m 

    # Promedio de todas las imágenes del año en aoi libre de nubes

    img = col.mean().clip(geom)
    vis = {'bands': ['B4','B3','B2'], 'min': 0, 'max': 3000}
    return img.visualize(**vis)

def _square_region_from_parcel(parcel_gdf, pad_frac=0.12):
    """
    Devuelve un ee.Geometry.Rectangle (cuadrado) en EPSG:4326 que circunscribe el predio con un margen (pad_frac).
    El cuadrado garantiza un encuadre idéntico para ambos años y cualquier predio.
    """
    ee = _ee_init_once()
    gdf_wgs = parcel_gdf.to_crs(4326)
    xmin, ymin, xmax, ymax = gdf_wgs.total_bounds
    cx = (xmin + xmax) / 2.0
    cy = (ymin + ymax) / 2.0
    w = xmax - xmin
    h = ymax - ymin
    side = max(w, h) * (1.0 + pad_frac)  # añade márgenes
    half = side / 2.0
    rect = ee.Geometry.Rectangle(
        [cx - half, cy - half, cx + half, cy + half],
        proj=None, geodesic=False
    )
    return rect


def _annotate_s2_png(png_in: str,
                     out_png: str,
                     rect_bounds: tuple[float,float,float,float],
                     parcel_gdf: gpd.GeoDataFrame):
    """
    Redibuja el PNG de Sentinel-2 agregando:
      - contorno del predio (línea blanca delgada),
      - flecha de norte,
      - barra de escala (aprox. lon/lat).
    rect_bounds: (xmin, ymin, xmax, ymax) en EPSG:4326 del rectángulo cuadrado.
    """
    xmin, ymin, xmax, ymax = rect_bounds
    extent = [xmin, xmax, ymin, ymax]

    # Lee la imagen
    img = mpimg.imread(png_in)

    # Figura cuadrada
    fig, ax = plt.subplots(figsize=(6.0, 6.0), constrained_layout=True)
    ax.imshow(img, extent=extent, zorder=1)
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_aspect('equal')
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_facecolor("white")

    # Contorno del polígono del predio (blanco fino)
    parcel_wgs = parcel_gdf.to_crs(4326)
    parcel_wgs.boundary.plot(ax=ax, color="white", linewidth=1.2, zorder=3)

    # Flecha del norte
    add_north_arrow(ax, pos=(0.08, 0.86), length=0.08, color="white")

    # Barra de escala: usamos el rectángulo como "gdf" para su bounding box
    rect_poly = gpd.GeoDataFrame(geometry=[box(xmin, ymin, xmax, ymax)], crs=4326)
    add_scalebar_lonlat(ax, gdf_wgs=rect_poly, loc="lower center", segments=4)

    plt.savefig(out_png, dpi=200, bbox_inches="tight")
    plt.close(fig)

def _rect_bounds_from_region_info(region_info: dict) -> tuple[float,float,float,float]:
    """
    Extrae (xmin, ymin, xmax, ymax) de la geometría tipo Polygon (rectángulo) devuelta por EE (getInfo()).
    """
    # region_info es un diccionario geojson con claves: tipo, coordenadas
    coords = region_info.get("coordinates", [])
    if not coords:
        raise ValueError("No hay coordenadas en region_info.")
    ring = coords[0]  # lista de [lon,lat]
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    return (min(xs), min(ys), max(xs), max(ys))

def download_sentinel_year_pngs(parcel_gdf, year_start, year_end, out_dir, dim=1024):
    """
    Descarga 2 PNGs (media anual B4-B3-B2) con el MISMO encuadre cuadrado y
    luego los re-renderiza agregando:
      - contorno de predio (blanco),
      - flecha del norte,
      - barra de escala.
    Retorna rutas a PNGs finales (con overlays).
    """
    ensure_dir(out_dir)
    ee = _ee_init_once()

    # Región cuadrada común a ambos años
    region_rect = _square_region_from_parcel(parcel_gdf, pad_frac=0.12)
    region_info = region_rect.getInfo()                 # dict geojson
    rect_bounds = _rect_bounds_from_region_info(region_info)  # (xmin,ymin,xmax,ymax)

    # Imágenes visualizadas (RGB)
    img_start = _s2_year_mean_rgb(ee, region_rect, int(year_start))
    img_end   = _s2_year_mean_rgb(ee, region_rect, int(year_end))

    # Parámetros (usar dict completo como 'region')
    params = {
        'region': region_info,
        'dimensions': f'{int(dim)}x{int(dim)}',
        'format': 'png'
    }

    # URLs de png renderizados
    try:
        url_start = img_start.getThumbURL(params)
        url_end   = img_end.getThumbURL(params)
    except Exception:
        # fallback: solo coordenadas
        params_fb = dict(params, region=region_info.get('coordinates'))
        url_start = img_start.getThumbURL(params_fb)
        url_end   = img_end.getThumbURL(params_fb)

    # Rutas temporales (crudo) y finales (con overlays/anotaciones)
    raw_start = os.path.join(out_dir, f"sentinel_raw_{year_start}.png")
    raw_end   = os.path.join(out_dir, f"sentinel_raw_{year_end}.png")
    png_start = os.path.join(out_dir, f"sentinel_{year_start}.png")
    png_end   = os.path.join(out_dir, f"sentinel_{year_end}.png")

    # Descargar
    for url, path in [(url_start, raw_start), (url_end, raw_end)]:
        r = requests.get(url, timeout=180)
        r.raise_for_status()
        with open(path, 'wb') as f:
            f.write(r.content)

    # Re-render con anotaciones
    _annotate_s2_png(raw_start, png_start, rect_bounds, parcel_gdf)
    _annotate_s2_png(raw_end,   png_end,   rect_bounds, parcel_gdf)

    # (opcional) borrar crudos
    try:
        os.remove(raw_start); os.remove(raw_end)
    except Exception:
        pass

    return png_start.replace("\\","/"), png_end.replace("\\","/")


def build_html_report(
    title_text, logo_path, red_hex,
    context_map_html, defo_png, df_yearly, out_html,
    period_text, summary_area_ha=None,
    pred_name=None, objectid_val=None, lotcodigo_val=None,
    sentinel_png_start: str | None = None,
    sentinel_png_end:   str | None = None,
    header_img1_path: str | None = None,
    header_img2_path: str | None = None,
    footer_img_path: str | None = None
):
    """
    Crea el HTML final. Si se proporcionan imágenes Sentinel-2 (start/end),
    agrega una tarjeta al final con ambas.
    """
    # Paths relativos
    ensure_dir(Path(out_html).parent)
    context_rel = _relpath_for_html(context_map_html, out_html).replace("\\", "/")
    defo_rel    = _relpath_for_html(defo_png,        out_html).replace("\\", "/")
    logo_rel    = _relpath_for_html(logo_path,       out_html).replace("\\", "/") if (logo_path and Path(logo_path).exists()) else None
    
    # Paths relativos para las nuevas imágenes del header y footer
    header_img1_rel = _relpath_for_html(header_img1_path, out_html).replace("\\", "/") if (header_img1_path and Path(header_img1_path).exists()) else None
    header_img2_rel = _relpath_for_html(header_img2_path, out_html).replace("\\", "/") if (header_img2_path and Path(header_img2_path).exists()) else None
    footer_img_rel = _relpath_for_html(footer_img_path, out_html).replace("\\", "/") if (footer_img_path and Path(footer_img_path).exists()) else None

    # Valores de resumen 
    total_loss = 0.0
    if df_yearly is not None and len(df_yearly):
        total_loss = float(df_yearly["deforestation_ha"].sum())

    pred_txt = (pred_name or title_text).strip()
    obj_txt  = (str(objectid_val).strip() if objectid_val is not None else "—")
    lot_txt  = (str(lotcodigo_val).strip() if lotcodigo_val is not None else "—")
    area_txt = f"{fmt_ha(summary_area_ha)}" if (summary_area_ha is not None) else "—"

    # Etiquetas para los títulos Sentinel 
    per_str = str(period_text)
    pnorm = per_str.replace("—", "-").replace("–", "-")
    try:
        p_start_label = pnorm.split("-")[0].strip()
        p_end_label   = pnorm.split("-")[-1].strip()
    except Exception:
        p_start_label, p_end_label = per_str, per_str

    # CSS
    css = """
    <style>
      :root { --card-bg:#fff; --muted:#666; --border:#e7e7e7; }
      * { box-sizing:border-box; }
      body { margin:0; font-family:Arial, sans-serif; background:#fafafa; color:#222; }

      header.banner { background:#e3351f; width:100%; margin:0; padding:1.5rem 0; display:flex; justify-content:space-between; align-items:center; }
      header.banner img { height:70px; margin:0 2rem; }
      
      footer.banner { background:#e3351f; width:100%; margin:3rem 0 0 0; padding:1.5rem 0; text-align:center; }
      footer.banner img { height:70px; }

      .container { padding:18px; max-width:1150px; margin:0 auto; }
      h1 { margin:12px 0 4px; font-size:26px; }
      .range { color:#777; margin-bottom:14px; }

      .grid-2 { display:grid; grid-template-columns: 1.4fr 1fr; gap:16px; }
      .card { background:var(--card-bg); border:1px solid var(--border); border-radius:12px; padding:12px; }
      .card h2 { margin:6px 0 8px; font-size:16px; }

      iframe { width:100%; height:420px; border:none; border-radius:10px; }
      .note { color:var(--muted); font-size:12px; margin-top:8px; }

      .kv { margin-top:4px; }
      .kv .row { display:flex; justify-content:space-between; gap:12px; padding:6px 2px; border-bottom:1px solid #eee; }
      .kv .row:last-child { border-bottom:none; }
      .kv .k { font-weight:700; color:#111; }
      .kv .v { font-weight:400; color:#111; }

      .map-img { width:100%; border-radius:10px; border:1px solid var(--border); }
      table { width:100%; border-collapse:collapse; }
      th, td { border-bottom:1px solid var(--border); padding:8px; text-align:right; }
      th:first-child, td:first-child { text-align:left; }
    </style>
    """

    # Tabla de deforestación anual
    if df_yearly is not None and len(df_yearly):
        rows_html = "\n".join(
            f"<tr><td>{int(r.year)}</td><td>{fmt_ha(r['deforestation_ha'])}</td></tr>"
            for _, r in df_yearly.iterrows()
        )
        table_card = f"""
        <div class="card">
          <h2>Hectáreas perdidas por año</h2>
          <table>
            <thead><tr><th>Año</th><th>Pérdida (ha)</th></tr></thead>
            <tbody>{rows_html}</tbody>
          </table>
          <p class="note">Área de píxel ~ 30 m × 30 m (Hansen GFC).</p>
        </div>
        """
    else:
        table_card = """
        <div class="card">
          <h2>Hectáreas perdidas por año</h2>
          <p class="note">No se detectó deforestación en el rango de años especificado.</p>
        </div>
        """

    # Sentinel- 2
    sentinel_block = ""
    if sentinel_png_start and sentinel_png_end:
        s1 = _relpath_for_html(sentinel_png_start, out_html).replace("\\", "/")
        s2 = _relpath_for_html(sentinel_png_end,   out_html).replace("\\", "/")

        sentinel_css = """
        <style>
          .s2-img {
            width: 100%;
            height: 420px;       /* mismo alto para ambas */
            object-fit: contain; /* se ve TODO el polígono, sin recortes */
            background: #fff;
            border-radius: 10px;
            border: 1px solid var(--border);
          }
        </style>
        """

        sentinel_block = f"""
        {sentinel_css}
        <div class="grid-2" style="margin-top:16px;">
          <div class="card">
            <h2>Imagen Sentinel-2 – {p_start_label}</h2>
            <img class="s2-img" src="{s1}" alt="Sentinel-2 {p_start_label}">
            <p class="note">Fuente: Sentinel-2 (media anual), resolución 10 m.</p>
          </div>
          <div class="card">
            <h2>Imagen Sentinel-2 – {p_end_label}</h2>
            <img class="s2-img" src="{s2}" alt="Sentinel-2 {p_end_label}">
            <p class="note">Fuente: Sentinel-2 (media anual), resolución 10 m.</p>
          </div>
        </div>
        """

    # HTML principal
    html_top = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>{title_text}</title>
  {css}
</head>
<body>
  <header class="banner">
    <div class="brand">
      {f'<img src="{logo_rel}" alt="Secretaría de Planeación, Bogotá" style="height:70px;">' if logo_rel else ''}
      <div>
        <div class="title">Reporte de alertas de deforestación – PSAH</div>
        <div class="sub">Secretaría Distrital de Planeación – Bogotá</div>
      </div>
    </div>
  </header>

  <div class="container">
    <h1>{title_text}</h1>
    <div class="range">Rango: {period_text}</div>

    <div class="card">
      <h2>Metodología</h2>
      <p>
        Este reporte presenta las alertas de deforestación entre el rango de años especificado del predio seleccionado,
        el cual participa en el esquema de PSAH en Bogotá y 19 municipios aledaños. Incluye un mapa de contexto geográfico
        interactivo, un mapa de deforestación y una tabla de hectáreas de pérdida por año.
      </p>
    </div>

    <div class="grid-2">
      <div class="card">
        <h2>Mapa de contextualización geográfica del predio</h2>
        <iframe src="{context_rel}"></iframe>
        <p class="note">Fuente del mapa base: Esri World Imagery.</p>
      </div>
      <div class="card">
        <h2>Resumen</h2>
        <div class="kv">
          <div class="row"><span class="k">Predio</span><span class="v">{pred_txt}</span></div>
          <div class="row"><span class="k">OBJECT ID</span><span class="v">{obj_txt}</span></div>
          <div class="row"><span class="k">Lot código</span><span class="v">{lot_txt}</span></div>
          <div class="row"><span class="k">Área en hectáreas</span><span class="v">{area_txt}</span></div>
          <div class="row"><span class="k">Rango</span><span class="v">{period_text}</span></div>
          <div class="row"><span class="k">Pérdida total</span><span class="v">{fmt_ha(total_loss)} ha</span></div>
        </div>
      </div>
    </div>

    <div class="grid-2" style="margin-top:16px;">
      <div class="card">
        <h2>Mapa de deforestación</h2>
        <img class="map-img" src="{defo_rel}" alt="Mapa de deforestación">
      </div>
      {table_card}
    </div>
"""

    html_bottom = """
  </div>
</body>
</html>
"""

    # Ensambla todo (incluye Sentinel)
    full_html = html_top + sentinel_block + html_bottom

    with open(out_html, "w", encoding="utf-8") as f:
        f.write(full_html)

    return out_html
