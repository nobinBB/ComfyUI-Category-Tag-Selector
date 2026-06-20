import json
import random
import re
import traceback
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

DEBUG_LOG = False
LOG_PREFIX = "[CategoryTagSelector(nobin)]"
PLUGIN_VERSION = "negative-marker-<!...!>-random-yaml-choice-v2"

NONE_LABEL = "なし"
RANDOM_LABEL = "ランダム"

OPTION_VALUE_KEYS = {
    "prompt",
    "prompts",
    "tag",
    "tags",
    "text",
    "value",
}

_CHOICE_PATTERN = re.compile(r"\{([^{}]*)\}")
_NEGATIVE_PATTERN = re.compile(r"<!\s*(.*?)\s*!>", re.DOTALL)


def _log(message: str) -> None:
    if DEBUG_LOG:
        print(f"{LOG_PREFIX} {message}", flush=True)


def _log_error(message: str) -> None:
    print(f"{LOG_PREFIX} ERROR {message}", flush=True)


_log(f"LOADED version={PLUGIN_VERSION}")
_log(f"NODE_DIR={NODE_DIR}")
_log(f"TAGS_DIR={TAGS_DIR}")


def _safe_yaml_name(name: str) -> str:
    try:
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

    except Exception as exc:
        _log_error(f"_safe_yaml_name failed: {exc!r}")
        _log_error(traceback.format_exc())
        raise


def _list_yaml_files() -> List[str]:
    try:
        files = sorted(
            p.relative_to(TAGS_DIR).as_posix()
            for p in TAGS_DIR.rglob("*")
            if p.is_file() and p.suffix.lower() in (".yaml", ".yml")
        )
        return files or ["sample_hair.yml"]

    except Exception as exc:
        _log_error(f"_list_yaml_files failed: {exc!r}")
        _log_error(traceback.format_exc())
        return ["sample_hair.yml"]


def _load_yaml(name: str) -> Dict[str, Any]:
    try:
        name = _safe_yaml_name(name)
        _log(f"LOAD_YAML file={name}")

        with (TAGS_DIR / name).open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        if not isinstance(data, dict):
            raise ValueError("YAML root must be a mapping/dictionary.")

        return data

    except Exception as exc:
        _log_error(f"_load_yaml failed: file={name!r} error={exc!r}")
        _log_error(traceback.format_exc())
        raise


def _resolve_choice_syntax(text: str) -> str:
    """
    Supported syntax:

      {a|b|c}
        -> choose one

      a{B|C|d}
        -> aB / aC / ad

      {a||}
        -> a / empty / empty

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

    try:
        return _CHOICE_PATTERN.sub(replace, str(text))

    except Exception as exc:
        _log_error(f"_resolve_choice_syntax failed: text={text!r} error={exc!r}")
        _log_error(traceback.format_exc())
        return str(text)


def _value_to_tags(value: Any) -> List[str]:
    if value is None:
        return []

    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        return [_resolve_choice_syntax(text)]

    if isinstance(value, (int, float, bool)):
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

    return [_resolve_choice_syntax(str(value))]


def _normalize_categories(data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    try:
        if len(data) == 1:
            only_value = next(iter(data.values()))

            if isinstance(only_value, dict):
                has_random_marker = RANDOM_LABEL in only_value

                has_option_value_dict = any(
                    isinstance(v, dict) and any(k in v for k in OPTION_VALUE_KEYS)
                    for v in only_value.values()
                )

                if (
                    not has_random_marker
                    and not has_option_value_dict
                    and all(isinstance(v, dict) for v in only_value.values())
                ):
                    return only_value

        categories: Dict[str, Dict[str, Any]] = {}

        for category, options in data.items():
            if isinstance(options, dict):
                categories[str(category)] = options

        return categories

    except Exception as exc:
        _log_error(f"_normalize_categories failed: {exc!r}")
        _log_error(traceback.format_exc())
        raise


def _to_bool_from_value(value: Any, default: bool = False) -> bool:
    values = _value_to_tags(value)

    if not values:
        return default

    text = str(values[0]).strip().lower()

    if text in ("true", "1", "yes", "on", "あり", "有り"):
        return True

    if text in ("false", "0", "no", "off", "なし", "無し"):
        return False

    return default


def _category_random_enabled(options: Dict[str, Any]) -> bool:
    if RANDOM_LABEL not in options:
        return False

    return _to_bool_from_value(options.get(RANDOM_LABEL), False)


def _option_labels(options: Dict[str, Any]) -> List[str]:
    return [
        str(label)
        for label in options.keys()
        if str(label) not in (NONE_LABEL, RANDOM_LABEL)
    ]


def _get_option_value(options: Dict[str, Any], selected_label: str) -> Any:
    if selected_label in options:
        return options[selected_label]

    for label, value in options.items():
        if str(label) == str(selected_label):
            return value

    return None


def _choose_random_label(options: Dict[str, Any]) -> str:
    labels = _option_labels(options)

    if not labels:
        return ""

    return random.choice(labels)


def _schema_for_yaml(name: str) -> Dict[str, Any]:
    try:
        data = _load_yaml(name)
        categories = _normalize_categories(data)
        schema_categories = []

        for category, options in categories.items():
            if not isinstance(options, dict):
                continue

            labels = _option_labels(options)

            schema_options = [NONE_LABEL]

            if _category_random_enabled(options):
                schema_options.append(RANDOM_LABEL)

            schema_options.extend(labels)

            schema_categories.append({
                "name": str(category),
                "options": schema_options,
            })

        _log(f"SCHEMA file={name!r} categories={len(schema_categories)}")

        return {
            "yaml_file": name,
            "categories": schema_categories,
        }

    except Exception as exc:
        _log_error(f"_schema_for_yaml failed: file={name!r} error={exc!r}")
        _log_error(traceback.format_exc())
        raise


def _normalize_prompt_text(text: str) -> str:
    text = str(text or "").strip()

    if not text:
        return ""

    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*,\s*", ", ", text)
    text = re.sub(r"(,\s*){2,}", ", ", text)
    text = text.strip()
    text = text.strip(",")
    text = text.strip()

    return text


def _add_trailing_comma(text: str, separator: str, trailing_comma: bool) -> str:
    text = _normalize_prompt_text(text)

    if not text:
        return ""

    if trailing_comma:
        sep = separator if separator is not None else ", "
        comma_like = sep.rstrip()
        text += comma_like[-1] if comma_like.endswith(",") else ","

    return text


def _split_negative_from_prompt_text(text: str, separator: str) -> Tuple[str, str]:
    try:
        raw_text = str(text or "")

        _log(f"SPLIT_RAW raw={raw_text!r}")

        open_count = raw_text.count("<!")
        close_count = raw_text.count("!>")

        if open_count != close_count:
            _log(
                "WARN marker count mismatch "
                f"open_count={open_count} close_count={close_count} raw={raw_text!r}"
            )

        negative_parts: List[str] = []

        for match in _NEGATIVE_PATTERN.finditer(raw_text):
            full = match.group(0)
            inner = _normalize_prompt_text(match.group(1))

            _log(f"NEGATIVE_MATCH full={full!r} inner={inner!r}")

            if inner:
                negative_parts.append(inner)

        positive = _NEGATIVE_PATTERN.sub("", raw_text)
        positive = _normalize_prompt_text(positive)

        sep = separator if separator is not None else ", "
        negative = _normalize_prompt_text(sep.join(negative_parts))

        if "<!" in raw_text and "!>" in raw_text and not negative_parts:
            _log(
                "WARN marker exists but no negative extracted. "
                "Correct format is <!bad anatomy!>."
            )

        if "<!" in positive or "!>" in positive:
            _log(f"WARN marker remained in positive={positive!r}")

        _log(f"SPLIT_RESULT positive={positive!r} negative={negative!r}")

        return positive, negative

    except Exception as exc:
        _log_error(f"_split_negative_from_prompt_text failed: text={text!r} error={exc!r}")
        _log_error(traceback.format_exc())
        return str(text or ""), ""


def _join_tags(tags: List[str], separator: str, trailing_comma: bool) -> str:
    try:
        clean: List[str] = []

        for tag in tags:
            tag_text = str(tag).strip()

            if not tag_text:
                continue

            resolved = _resolve_choice_syntax(tag_text)
            resolved = str(resolved).strip()

            if resolved:
                clean.append(resolved)

        if not clean:
            return ""

        sep = separator if separator is not None else ", "
        text = sep.join(clean)

        if trailing_comma:
            comma_like = sep.rstrip()
            text += comma_like[-1] if comma_like.endswith(",") else ","

        return text

    except Exception as exc:
        _log_error(f"_join_tags failed: tags={tags!r} error={exc!r}")
        _log_error(traceback.format_exc())
        return ""


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

    RETURN_TYPES = ("STRING", "STRING", "STRING", "STRING")
    RETURN_NAMES = ("positive", "negative", "positive_negative", "title_text")
    FUNCTION = "build_prompt"
    CATEGORY = "prompt/yaml"

    def build_prompt(
        self,
        yaml_file: str,
        separator: str = ", ",
        trailing_comma: bool = True,
        selections_json: str = "{}",
    ) -> Tuple[str, str, str, str]:
        _log("BUILD_START")
        _log(f"INPUT yaml_file={yaml_file!r}")
        _log(f"INPUT separator={separator!r}")
        _log(f"INPUT trailing_comma={trailing_comma!r}")
        _log(f"INPUT selections_json={selections_json!r}")

        try:
            data = _load_yaml(yaml_file)
            categories = _normalize_categories(data)
            selections = json.loads(selections_json or "{}")

            if not isinstance(selections, dict):
                _log("WARN selections_json is not dict. Reset to empty dict.")
                selections = {}

        except Exception as exc:
            error_text = f"[CategoryTagSelector error: {exc}]"
            _log_error(f"BUILD_SETUP failed: {exc!r}")
            _log_error(traceback.format_exc())
            return (error_text, "", "", "")

        try:
            tags: List[str] = []
            selected_titles: List[str] = []

            for category, options in categories.items():
                if not isinstance(options, dict):
                    _log(f"SKIP category={category!r} reason=options_not_dict")
                    continue

                selected_label = selections.get(category)

                _log(f"SELECT category={category!r} selected_label={selected_label!r}")

                if not selected_label or selected_label == NONE_LABEL:
                    continue

                title_label = str(selected_label)

                if selected_label == RANDOM_LABEL:
                    if not _category_random_enabled(options):
                        _log(f"SKIP category={category!r} reason=random_disabled")
                        continue

                    random_selected_label = _choose_random_label(options)

                    if not random_selected_label:
                        _log(f"SKIP category={category!r} reason=no_random_candidates")
                        continue

                    _log(
                        f"RANDOM_SELECTED category={category!r} "
                        f"selected_label={random_selected_label!r}"
                    )

                    selected_label = random_selected_label
                    title_label = RANDOM_LABEL

                selected_titles.append(title_label)

                selected_value = _get_option_value(options, selected_label)
                selected_tags = _value_to_tags(selected_value)

                _log(f"SELECTED_VALUE category={category!r} value={selected_value!r}")
                _log(f"SELECTED_TAGS category={category!r} tags={selected_tags!r}")

                tags.extend(selected_tags)

            raw_prompt = _join_tags(tags, separator, False)

            _log(f"RAW_PROMPT {raw_prompt!r}")

            positive_raw, negative_raw = _split_negative_from_prompt_text(raw_prompt, separator)

            positive = _add_trailing_comma(positive_raw, separator, trailing_comma)
            negative = _add_trailing_comma(negative_raw, separator, trailing_comma)
            positive_negative = _add_trailing_comma(raw_prompt, separator, trailing_comma)
            title_text = _join_tags(selected_titles, separator, trailing_comma)

            _log(f"OUTPUT positive={positive!r}")
            _log(f"OUTPUT negative={negative!r}")
            _log(f"OUTPUT positive_negative={positive_negative!r}")
            _log(f"OUTPUT title_text={title_text!r}")
            _log("BUILD_END")

            return (positive, negative, positive_negative, title_text)

        except Exception as exc:
            error_text = f"[CategoryTagSelector error: {exc}]"
            _log_error(f"BUILD_PROMPT failed: {exc!r}")
            _log_error(traceback.format_exc())
            return (error_text, "", "", "")


def _register_routes():
    if PromptServer is None:
        _log("WARN PromptServer is None. Routes not registered.")
        return

    try:
        routes = PromptServer.instance.routes

        @routes.get("/category_tag_selector/yamls")
        async def get_yaml_files(request):
            files = _list_yaml_files()
            _log(f"ROUTE /category_tag_selector/yamls files={files!r}")
            return web.json_response({"files": files})

        @routes.get("/category_tag_selector/schema")
        async def get_yaml_schema(request):
            try:
                yaml_file = request.query.get("file", "") or _list_yaml_files()[0]
                _log(f"ROUTE /category_tag_selector/schema file={yaml_file!r}")
                return web.json_response(_schema_for_yaml(yaml_file))
            except Exception as exc:
                _log_error(f"ROUTE /category_tag_selector/schema failed: {exc!r}")
                _log_error(traceback.format_exc())
                return web.json_response(
                    {"error": str(exc), "categories": []},
                    status=400,
                )

    except Exception as exc:
        _log_error(f"_register_routes failed: {exc!r}")
        _log_error(traceback.format_exc())
        raise


_register_routes()

NODE_CLASS_MAPPINGS = {
    "CategoryTagSelector": CategoryTagSelector,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "CategoryTagSelector": "Category Tag Selector(nobin)",
}

WEB_DIRECTORY = "./web/js"