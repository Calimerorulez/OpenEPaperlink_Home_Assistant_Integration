"""Ensure text snapshot tolerance still rejects material regressions."""
import pytest
from PIL import Image, ImageDraw

from conftest import images_equal, text_images_equal


def text_mask(offset=0, color="black", omit=False):
    image = Image.new("RGB", (80, 30), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((10 + offset, 5, 12 + offset, 20), fill=color)
    if not omit:
        draw.rectangle((20 + offset, 5, 22 + offset, 20), fill=color)
    return image


@pytest.mark.parametrize("offset,accepted", [(0, True), (1, True), (3, False)])
def test_text_comparison_limits_raster_shift(offset, accepted):
    assert text_images_equal(text_mask(offset), text_mask()) is accepted


@pytest.mark.parametrize("actual", [text_mask(omit=True), text_mask(color="red"), Image.new("RGB", (80, 30), "white")])
def test_text_comparison_rejects_missing_or_recolored_content(actual):
    assert not text_images_equal(actual, text_mask())


def test_text_comparison_rejects_wrong_canvas():
    assert not text_images_equal(Image.new("RGB", (81, 30), "white"), text_mask())


def test_shape_comparison_remains_exact():
    assert not images_equal(text_mask(1), text_mask())
