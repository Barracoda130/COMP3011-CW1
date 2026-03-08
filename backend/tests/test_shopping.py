from app.services.shopping import _should_skip_small_quantity


def test_should_skip_small_quantity_keywords() -> None:
    assert _should_skip_small_quantity("pinch of salt") is True
    assert _should_skip_small_quantity("to taste") is True


def test_should_skip_small_quantity_small_spoon_measure() -> None:
    assert _should_skip_small_quantity("2 tsp") is True
    assert _should_skip_small_quantity("2.5 tbsp") is True
    assert _should_skip_small_quantity("99 ml") is True
    assert _should_skip_small_quantity("80 g") is True
    assert _should_skip_small_quantity("3 oz") is True


def test_should_not_skip_at_or_above_thresholds() -> None:
    assert _should_skip_small_quantity("3 tsp") is False
    assert _should_skip_small_quantity("3 tbsp") is False
    assert _should_skip_small_quantity("100 ml") is False
    assert _should_skip_small_quantity("100 g") is False
    assert _should_skip_small_quantity("3.5 oz") is False


def test_should_not_skip_normal_cooking_amounts() -> None:
    assert _should_skip_small_quantity("2 cups") is False
    assert _should_skip_small_quantity("250 g") is False
