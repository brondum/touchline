"""Constant values for Roth Touchline floor heating controller."""

from __future__ import annotations

from datetime import timedelta
import logging

DOMAIN = "touchline"
MANUFACTURER = "Roth"

DEFAULT_SCAN_INTERVAL = timedelta(seconds=60)
DEFAULT_MIN_TEMP = 5.0
DEFAULT_MAX_TEMP = 30.0
DEFAULT_TEMP_STEP = 0.5

_LOGGER = logging.getLogger(__package__)
