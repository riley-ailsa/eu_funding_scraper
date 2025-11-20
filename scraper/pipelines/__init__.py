"""
Pipeline modules for different funding bodies.

Each module implements a bespoke scraper for a specific funding source,
all outputting to the same normalized format.
"""

from . import horizon_europe
from . import digital_europe

__all__ = ['horizon_europe', 'digital_europe']
