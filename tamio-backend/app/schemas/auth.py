"""Authentication schemas."""
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, EmailStr, Field, field_serializer


# Valid industry values
Industry = Literal[
    'professional_services',
    'construction',
    'real_estate',
    'healthcare',
    'technology',
    'creative',
    'hospitality',
    'manufacturing',
    'other'
]

# Valid subcategory values for professional services
ProfessionalSubcategory = Literal[
    'marketing_agency',
    'consulting',
    'legal',
    'accounting',
    'design_agency',
    'it_services'
]

# Valid revenue range values
RevenueRange = Literal[
    '0-500k',
    '500k-2m',
    '2m-5m',
    '5m-15m',
    '15m+'
]

# Valid currency values
Currency = Literal[
    'USD', 'EUR', 'GBP', 'AED', 'AUD', 'CAD', 'CHF', 'SGD', 'JPY', 'NZD'
]


class SignupRequest(BaseModel):
    """Schema for user signup."""
    email: EmailStr
    password: str = Field(..., min_length=8, description="Password must be at least 8 characters")


class LoginRequest(BaseModel):
    """Schema for user login."""
    email: EmailStr
    password: str


class UserAuthInfo(BaseModel):
    """User info returned after auth."""
    id: str
    email: str
    company_name: str | None = None
    base_currency: str
    has_completed_onboarding: bool
    industry: str | None = None
    subcategory: str | None = None
    revenue_range: str | None = None
    business_profile_completed_at: datetime | str | None = None
    is_demo: bool = False

    model_config = {"from_attributes": True}

    @field_serializer('business_profile_completed_at')
    @classmethod
    def serialize_datetime(cls, v: datetime | str | None) -> str | None:
        if v is None:
            return None
        if isinstance(v, datetime):
            return v.isoformat()
        return v


class DemoLoginRequest(BaseModel):
    """Schema for demo account login."""
    token: str = Field(..., description="Demo access token")


class AuthResponse(BaseModel):
    """Schema for authentication response."""
    access_token: str
    token_type: str = "bearer"
    user: UserAuthInfo


class ForgotPasswordRequest(BaseModel):
    """Schema for forgot password request."""
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    """Schema for forgot password response."""
    message: str


class ResetPasswordRequest(BaseModel):
    """Schema for reset password request."""
    token: str
    new_password: str = Field(..., min_length=8, description="Password must be at least 8 characters")


class ChangePasswordRequest(BaseModel):
    """Schema for change password request (authenticated users)."""
    current_password: str
    new_password: str = Field(..., min_length=8, description="Password must be at least 8 characters")


class BusinessProfileRequest(BaseModel):
    """Schema for business profile submission during onboarding."""
    industry: Industry
    subcategory: ProfessionalSubcategory | None = None
    revenue_range: RevenueRange
    base_currency: Currency


class BusinessProfileResponse(BaseModel):
    """Response after getting/saving business profile."""
    industry: str | None = None
    subcategory: str | None = None
    revenue_range: str | None = None
    base_currency: str
    is_complete: bool

    model_config = {"from_attributes": True}
