"""Shared base utilities for data models."""
import secrets


def generate_id(prefix: str) -> str:
    """Generate a unique ID with a prefix."""
    return f"{prefix}_{secrets.token_hex(6)}"
