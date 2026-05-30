"""Provider adapters convert platform data into the normalized schema.

Ship today: :class:`~smbd.providers.importer.ImportProvider` (CSV/JSON/paste).
Coming next: Instagram Graph, YouTube Data API, X API, and an optional scraper
extra — all behind :class:`~smbd.providers.base.Provider`.
"""

from smbd.providers.base import Provider
from smbd.providers.importer import ImportProvider

__all__ = ["Provider", "ImportProvider"]
