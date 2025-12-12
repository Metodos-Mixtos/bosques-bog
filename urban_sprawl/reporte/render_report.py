import json
import re
import os
from pathlib import Path
from datetime import datetime

SECTION_PAT = re.compile(r"{{#(\w+)}}(.*?){{/\1}}", re.DOTALL)
TOKEN_PAT = re.compile(r"{{\s*([\w\.]+)\s*}}")

def render(template_path: Path, data_path: Path, out_path: Path):
    template = template_path.read_text(encoding="utf-8")
    data = json.loads(data_path.read_text(encoding="utf-8"))
    
    # Agrega fecha de generación
    data["FECHA_GENERACION"] = datetime.now().strftime("%d de %B de %Y")
    
    # Agrega rutas de imágenes del header y footer
    inputs_path = os.getenv("INPUTS_PATH", "")
    data["LOGO_ASI"] = os.path.join(inputs_path, "area_estudio", "asi_4.png")
    data["LOGO_BOGOTA"] = os.path.join(inputs_path, "area_estudio", "bogota_4.png")
    data["LOGO_FOOTER"] = os.path.join(inputs_path, "area_estudio", "secre_5.png")
    
    html = render_template(template, data)
    out_path.write_text(html, encoding="utf-8")
    return out_path

def render_template(tpl: str, root: dict) -> str:
    def _render_block(block: str, ctx: dict) -> str:
        def _section(m):
            key, inner = m.group(1), m.group(2)
            arr = ctx.get(key, [])
            if not isinstance(arr, list):
                return ""
            return "".join(_render_block(inner, {**ctx, **item}) for item in arr)

        out = SECTION_PAT.sub(_section, block)
        def _token(m):
            k = m.group(1)
            return str(ctx.get(k, root.get(k, "")))
        return TOKEN_PAT.sub(_token, out)
    return _render_block(tpl, root)
