from __future__ import annotations
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

PROMPT_ROOT = Path(__file__).parent / "prompts"

_env = Environment(loader=FileSystemLoader(PROMPT_ROOT))

def render_prompt(tpl_name: str, **kwargs) -> str:
    tpl = _env.get_template(tpl_name)
    return tpl.render(**kwargs)
