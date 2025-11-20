"""
Grant scraper framework.

Provides base classes and utilities for scraping multiple funding bodies
with shared infrastructure for logging, checkpointing, and validation.
"""

from .base import FundingBodyPipeline, NormalizedGrant

__all__ = ['FundingBodyPipeline', 'NormalizedGrant']
