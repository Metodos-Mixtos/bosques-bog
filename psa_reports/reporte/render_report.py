#!/usr/bin/env python3
"""
Render HTML report from template and data dictionary.
Similar to the render_report.py used in dynamic_world, gfw_alerts, and urban_sprawl.
"""
import json
import re
from pathlib import Path

SECTION_PAT = re.compile(r"{{#(\w+)}}(.*?){{/\1}}", re.DOTALL)
TOKEN_PAT = re.compile(r"{{\s*([\w\.]+)\s*}}")


def render_template(tpl: str, root: dict) -> str:
    """
    Render a template string with data from root dictionary.
    Supports:
    - Simple tokens: {{KEY}}
    - Section loops: {{#KEY}}...{{/KEY}}
    """
    def _render_block(block: str, ctx: dict) -> str:
        def _section(m):
            key, inner = m.group(1), m.group(2)
            arr = ctx.get(key, [])
            if not isinstance(arr, list):
                return ""
            out = []
            for item in arr:
                local = {**ctx, **(item if isinstance(item, dict) else {".": item})}
                out.append(_render_block(inner, local))
            return "".join(out)

        out = SECTION_PAT.sub(_section, block)

        def _token(m):
            k = m.group(1)
            return str(ctx.get(k, root.get(k, "")))
        return TOKEN_PAT.sub(_token, out)

    return _render_block(tpl, root)


def render(template_path: Path, data: dict, out_path: Path):
    """
    Render template file with data dictionary and write to out_path.
    
    Args:
        template_path: Path to HTML template file
        data: Dictionary with template variables
        out_path: Path where rendered HTML will be saved
    
    Returns:
        Path to rendered output file
    """
    template = template_path.read_text(encoding="utf-8")
    html = render_template(template, data)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html, encoding="utf-8")
    return out_path


def render_from_json(template_path: Path, data_path: Path, out_path: Path):
    """
    Render template file with data from JSON file and write to out_path.
    
    Args:
        template_path: Path to HTML template file
        data_path: Path to JSON data file
        out_path: Path where rendered HTML will be saved
    
    Returns:
        Path to rendered output file
    """
    data = json.loads(data_path.read_text(encoding="utf-8"))
    return render(template_path, data, out_path)
