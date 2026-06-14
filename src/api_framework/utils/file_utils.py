# Utilities for reading test data files and encoding images.


from __future__ import annotations

import base64
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Canonical path to test image fixtures
_TEST_DATA_DIR = Path(__file__).parents[3] / "test_data" / "images"


def load_image_as_base64(image_path: Path | str) -> str:
    """
    Read an image file from disk and return its base64-encoded string.

    The IDcheck API expects raw base64 (no data URI prefix like
    'data:image/jpeg;base64,...'). We strip any such prefix if present.

    Args:
        image_path: Absolute or relative path to the image file.

    Returns:
        Pure base64-encoded string ready to embed in the API payload.

    Raises:
        FileNotFoundError: If the image file does not exist.
    """
    path = Path(image_path)
    if not path.is_absolute():
        path = _TEST_DATA_DIR / path

    if not path.exists():
        raise FileNotFoundError(
            f"Test image not found: {path}\n"
            f"Expected directory: {_TEST_DATA_DIR}"
        )

    raw_bytes = path.read_bytes()
    encoded = base64.b64encode(raw_bytes).decode("utf-8")
    logger.debug("Loaded image: %s (%d bytes → %d base64 chars)", path.name, len(raw_bytes), len(encoded))
    return encoded


def get_specimen_front() -> str:
    """Return base64 of the specimen ID card front (RECTO)."""
    return load_image_as_base64("specimen_recto.jpg")


def get_specimen_back() -> str:
    """Return base64 of the specimen ID card back (VERSO)."""
    return load_image_as_base64("specimen_verso.jpg")
