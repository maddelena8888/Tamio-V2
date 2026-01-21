"""
Routes for UserConfiguration CRUD operations.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.data.users.models import User
from .models import UserConfiguration, SafetyMode
from .schemas import (
    UserConfigurationCreate,
    UserConfigurationUpdate,
    UserConfigurationResponse,
)

router = APIRouter(prefix="/user-config", tags=["User Configuration"])


@router.get("/{user_id}", response_model=UserConfigurationResponse)
async def get_user_configuration(
    user_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Get user configuration.

    Returns the user's detection/preparation settings.
    If no configuration exists, creates one with defaults.
    """
    result = await db.execute(
        select(UserConfiguration).where(UserConfiguration.user_id == user_id)
    )
    config = result.scalar_one_or_none()

    if not config:
        # Create default configuration for user
        config = await _create_default_config(db, user_id)

    return config


@router.post("/", response_model=UserConfigurationResponse)
async def create_user_configuration(
    data: UserConfigurationCreate,
    db: AsyncSession = Depends(get_db),
):
    """
    Create user configuration.

    Creates a new configuration record for the user.
    Raises 400 if configuration already exists.
    """
    # Verify user exists
    user_result = await db.execute(
        select(User).where(User.id == data.user_id)
    )
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Check if config already exists
    existing_result = await db.execute(
        select(UserConfiguration).where(UserConfiguration.user_id == data.user_id)
    )
    if existing_result.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="Configuration already exists for this user. Use PUT to update."
        )

    # Create configuration
    config = UserConfiguration(
        user_id=data.user_id,
        obligations_buffer_amount=data.obligations_buffer_amount or 0,
        runway_buffer_months=data.runway_buffer_months or 6,
        late_payment_threshold_days=data.late_payment_threshold_days or 7,
        unexpected_expense_threshold_pct=data.unexpected_expense_threshold_pct or 20.0,
        safety_mode=SafetyMode(data.safety_mode) if data.safety_mode else SafetyMode.NORMAL,
        payroll_check_days_before=data.payroll_check_days_before or 7,
        payroll_buffer_percent=data.payroll_buffer_percent or 10.0,
        payment_cluster_threshold_pct=data.payment_cluster_threshold_pct or 40.0,
    )

    db.add(config)
    await db.flush()

    return config


@router.put("/{user_id}", response_model=UserConfigurationResponse)
async def update_user_configuration(
    user_id: str,
    data: UserConfigurationUpdate,
    db: AsyncSession = Depends(get_db),
):
    """
    Update user configuration.

    Updates existing configuration. Creates one if it doesn't exist.
    Only provided fields are updated.
    """
    result = await db.execute(
        select(UserConfiguration).where(UserConfiguration.user_id == user_id)
    )
    config = result.scalar_one_or_none()

    if not config:
        # Create default, then apply updates
        config = await _create_default_config(db, user_id)

    # Update fields that were provided
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field == "safety_mode" and value is not None:
            value = SafetyMode(value)
        setattr(config, field, value)

    await db.flush()

    return config


@router.delete("/{user_id}")
async def delete_user_configuration(
    user_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Delete user configuration.

    Removes the configuration record. A new one will be created
    with defaults on next access.
    """
    result = await db.execute(
        select(UserConfiguration).where(UserConfiguration.user_id == user_id)
    )
    config = result.scalar_one_or_none()

    if not config:
        raise HTTPException(status_code=404, detail="Configuration not found")

    await db.delete(config)
    await db.flush()

    return {"status": "deleted", "user_id": user_id}


async def _create_default_config(db: AsyncSession, user_id: str) -> UserConfiguration:
    """Create a default configuration for a user."""
    # Verify user exists
    user_result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    config = UserConfiguration(
        user_id=user_id,
        # All other fields use model defaults
    )

    db.add(config)
    await db.flush()

    return config


async def get_or_create_config(db: AsyncSession, user_id: str) -> UserConfiguration:
    """
    Utility function for engines to get user configuration.

    Returns existing config or creates one with defaults.
    This is the recommended way for detection/preparation engines
    to access user configuration.
    """
    result = await db.execute(
        select(UserConfiguration).where(UserConfiguration.user_id == user_id)
    )
    config = result.scalar_one_or_none()

    if not config:
        config = await _create_default_config(db, user_id)

    return config
