"""Audit models - re-exports from consolidated models package.

DEPRECATED: Import from app.models instead.
"""
from app.models.audit import AuditLog

__all__ = ["AuditLog"]
