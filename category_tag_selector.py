import json
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml
from aiohttp import web

try:
    from server import PromptServer
except Exception:
    PromptServer = None

NODE_DIR = Path(__file__).resolve().parent
TAGS_DIR = NODE_DIR / "tags"
TAGS_DIR.mkdir(exist_ok=True)


def _safe_yaml_name(name: str) -> str:
    name = os.path.basename(str(name or ""))
    if not name.lower().endswith((".yaml", ".yml")):
        raise ValueError("Only .yaml / .yml files are supported.")
    path = (TAGS_DIR / name).resolve()
    if TAGS_DIR.resolve() not in path.parents and path != TAGS_DIR.resolve():
        raise ValueError("Invalid yaml path.")
    if not path.exists():
        raise FileNotFoundError(f"YAML not found: {name}")
    return name


def _list_yaml_files() -> List[str]:
    files = sorted(p.name for p in TAGS_DIR.iterdir() if p.is_file() and p.suffix.lower() in (".yaml", ".yml"))
    return files or ["sample_hair.yml"]


def _load_yaml(name: str) -> Dict[str, Any]:
    name = _safe_yaml_name(name)
    with (TAGS_DIR / name).open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError("YAML root must be a mapping/dictionary.")
    return data


def _normalize_categories(data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Supported formats:

    Recommended flat categories:
      髪型:
        ショートヘア: short hair
      髪色:
        赤色: red hair

    Single-root nested categories:
      髪のタイプ:
        髪型:
          ショートヘア:
            - short hair
        髪色:
          赤色:
            - red hair
    """
    if len(data) == 1:
        only_value = next(iter(data.values()))
        if isinstance(only_value, dict) and all(isinstance(v, dict) for v in only_value.values()):
            return only_value

    categories: Dict[str, Dict[str, Any]] = {}
    for category, options in data.items():
        if isinstance(options, dict):
            categories[str(category)] = options
    return categories


def _value_to_tags(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, (int, float)):
        return [str(value)]
    if isinstance(value, (list, tuple)):
        tags: List[str] = []
        for item in value:
            tags.extend(_value_to_tags(item))
        return tags
    if isinstance(value, dict):
        for key in ("prompt", "prompts", "tag", "tags", "text", "value"):
            if key in value:
                return _value_to_tags(value[key])
        return []
    return [str(value)]


def _schema_for_yaml(name: str) -> Dict[str, Any]:
    data = _load_yaml(name)
    categories = _normalize_categories(data)
    schema_categories = []
    for category, options in categories.items():
        if not isinstance(options, dict):
            continue
        labels = [str(label) for label in options.keys()]
        schema_categories.append({"name": str(category), "options": ["なし"] + labels})
    return {"yaml_file": name, "categories": schema_categories}


def _join_tags(tags: List[str], separator: str, trailing_comma: bool) -> str:
    clean = [str(tag).strip() for tag in tags if str(tag).strip()]
    if not clean:
        return ""
    sep = separator if separator is not None else ", "
    text = sep.join(clean)
    if trailing_comma:
        comma_like = sep.rstrip()
        text += comma_like[-1] if comma_like.endswith(",") else ","
    return text


class CategoryTagSelector:
    """
    YAML category tag selector.

    Frontend JS reads the selected YAML and adds one dropdown per YAML category title.
    Selected Japanese labels are stored into selections_json.
    Backend maps those labels to prompt tags and outputs a single STRING.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "yaml_file": (_list_yaml_files(),),
                "separator": ("STRING", {"default": ", ", "multiline": False}),
                "trailing_comma": ("BOOLEAN", {"default": True}),
                "selections_json": ("STRING", {"default": "{}", "multiline": True}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("text",)
    FUNCTION = "build_prompt"
    CATEGORY = "prompt/yaml"

    def build_prompt(self, yaml_file: str, separator: str = ", ", trailing_comma: bool = True, selections_json: str = "{}") -> Tuple[str]:
        try:
            data = _load_yaml(yaml_file)
            categories = _normalize_categories(data)
            selections = json.loads(selections_json or "{}")
            if not isinstance(selections, dict):
                selections = {}
        except Exception as exc:
            return (f"[CategoryTagSelector error: {exc}]",)

        tags: List[str] = []
        for category, selected_label in selections.items():
            if not selected_label or selected_label == "なし":
                continue
            options = categories.get(category)
            if not isinstance(options, dict):
                continue
            tags.extend(_value_to_tags(options.get(selected_label)))
        return (_join_tags(tags, separator, trailing_comma),)


def _register_routes():
    if PromptServer is None:
        return
    routes = PromptServer.instance.routes

    @routes.get("/category_tag_selector/yamls")
    async def get_yaml_files(request):
        return web.json_response({"files": _list_yaml_files()})

    @routes.get("/category_tag_selector/schema")
    async def get_yaml_schema(request):
        try:
            yaml_file = request.query.get("file", "") or _list_yaml_files()[0]
            return web.json_response(_schema_for_yaml(yaml_file))
        except Exception as exc:
            return web.json_response({"error": str(exc), "categories": []}, status=400)


_register_routes()

NODE_CLASS_MAPPINGS = {"CategoryTagSelector": CategoryTagSelector}
NODE_DISPLAY_NAME_MAPPINGS = {"CategoryTagSelector": "Category Tag Selector(nobin)"}
WEB_DIRECTORY = "./web/js"
