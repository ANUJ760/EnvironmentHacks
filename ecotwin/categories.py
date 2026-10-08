"""Waste category taxonomy for EcoTwin."""

from __future__ import annotations
from enum import Enum


class WasteCategory(str, Enum):
    """Core urban waste categories."""

    ORGANIC = "organic"
    RECYCLABLE = "recyclable"
    E_WASTE = "e-waste"
    RESIDUAL = "residual"

    @classmethod
    def from_str(cls, value: str) -> WasteCategory:
        """Parses a string into a WasteCategory, accepting flexible case and hyphen/underscore variations."""
        normalized = value.strip().lower().replace("_", "-")
        for member in cls:
            if member.value == normalized or member.name.lower().replace("_", "-") == normalized:
                return member
        raise ValueError(f"Unknown waste category: '{value}'. Valid categories: {[c.value for c in cls]}")
