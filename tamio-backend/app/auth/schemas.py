"""Authentication schemas - re-exports from consolidated schemas package.

DEPRECATED: Import from app.schemas instead.
"""
from app.schemas.auth import (
    Industry,
    ProfessionalSubcategory,
    RevenueRange,
    Currency,
    SignupRequest,
    LoginRequest,
    UserAuthInfo,
    DemoLoginRequest,
    AuthResponse,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    ResetPasswordRequest,
    ChangePasswordRequest,
    BusinessProfileRequest,
    BusinessProfileResponse,
)

__all__ = [
    "Industry",
    "ProfessionalSubcategory",
    "RevenueRange",
    "Currency",
    "SignupRequest",
    "LoginRequest",
    "UserAuthInfo",
    "DemoLoginRequest",
    "AuthResponse",
    "ForgotPasswordRequest",
    "ForgotPasswordResponse",
    "ResetPasswordRequest",
    "ChangePasswordRequest",
    "BusinessProfileRequest",
    "BusinessProfileResponse",
]
