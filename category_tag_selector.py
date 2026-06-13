import json
import random
import re
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
    name = str(name or "").replace("\\", "/").lstrip("/")
    if not name.lower().endswith((".yaml", ".yml")):
        raise ValueError("Only .yaml / .yml files are supported.")

    path = (TAGS_DIR / name).resolve()
    tags_root = TAGS_DIR.resolve()

    if tags_root not in path.parents and path != tags_root:
        raise ValueError("Invalid yaml path.")

    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"YAML not found: {name}")

    return name


def _list_yaml_files() -> List[str]:
    files = sorted(
        p.relative_to(TAGS_DIR).as_posix()
        for p in TAGS_DIR.rglob("*")
        if p.is_file() and p.suffix.lower() in (".yaml", ".yml")
    )
    return files or ["sample_hair.yml"]


def _load_yaml(name: str) -> Dict[str, Any]:
    name = _safe_yaml_name(name)
    with (TAGS_DIR / name).open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    if not isinstance(data, dict):
        raise ValueError("YAML root must be a mapping/dictionary.")

    return data


def _normalize_categories(data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
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


_CHOICE_PATTERN = re.compile(r"\{([^{}]*)\}")


def _resolve_choice_syntax(text: str) -> str:
    """
    Supported syntax:

      {a|b|c}
        -> choose one

      {a||}
        -> a / empty / empty
        -> a 33%, empty 66%

      {1$$3::a|b|c|d}
        -> choose 1 to 3 items

      {a}
        -> unchanged

    Nested braces are not supported.
    """

    def replace(match: re.Match) -> str:
        body = match.group(1)

        multi_match = re.match(r"^(\d+)\$\$(\d+)::(.*)$", body)

        if multi_match:
            min_count = int(multi_match.group(1))
            max_count = int(multi_match.group(2))
            raw_options = multi_match.group(3)

            if min_count > max_count:
                min_count, max_count = max_count, min_count

            options = [
                option.strip()
                for option in raw_options.split("|")
                if option.strip()
            ]

            if not options:
                return ""

            max_count = min(max_count, len(options))
            min_count = min(min_count, max_count)

            count = random.randint(min_count, max_count)

            if count <= 0:
                return ""

            selected = random.sample(options, count)
            return ", ".join(selected)

        if "|" not in body:
            return match.group(0)

        options = [part.strip() for part in body.split("|")]
        return random.choice(options)

    return _CHOICE_PATTERN.sub(replace, str(text))


def _schema_for_yaml(name: str) -> Dict[str, Any]:
    data = _load_yaml(name)
    categories = _normalize_categories(data)
    schema_categories = []

    for category, options in categories.items():
        if not isinstance(options, dict):
            continue

        labels = [str(label) for label in options.keys()]

        schema_categories.append({
            "name": str(category),
            "options": ["なし"] + labels,
        })

    return {
        "yaml_file": name,
        "categories": schema_categories,
    }


def _join_tags(tags: List[str], separator: str, trailing_comma: bool) -> str:
    clean = [
        _resolve_choice_syntax(str(tag).strip())
        for tag in tags
        if str(tag).strip()
    ]

    clean = [tag for tag in clean if tag]

    if not clean:
        return ""

    sep = separator if separator is not None else ", "
    text = sep.join(clean)

    if trailing_comma:
        comma_like = sep.rstrip()
        text += comma_like[-1] if comma_like.endswith(",") else ","

    return text


class CategoryTagSelector:
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

    @classmethod
    def IS_CHANGED(
        cls,
        yaml_file: str,
        separator: str = ", ",
        trailing_comma: bool = True,
        selections_json: str = "{}",
    ):
        return random.random()

    RETURN_TYPES = ("STRING", "STRING")
    RETURN_NAMES = ("prompt", "title_text")
    FUNCTION = "build_prompt"
    CATEGORY = "prompt/yaml"

    def build_prompt(
        self,
        yaml_file: str,
        separator: str = ", ",
        trailing_comma: bool = True,
        selections_json: str = "{}",
    ) -> Tuple[str, str]:
        try:
            data = _load_yaml(yaml_file)
            categories = _normalize_categories(data)
            selections = json.loads(selections_json or "{}")

            if not isinstance(selections, dict):
                selections = {}

        except Exception as exc:
            error_text = f"[CategoryTagSelector error: {exc}]"
            return (error_text, "")

        tags: List[str] = []
        selected_titles: List[str] = []

        for category, options in categories.items():
            if not isinstance(options, dict):
                continue

            selected_label = selections.get(category)

            if not selected_label or selected_label == "なし":
                continue

            selected_titles.append(str(selected_label))
            tags.extend(_value_to_tags(options.get(selected_label)))

        prompt = _join_tags(tags, separator, trailing_comma)
        title_text = _join_tags(selected_titles, separator, trailing_comma)

        return (prompt, title_text)


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
            return web.json_response(
                {"error": str(exc), "categories": []},
                status=400,
            )


_register_routes()

NODE_CLASS_MAPPINGS = {
    "CategoryTagSelector": CategoryTagSelector,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "CategoryTagSelector": "Category Tag Selector(nobin)",
}

WEB_DIRECTORY = "./web/js"