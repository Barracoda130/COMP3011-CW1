import pytest

from app.services import recipe_import
from app.services.recipe_import import RecipeImportError, _split_intro_and_instructions, extract_recipe_from_url


def test_split_intro_and_instructions_with_line_marker() -> None:
    text = "Great family dinner.\n\nInstructions\n1. Prep\n2. Cook"
    intro, steps = _split_intro_and_instructions(text)

    assert intro == "Great family dinner."
    assert steps == "1. Prep\n2. Cook"


def test_split_intro_and_instructions_with_inline_marker() -> None:
    text = "Comfort food. Directions: Mix ingredients. Bake 25 minutes."
    intro, steps = _split_intro_and_instructions(text)

    assert intro == "Comfort food."
    assert steps == "Mix ingredients. Bake 25 minutes."


def test_split_intro_and_instructions_without_marker_treats_all_as_steps() -> None:
    text = "Heat oil and saute onions. Add tomatoes and simmer."
    intro, steps = _split_intro_and_instructions(text)

    assert intro is None
    assert steps == text


def test_split_intro_and_instructions_marker_without_content_falls_back_to_steps() -> None:
    text = "Quick note. Instructions:"
    intro, steps = _split_intro_and_instructions(text)

    assert intro is None
    assert steps == text


def test_extract_recipe_from_url_rejects_unsupported_scheme() -> None:
    with pytest.raises(RecipeImportError, match="Only http/https URLs are supported"):
        recipe_import._validate_public_url("ftp://example.com/recipe")


def test_extract_recipe_from_url_raises_when_html_has_no_recipe_data(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        recipe_import,
        "_fetch_html",
        lambda _url: "<html><body><p>No title or recipe metadata.</p></body></html>",
    )

    with pytest.raises(RecipeImportError, match="Could not parse recipe data from this URL"):
        extract_recipe_from_url("https://example.com/no-recipe")
