import ipaddress
import json
import re
import socket
from typing import Any
from urllib.parse import urlparse

import httpx

BLOCKED_HOSTNAMES = {"localhost", "127.0.0.1", "::1"}
MAX_HTML_SIZE_BYTES = 2_000_000
REQUEST_TIMEOUT_SECONDS = 10.0
INSTRUCTION_MARKER_PATTERN = re.compile(
    r"(?i)\b(instructions?|method|directions?|preparation|how to make|steps?)\b\s*[:\-]?\s*"
)
INSTRUCTION_LINE_PATTERN = re.compile(
    r"(?im)^\s*(instructions?|method|directions?|preparation|how to make|steps?)\s*[:\-]?\s*$"
)


class RecipeImportError(ValueError):
    pass


def _split_intro_and_instructions(text: str | None) -> tuple[str | None, str | None]:
    normalized = (text or "").strip()
    if not normalized:
        return None, None

    line_match = INSTRUCTION_LINE_PATTERN.search(normalized)
    if line_match:
        intro = normalized[: line_match.start()].strip() or None
        instructions = normalized[line_match.end() :].strip() or None
        if instructions:
            return intro, instructions

    inline_match = INSTRUCTION_MARKER_PATTERN.search(normalized)
    if inline_match:
        intro = normalized[: inline_match.start()].strip() or None
        instructions = normalized[inline_match.end() :].strip() or None
        if instructions:
            return intro, instructions

    # No marker found: treat all text as instructions.
    return None, normalized


def _extract_json_ld_blocks(html: str) -> list[str]:
    pattern = re.compile(
        r"<script[^>]*type=['\"]application/ld\+json['\"][^>]*>(.*?)</script>",
        re.IGNORECASE | re.DOTALL,
    )
    return [match.strip() for match in pattern.findall(html) if match.strip()]


def _as_type_list(raw_type: Any) -> list[str]:
    if isinstance(raw_type, list):
        return [str(value) for value in raw_type]
    if raw_type is None:
        return []
    return [str(raw_type)]


def _find_recipe_objects(node: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(node, dict):
        node_types = {item.lower() for item in _as_type_list(node.get("@type"))}
        if "recipe" in node_types:
            found.append(node)

        graph = node.get("@graph")
        if isinstance(graph, list):
            for item in graph:
                found.extend(_find_recipe_objects(item))

        for value in node.values():
            if isinstance(value, (dict, list)):
                found.extend(_find_recipe_objects(value))

    if isinstance(node, list):
        for item in node:
            found.extend(_find_recipe_objects(item))

    return found


def _normalize_image(image_data: Any) -> str | None:
    if isinstance(image_data, str):
        return image_data.strip() or None
    if isinstance(image_data, list):
        for item in image_data:
            normalized = _normalize_image(item)
            if normalized:
                return normalized
    if isinstance(image_data, dict):
        candidate = image_data.get("url") or image_data.get("contentUrl")
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()
    return None


def _normalize_tags(raw_keywords: Any, raw_category: Any = None) -> list[str]:
    values: list[str] = []

    if isinstance(raw_keywords, str):
        values.extend([item.strip() for item in raw_keywords.split(",")])
    elif isinstance(raw_keywords, list):
        for item in raw_keywords:
            if isinstance(item, str):
                values.extend([part.strip() for part in item.split(",")])

    if isinstance(raw_category, str):
        values.append(raw_category.strip())
    elif isinstance(raw_category, list):
        for item in raw_category:
            if isinstance(item, str):
                values.append(item.strip())

    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        if not value:
            continue
        lowered = value.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        deduped.append(value)

    return deduped[:20]


def _parse_iso_duration_to_minutes(raw: Any) -> int | None:
    if not isinstance(raw, str):
        return None

    duration = raw.strip().upper()
    match = re.fullmatch(r"P(?:\d+D)?T(?:(\d+)H)?(?:(\d+)M)?", duration)
    if not match:
        return None

    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    total = hours * 60 + minutes
    return total if total > 0 else None


def _extract_instruction_text(raw_instructions: Any) -> str | None:
    lines: list[str] = []

    def walk(node: Any) -> None:
        if isinstance(node, str):
            value = node.strip()
            if value:
                lines.append(value)
            return

        if isinstance(node, dict):
            text = node.get("text")
            if isinstance(text, str) and text.strip():
                lines.append(text.strip())
            nested = node.get("itemListElement")
            if isinstance(nested, (list, dict, str)):
                walk(nested)
            return

        if isinstance(node, list):
            for item in node:
                walk(item)

    walk(raw_instructions)

    if not lines:
        return None
    return "\n".join(lines)


def _strip_tags(html_fragment: str) -> str:
    no_script = re.sub(r"<script[^>]*>.*?</script>", " ", html_fragment, flags=re.IGNORECASE | re.DOTALL)
    no_style = re.sub(r"<style[^>]*>.*?</style>", " ", no_script, flags=re.IGNORECASE | re.DOTALL)
    no_tags = re.sub(r"<[^>]+>", " ", no_style)
    compacted = re.sub(r"\s+", " ", no_tags)
    return compacted.strip()


def _extract_meta_tag(html: str, attribute_name: str, attribute_value: str) -> str | None:
    pattern = re.compile(
        rf"<meta[^>]*{attribute_name}=['\"]{re.escape(attribute_value)}['\"][^>]*content=['\"](.*?)['\"][^>]*>",
        re.IGNORECASE,
    )
    match = pattern.search(html)
    if match:
        return match.group(1).strip() or None
    return None


def _extract_title_from_html(html: str) -> str | None:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    cleaned = _strip_tags(match.group(1))
    if not cleaned:
        return None
    return cleaned.split("|")[0].split("-")[0].strip() or cleaned


def _is_blocked_ip(ip_text: str) -> bool:
    ip = ipaddress.ip_address(ip_text)
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _validate_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise RecipeImportError("Only http/https URLs are supported")

    host = (parsed.hostname or "").strip().lower()
    if not host:
        raise RecipeImportError("Invalid URL")
    if host in BLOCKED_HOSTNAMES:
        raise RecipeImportError("This URL is not allowed")

    try:
        addr_info = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise RecipeImportError("Could not resolve URL hostname") from exc

    for item in addr_info:
        ip_text = str(item[4][0])
        if _is_blocked_ip(ip_text):
            raise RecipeImportError("This URL is not allowed")


def _fetch_html(url: str) -> str:
    _validate_public_url(url)

    headers = {
        "User-Agent": "MealPlannerRecipeImporter/1.0",
        "Accept": "text/html,application/xhtml+xml",
    }

    try:
        with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS, follow_redirects=True, max_redirects=5) as client:
            response = client.get(url, headers=headers)
            response.raise_for_status()
    except httpx.HTTPError as exc:
        raise RecipeImportError("Unable to fetch the provided URL") from exc

    content_type = (response.headers.get("content-type") or "").lower()
    if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
        raise RecipeImportError("URL does not appear to be an HTML recipe page")

    content = response.content
    if len(content) > MAX_HTML_SIZE_BYTES:
        raise RecipeImportError("Recipe page is too large to import")

    return response.text


def _build_preview_from_json_ld(recipe: dict[str, Any], source_url: str) -> dict[str, Any] | None:
    title = (recipe.get("name") or "").strip()
    if not title:
        return None

    cuisine = recipe.get("recipeCuisine")
    if isinstance(cuisine, list):
        cuisine = next((item.strip() for item in cuisine if isinstance(item, str) and item.strip()), None)

    description = (recipe.get("description") or "").strip() or None
    instructions_text = _extract_instruction_text(recipe.get("recipeInstructions"))
    ingredient_lines = [line.strip() for line in recipe.get("recipeIngredient") or [] if isinstance(line, str) and line.strip()]
    intro = description
    steps = None

    if instructions_text:
        embedded_intro, parsed_instructions = _split_intro_and_instructions(instructions_text)
        if embedded_intro and not intro:
            intro = embedded_intro
        steps = parsed_instructions
    elif description:
        intro_from_description, parsed_from_description = _split_intro_and_instructions(description)
        intro = intro_from_description
        steps = parsed_from_description

    return {
        "title": title,
        "cuisine": cuisine.strip() if isinstance(cuisine, str) and cuisine.strip() else None,
        "prep_minutes": _parse_iso_duration_to_minutes(recipe.get("totalTime") or recipe.get("cookTime") or recipe.get("prepTime")),
        "calories": None,
        "intro": intro,
        "image_url": _normalize_image(recipe.get("image")),
        "ingredients": ingredient_lines[:40],
        "tags": _normalize_tags(recipe.get("keywords"), recipe.get("recipeCategory")),
        "steps": steps,
        "source_url": source_url,
    }


def _extract_recipe_from_json_ld(html: str, source_url: str) -> dict[str, Any] | None:
    for block in _extract_json_ld_blocks(html):
        try:
            payload = json.loads(block)
        except json.JSONDecodeError:
            continue

        recipe_objects = _find_recipe_objects(payload)
        for recipe in recipe_objects:
            preview = _build_preview_from_json_ld(recipe, source_url)
            if preview:
                return preview

    return None


def _extract_recipe_fallback(html: str, source_url: str) -> dict[str, Any] | None:
    title = (
        _extract_meta_tag(html, "property", "og:title")
        or _extract_meta_tag(html, "name", "twitter:title")
        or _extract_title_from_html(html)
    )
    if not title:
        return None

    description = (
        _extract_meta_tag(html, "property", "og:description")
        or _extract_meta_tag(html, "name", "description")
    )
    image_url = _extract_meta_tag(html, "property", "og:image")

    body_text = _strip_tags(html)
    if not description and len(body_text) > 120:
        description = body_text[:1200].strip()

    intro, steps = _split_intro_and_instructions(description)

    return {
        "title": title,
        "cuisine": None,
        "prep_minutes": None,
        "calories": None,
        "intro": intro,
        "image_url": image_url,
        "ingredients": [],
        "tags": [],
        "steps": steps,
        "source_url": source_url,
    }


def extract_recipe_from_url(url: str) -> dict[str, Any]:
    html = _fetch_html(url)

    from_json_ld = _extract_recipe_from_json_ld(html, source_url=url)
    if from_json_ld:
        return from_json_ld

    from_fallback = _extract_recipe_fallback(html, source_url=url)
    if from_fallback:
        return from_fallback

    raise RecipeImportError("Could not parse recipe data from this URL")
