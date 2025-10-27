import json
import re
from pathlib import Path

SECTION_PAT = re.compile(r"{{#(\w+)}}(.*?){{/\1}}", re.DOTALL)
TOKEN_PAT = re.compile(r"{{\s*([\w\.]+)\s*}}")

def render(template_path: Path, data_path: Path, out_path: Path):
    template = template_path.read_text(encoding="utf-8")
    data = json.loads(data_path.read_text(encoding="utf-8"))
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
