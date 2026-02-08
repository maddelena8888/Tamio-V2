"""Shared base utilities - re-exports from consolidated models package.

DEPRECATED: Import from app.models instead.
"""
from app.models.base import generate_id

__all__ = ["generate_id"]
