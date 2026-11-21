"""Unicode NFKC normalization and production environment/tag detection utilities."""

from __future__ import annotations

import unicodedata
from collections.abc import Mapping

PRODUCTION_VALUES: frozenset[str] = frozenset({"production", "prod", "prd"})
ENVIRONMENT_TAG_KEYS: frozenset[str] = frozenset({"environment", "env", "stage"})


def normalize_str(value: str) -> str:
    """Normalize a string using Unicode NFKC, strip whitespace, and casefold."""
    return unicodedata.normalize("NFKC", value).strip().casefold()


def is_production_resource(environment: str, tags: Mapping[str, str] | None = None) -> bool:
    """Return True if environment or any environment-related tag indicates production."""
    if normalize_str(environment) in PRODUCTION_VALUES:
        return True
    if tags:
        for key, val in tags.items():
            if normalize_str(key) in ENVIRONMENT_TAG_KEYS and normalize_str(val) in PRODUCTION_VALUES:
                return True
    return False
