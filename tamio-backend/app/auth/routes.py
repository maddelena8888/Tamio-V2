"""Authentication routes."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.data.models import User
from app.auth import schemas
from app.auth.utils import (
    get_password_hash,
    verify_password,
    create_access_token,
    generate_password_reset_token,
    get_password_reset_expiry,
)
from app.auth.dependencies import get_current_user
from app.config import settings

router = APIRouter()


@router.post("/signup", response_model=schemas.AuthResponse)
async def signup(data: schemas.SignupRequest, db: AsyncSession = Depends(get_db)):
    """
    Register a new user with email and password.
    Returns JWT token on success.
    """
    # Check if email already exists
    result = await db.execute(select(User).where(User.email == data.email))
    existing_user = result.scalar_one_or_none()

    if existing_user:
        # If user exists but has no password, they signed up via Xero
        if existing_user.hashed_password is None:
            # Allow them to set a password
            existing_user.hashed_password = get_password_hash(data.password)
            await db.commit()
            await db.refresh(existing_user)

            token = create_access_token(existing_user.id, existing_user.email)
            return schemas.AuthResponse(
                access_token=token,
                user=schemas.UserAuthInfo.model_validate(existing_user)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )

    # Create new user with default USD currency (will be updated during onboarding)
    user = User(
        email=data.email,
        hashed_password=get_password_hash(data.password),
        base_currency="USD",
        has_completed_onboarding=False
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(user.id, user.email)
    return schemas.AuthResponse(
        access_token=token,
        user=schemas.UserAuthInfo.model_validate(user)
    )


@router.post("/login", response_model=schemas.AuthResponse)
async def login(data: schemas.LoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Authenticate user with email and password.
    Returns JWT token on success.
    """
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    if not user or not user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    if not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    token = create_access_token(user.id, user.email)
    return schemas.AuthResponse(
        access_token=token,
        user=schemas.UserAuthInfo.model_validate(user)
    )


@router.post("/demo-login", response_model=schemas.AuthResponse)
async def demo_login(data: schemas.DemoLoginRequest, db: AsyncSession = Depends(get_db)):
    """
    Login to demo account with special demo token.
    Allows anyone to try Tamio with sample data.
    """
    # Verify demo token
    if data.token != settings.DEMO_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid demo token"
        )

    # Find the demo account
    result = await db.execute(
        select(User).where(User.email == settings.DEMO_ACCOUNT_EMAIL)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Demo account not found"
        )

    # Ensure the account is marked as demo
    if not user.is_demo:
        user.is_demo = True
        await db.commit()
        await db.refresh(user)

    token = create_access_token(user.id, user.email)
    return schemas.AuthResponse(
        access_token=token,
        user=schemas.UserAuthInfo.model_validate(user)
    )


@router.get("/me", response_model=schemas.UserAuthInfo)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current authenticated user info."""
    return schemas.UserAuthInfo.model_validate(current_user)


@router.post("/refresh", response_model=schemas.AuthResponse)
async def refresh_token(current_user: User = Depends(get_current_user)):
    """Refresh the access token (extends session)."""
    token = create_access_token(current_user.id, current_user.email)
    return schemas.AuthResponse(
        access_token=token,
        user=schemas.UserAuthInfo.model_validate(current_user)
    )


@router.post("/complete-onboarding", response_model=schemas.UserAuthInfo)
async def complete_onboarding(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Mark user's onboarding as complete."""
    current_user.has_completed_onboarding = True
    await db.commit()
    await db.refresh(current_user)
    return schemas.UserAuthInfo.model_validate(current_user)


@router.post("/forgot-password", response_model=schemas.ForgotPasswordResponse)
async def forgot_password(
    data: schemas.ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Request a password reset email.
    Always returns success to prevent email enumeration attacks.
    """
    result = await db.execute(select(User).where(User.email == data.email))
    user = result.scalar_one_or_none()

    if user:
        # Generate reset token
        token = generate_password_reset_token()
        user.password_reset_token = token
        user.password_reset_expires = get_password_reset_expiry()
        await db.commit()

        # Build reset URL
        frontend_url = settings.FRONTEND_URL.rstrip("/")
        reset_url = f"{frontend_url}/reset-password?token={token}"

        # Log the reset link (in production, send email instead)
        print("\n" + "=" * 60)
        print("PASSWORD RESET REQUEST")
        print("=" * 60)
        print(f"Email: {user.email}")
        print(f"Reset URL: {reset_url}")
        print(f"Token expires: {user.password_reset_expires}")
        print("=" * 60 + "\n")

    # Always return success to prevent email enumeration
    return schemas.ForgotPasswordResponse(
        message="If an account with that email exists, we've sent password reset instructions."
    )


@router.post("/reset-password", response_model=schemas.ForgotPasswordResponse)
async def reset_password(
    data: schemas.ResetPasswordRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Reset password using a valid reset token.
    """
    # Find user by reset token
    result = await db.execute(
        select(User).where(User.password_reset_token == data.token)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token"
        )

    # Check if token has expired
    if user.password_reset_expires is None or user.password_reset_expires < datetime.now(timezone.utc):
        # Clear the expired token
        user.password_reset_token = None
        user.password_reset_expires = None
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token has expired. Please request a new one."
        )

    # Update password and clear reset token
    user.hashed_password = get_password_hash(data.new_password)
    user.password_reset_token = None
    user.password_reset_expires = None
    await db.commit()

    print(f"\n[PASSWORD RESET] Password successfully reset for: {user.email}\n")

    return schemas.ForgotPasswordResponse(
        message="Your password has been reset successfully. You can now log in."
    )


@router.post("/change-password", response_model=schemas.ForgotPasswordResponse)
async def change_password(
    data: schemas.ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Change password for authenticated user.
    Requires current password verification.
    """
    # Verify current password
    if not current_user.hashed_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No password set. Please use forgot password to set one."
        )

    if not verify_password(data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )

    # Update password
    current_user.hashed_password = get_password_hash(data.new_password)
    await db.commit()

    return schemas.ForgotPasswordResponse(
        message="Password changed successfully"
    )


@router.get("/business-profile", response_model=schemas.BusinessProfileResponse)
async def get_business_profile(current_user: User = Depends(get_current_user)):
    """Get current user's business profile."""
    return schemas.BusinessProfileResponse(
        industry=current_user.industry,
        subcategory=current_user.subcategory,
        revenue_range=current_user.revenue_range,
        base_currency=current_user.base_currency,
        is_complete=current_user.business_profile_completed_at is not None
    )


@router.post("/business-profile", response_model=schemas.UserAuthInfo)
async def save_business_profile(
    data: schemas.BusinessProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Save user's business profile during onboarding.
    Sets the business_profile_completed_at timestamp.
    """
    # Validate subcategory is only provided for professional_services
    if data.industry != 'professional_services' and data.subcategory is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Subcategory is only valid for professional_services industry"
        )

    # Update user's business profile
    current_user.industry = data.industry
    current_user.subcategory = data.subcategory
    current_user.revenue_range = data.revenue_range
    current_user.base_currency = data.base_currency
    current_user.business_profile_completed_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(current_user)

    return schemas.UserAuthInfo.model_validate(current_user)
