"""OriginShot generative pipelines (Genblaze orchestration).

Builders are import-safe without Genblaze installed — provider classes are imported lazily
inside each builder so this package (and its registry) can be imported and unit-tested
independently of the web layer or the SDK.
"""
from . import registry  # noqa: F401

__all__ = ["registry"]
