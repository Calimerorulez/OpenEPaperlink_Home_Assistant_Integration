"""Shared fixtures for drawcustom tests."""
import os
import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from PIL import ImageFont

from PIL import ImageChops
sys.modules['serial'] = MagicMock()
sys.modules['serial.tools'] = MagicMock()
sys.modules['serial.tools.list_ports'] = MagicMock()
sys.modules['homeassistant.components.bluetooth'] = MagicMock()
from homeassistant.core import HomeAssistant
from custom_components.open_epaper_link.imagegen import ImageGen
from custom_components.open_epaper_link.const import DOMAIN

current_dir = os.path.dirname(os.path.abspath(__file__))
BASE_IMG_PATH = os.path.join(current_dir, "test_images")


@pytest.fixture
def mock_hass():
    """Create a mock Home Assistant instance."""
    hass = MagicMock(spec=HomeAssistant)

    # Mock async_add_executor_job
    hass.async_add_executor_job = AsyncMock()

    # Mock async_create_task to properly await coroutines
    async def mock_create_task(coro, name=None):
        await coro
        return None
    hass.async_create_task = mock_create_task

    # Mock config.path
    mock_config = MagicMock()
    def mock_path(*args):
        return os.path.join("/mock_path", *args)
    mock_config.path = mock_path
    hass.config = mock_config

    # Setup data attribute with required domain structure
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry_id"
    mock_entry.options = {"custom_font_dirs": ""}

    mock_hub = MagicMock()
    mock_hub.entry = mock_entry

    hass.data = {DOMAIN: {"test_entry_id": mock_hub}}

    return hass

@pytest.fixture
def mock_tag_info():
    """Create a mock tag type info."""
    tag_type = MagicMock()
    tag_type.width = 296
    tag_type.height = 128
    tag_type.color_table = {
        "white": [255, 255, 255],
        "black": [0, 0, 0],
        "red": [255, 0, 0],
        "accent": [255, 0, 0]
    }
    return tag_type, "red"

@pytest.fixture
def image_gen(mock_hass):
    """Create an ImageGen instance with mocked Home Assistant."""
    # Find the real font paths in the integration directory
    integration_dir = os.path.dirname(os.path.dirname(current_dir))
    component_dir = os.path.join(integration_dir, "custom_components", "open_epaper_link")

    # Try different paths for finding the font directory
    possible_component_dirs = [
        component_dir,
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(current_dir))),
                     "custom_components", "open_epaper_link"),
        # Add more possible locations if needed
    ]

    # Find the first valid component directory
    for dir_path in possible_component_dirs:
        if os.path.exists(dir_path):
            component_dir = dir_path
            break

    assets_dir = os.path.join(component_dir, "imagegen", "assets")

    # Define font paths
    font_paths = {
        "ppb.ttf": os.path.join(assets_dir, "ppb.ttf"),
        "rbm.ttf": os.path.join(assets_dir, "rbm.ttf")
    }

    # Check if fonts exist
    fonts_exist = all(os.path.exists(path) for path in font_paths.values())
    if not fonts_exist:
        print(f"WARNING: Some font files not found in {assets_dir}")
        if os.path.exists(assets_dir):
            print(f"Available files in directory: {os.listdir(assets_dir)}")
        else:
            print("Assets directory not found")

    # Create a patch for FontManager to avoid filesystem operations
    with patch('custom_components.open_epaper_link.imagegen.core.FontManager', autospec=True) as MockFontManager:
        # Configure the mock FontManager
        font_manager_instance = MockFontManager.return_value

        # Define the get_font method
        def mock_get_font(font_name, size):
            if font_name in font_paths and os.path.exists(font_paths[font_name]):
                # Use the actual font if available
                return ImageFont.truetype(font_paths[font_name], size)
            elif font_name == "rbm.ttf" and os.path.exists(font_paths["ppb.ttf"]):
                # Fallback to ppb.ttf for rbm.ttf if needed
                print(f"WARNING: Using ppb.ttf as a fallback for {font_name}")
                return ImageFont.truetype(font_paths["ppb.ttf"], size)
            else:
                # Last resort: create a mock font
                mock_font = MagicMock()
                mock_font.getbbox.return_value = (0, 0, 10 * len("Mocked Text"), 10)
                mock_font.getlength.return_value = 10 * len("Mocked Text")
                print(f"WARNING: Creating mock font for {font_name}")
                return mock_font

        font_manager_instance.get_font.side_effect = mock_get_font

        # Create the ImageGen instance with our mock setup
        instance = ImageGen(mock_hass)

        # Mock the get_tag_info method
        async def mock_get_tag_info(entity_id):
            tag_type = MagicMock()
            tag_type.width = 296
            tag_type.height = 128
            tag_type.color_table = {
                "white": [255, 255, 255],
                "black": [0, 0, 0],
                "red": [255, 0, 0],
                "accent": [255, 0, 0]
            }
            return tag_type, "red"

        instance.get_tag_info = mock_get_tag_info

        return instance

# Helper functions that might be needed across multiple test files
def get_test_image_path(filename):
    """Get the full path to a test image file."""
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), "test_images", filename)

def mock_service_data(payload):
    """Create a standard service data structure with given payload."""
    return {
        "background": "white",
        "rotate": 0,
        "dither": 2,
        "payload": payload
    }

def images_equal(img1, img2):
    """Compare two images and return True if they are identical."""
    return ImageChops.difference(img1, img2).getbbox() is None

def save_image(image_bytes):
    """Save image for debugging."""
    img_path = os.path.join(BASE_IMG_PATH, 'rename_me.png')
    with open(img_path, 'wb') as f:
        f.write(image_bytes)

async def generate_test_image(image_gen: ImageGen, service_data, entity_id="open_epaper_link.test_tag"):
    """Helper to generate test images with standard dimensions."""
    return  await image_gen.generate_custom_image(
        entity_id=entity_id,
        service_data=service_data,
        width=296,
        height=128,
        accent_color="red"
    )


# Setup and cleanup code that runs before and after each test session
def pytest_sessionstart(session):
    """
    Called after the Session object has been created and
    before performing collection and entering the run test loop.
    """
    # Create test_images directory if it doesn't exist
    test_images_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "test_images")
    os.makedirs(test_images_dir, exist_ok=True)

def pytest_sessionfinish(session, exitstatus):
    """
    Called after whole test run finished, right before
    returning the exit status to the system.
    """
    pass  # Add any cleanup code if needed


def text_images_equal(img1, img2):
    """Compare text masks allowing one pixel of FreeType rasterization variation.

    Reference images were created in 2024. Compare each thresholded RGB color
    separately, preserving ink counts and layout without relying on JPEG noise
    or an identical FreeType build. Shape tests keep exact images_equal checks.
    """
    import numpy as np
    from PIL import Image, ImageFilter

    if img1.size != img2.size:
        return False
    labels = []
    for img in (img1, img2):
        channels = np.asarray(img.convert("RGB")) < 128
        labels.append(
            channels[:, :, 0].astype(np.uint8) * 4
            + channels[:, :, 1].astype(np.uint8) * 2
            + channels[:, :, 2].astype(np.uint8)
        )
    for color in range(1, 8):
        actual = labels[0] == color
        expected = labels[1] == color
        expected_count = int(expected.sum())
        if abs(int(actual.sum()) - expected_count) > max(1, expected_count * 0.01):
            return False
        expanded_actual = np.asarray(
            Image.fromarray(actual.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(3))
        ) > 0
        expanded_expected = np.asarray(
            Image.fromarray(expected.astype(np.uint8) * 255).filter(ImageFilter.MaxFilter(3))
        ) > 0
        if np.any(actual & ~expanded_expected) or np.any(expected & ~expanded_actual):
            return False
    return True
