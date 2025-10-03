"""
Utility functions to generate deforestation HTML reports.
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
import matplotlib.patches as mpatches
from shapely.geometry import mapping
import json
import locale
import warnings
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

from branca.element import Element, MacroElement, Template
import json

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

    # Escala - REVISAR
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
    ensure_dir(output_folder)
    safe_name = str(name_of_area).replace(" ", "_").replace("/", "_")
    output_path = os.path.join(
        output_folder, f"deforestacion_{safe_name}_{year_start}_a_{year_end}.png"
    )

    with rasterio.open(raster_path) as src:
        raster_crs = src.crs
        gdf_r = gdf.to_crs(raster_crs) if (gdf.crs and gdf.crs != raster_crs) else gdf
        geoms = [mapping(geom) for geom in gdf_r.geometry]

        # Recorte; fuera del polígono se rellena con 0
        clipped, transform = rio_mask.mask(src, geoms, crop=True, filled=True)
        band_count = src.count

        start_code = int(year_start - 2000)
        end_code   = int(year_end   - 2000)

        # Construye máscaras booleanas (True donde el píxel debe dibujarse)
        if band_count == 1:
            lossyear = clipped[0]
            loss_bool = (lossyear >= start_code) & (lossyear <= end_code)
            preserved_bool = (lossyear == 0)  # never lost up to end_code
        elif band_count >= 3:
            tc2000 = clipped[0]; loss = clipped[1]; lossyear = clipped[2]
            valid_forest = tc2000 > 0
            loss_bool = valid_forest & (loss == 1) & (lossyear >= start_code) & (lossyear <= end_code)
            preserved_bool = valid_forest & ((loss == 0) | (lossyear > end_code))
        else:
            raise ValueError("El ráster debe tener 1 banda (lossyear) o 3 bandas (tc2000, loss, lossyear).")

        # Extent for imshow (note cols, rows order)
        rows, cols = loss_bool.shape
        left, bottom, right, top = rasterio.transform.array_bounds(cols, rows, transform)
        extent = [left, right, bottom, top]

    # Construye una imagen RGBA transparente (sin colormap, sin gris)
    rgba = np.zeros((rows, cols, 4), dtype=float)  

    # Colores (0–1) — puedes ajustar si lo deseas
    green = (0.35, 0.60, 0.45)   # bosque preservado
    red   = (0.85, 0.16, 0.16)   # pérdida de cobertura arbórea

    # Dibuja primero el bosque preservado (debajo), luego la pérdida encima
    if preserved_bool.any():
        r, g, b = green
        rgba[preserved_bool, 0] = r
        rgba[preserved_bool, 1] = g
        rgba[preserved_bool, 2] = b
        rgba[preserved_bool, 3] = 0.45   # alpha

    if loss_bool.any():
        r, g, b = red
        rgba[loss_bool, 0] = r
        rgba[loss_bool, 1] = g
        rgba[loss_bool, 2] = b
        rgba[loss_bool, 3] = 0.75   # alpha

    # Plot 
    fig, ax = plt.subplots(figsize=(9, 8), constrained_layout=True)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    ax.imshow(rgba, extent=extent, interpolation="nearest", zorder=1)

    # Dibuja el contorno de la parcela y etiqueta opcional
    gdf_r.boundary.plot(ax=ax, color="black", linewidth=1.1, zorder=2)
    for _, row in gdf_r.iterrows():
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

    # Ajusta el marco para que la parcela llene mejor la vista
    xmin, ymin, xmax, ymax = gdf_r.total_bounds
    dx = (xmax - xmin) * 0.10
    dy = (ymax - ymin) * 0.10
    ax.set_xlim(xmin - dx, xmax + dx)
    ax.set_ylim(ymin - dy, ymax + dy)
    ax.set_aspect("equal", adjustable="datalim")

    # Flecha de norte y barra de escala (asegúrate de mantener los helpers mejorados)
    add_north_arrow(ax, pos=(0.06, 0.84), length=0.08, color="black")
    gdf_wgs = gdf.to_crs(4326) if (gdf.crs and gdf.crs.to_epsg() != 4326) else gdf
    add_scalebar_lonlat(ax, gdf_wgs=gdf_wgs, loc="lower center", segments=4)
    add_attribution(ax, "Fuente: Hansen Global Forest Change 2024", fontsize=9, loc="lower left")

    plt.savefig(output_path, bbox_inches="tight", dpi=300)
    plt.close()
    return output_path


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

def build_html_report(
    title_text, logo_path, red_hex,
    context_map_html, defo_png, df_yearly, out_html,
    period_text, summary_area_ha=None,
    pred_name=None, objectid_val=None, lotcodigo_val=None
):
    """
    Constructor final de HTML con seis filas en 'Resumen':
      Predio | OBJECT ID | Lot código | Área en hectáreas | Rango | Pérdida total
    Etiquetas en negrita, valores normales. Los recursos se referencian con rutas relativas.
    """
    # Paths
    ensure_dir(Path(out_html).parent)
    context_rel = _relpath_for_html(context_map_html, out_html).replace("\\", "/")
    defo_rel    = _relpath_for_html(defo_png, out_html).replace("\\", "/")
    logo_rel    = _relpath_for_html(logo_path, out_html).replace("\\", "/") if (logo_path and Path(logo_path).exists()) else None

    # Valores de resumen
    total_loss = 0.0
    if df_yearly is not None and len(df_yearly):
        total_loss = float(df_yearly["deforestation_ha"].sum())

    pred_txt = (pred_name or title_text).strip()
    obj_txt  = (str(objectid_val).strip() if objectid_val is not None else "—")
    lot_txt  = (str(lotcodigo_val).strip() if lotcodigo_val is not None else "—")
    area_txt = f"{fmt_ha(summary_area_ha)}" if (summary_area_ha is not None) else "—"

    # CSS (header + bold labels, normal values)
    css = """
    <style>
      :root {
        --card-bg: #fff;
        --muted: #666;
        --border: #e7e7e7;
      }
      * { box-sizing: border-box; }
      body { margin:0; font-family: Arial, sans-serif; background:#fafafa; color:#222; }

      /* Header sizing & color (as requested) */
      header { background:#E4002D; padding:.75rem 1rem; }
      header.banner { background:#E4002D; width:100%; margin:0 auto; padding:1.5rem 0; }

      .brand { max-width:1150px; margin:0 auto; display:flex; align-items:center; gap:16px; padding:0 16px; }
      .brand .title { color:#fff; font-size:18px; font-weight:700; line-height:1.1; }
      .brand .sub { color:#fff; font-size:12px; opacity:.92; margin-top:2px; }

      .container { padding:18px; max-width:1150px; margin:0 auto; }
      h1 { margin:12px 0 4px; font-size:26px; }
      .range { color:#777; margin-bottom:14px; }

      .grid-2 { display:grid; grid-template-columns: 1.4fr 1fr; gap:16px; }
      .card { background:var(--card-bg); border:1px solid var(--border); border-radius:12px; padding:12px; }
      .card h2 { margin:6px 0 8px; font-size:16px; }

      iframe { width:100%; height:420px; border:none; border-radius:10px; }
      .note { color:var(--muted); font-size:12px; margin-top:8px; }

      /* Resumen key–value (labels bold, values normal) */
      .kv { margin-top:4px; }
      .kv .row {
        display:flex; justify-content:space-between; gap:12px;
        padding:6px 2px; border-bottom:1px solid #eee;
      }
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
          <h2> Hectáreas perdidas por año</h2>
          <table>
            <thead><tr><th>Año</th><th>Pérdida (ha)</th></tr></thead>
            <tbody>{rows_html}</tbody>
          </table>
          <p class="note">Área de píxel ~30 m × 30 m (Hansen GFC).</p>
        </div>
        """
    else:
        table_card = """
        <div class="card">
          <h2> Hectáreas perdidas por año</h2>
          <p class="note"> No se detectó deforestación en el rango de años especificado.</p>
        </div>
        """

    # HTML
    html = f"""<!doctype html><html><head><meta charset="utf-8"><title>{title_text}</title>{css}</head>
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
            el cual participa en el esquema de PSAH en Bogotá y 19 municipios aledaños. Incluye un mapa de contexto geográfico interactivo,
            un mapa de deforestación y una tabla de hectáreas de pérdida por año.
          </p>
        </div>

        <div class="grid-2">
          <div class="card">
            <h2> Mapa de contextualización geográfica del predio </h2>
            <iframe src="{context_rel}"></iframe>
            <p class="note">Fuente del mapa base: Esri World Imagery. </p>
          </div>
          <div class="card">
            <h2> Resumen</h2>
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
            <h2> Mapa de deforestación</h2>
            <img class="map-img" src="{defo_rel}" alt="Mapa de deforestación">
          </div>
          {table_card}
        </div>
      </div>
    </body></html>"""

    with open(out_html, "w", encoding="utf-8") as f:
        f.write(html)
    return out_html
