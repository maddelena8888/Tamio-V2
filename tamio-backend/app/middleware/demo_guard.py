"""Middleware to block mutations from demo accounts."""
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.data.models import User
from app.auth.utils import decode_access_token


# Endpoints that are allowed for demo accounts (read-only operations, login, etc.)
ALLOWED_METHODS = {"GET", "OPTIONS", "HEAD"}

# Specific POST endpoints that are allowed for demo accounts
ALLOWED_POST_ENDPOINTS = {
    "/api/auth/login",
    "/api/auth/demo-login",
    "/api/auth/signup",
    "/api/auth/forgot-password",
    "/api/auth/reset-password",
    "/api/auth/refresh",
    # Read-only POST endpoints (forecast calculations, etc.)
    "/api/forecast/calculate",
    "/api/forecast/detailed",
    "/api/tami/chat",
    "/api/tami/chat/stream",
    "/api/scenarios/evaluate/base",
}


class DemoGuardMiddleware(BaseHTTPMiddleware):
    """
    Middleware that blocks mutation operations for demo accounts.

    Demo accounts can:
    - View all data (GET requests)
    - Use TAMI chat
    - View forecasts and scenarios

    Demo accounts cannot:
    - Create/update/delete clients
    - Create/update/delete expenses
    - Modify settings
    - Create/modify scenarios
    - Any other data mutation
    """

    async def dispatch(self, request: Request, call_next):
        # Allow all GET, OPTIONS, HEAD requests
        if request.method in ALLOWED_METHODS:
            return await call_next(request)

        # Check if this is an allowed POST endpoint
        path = request.url.path
        if path in ALLOWED_POST_ENDPOINTS:
            return await call_next(request)

        # Check for allowed endpoint prefixes (like /api/scenarios/*/forecast which is read-only)
        if "/forecast" in path and request.method == "GET":
            return await call_next(request)

        # Extract token from Authorization header
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            # No auth header, let the actual endpoint handle authentication
            return await call_next(request)

        token = auth_header.split(" ")[1]
        payload = decode_access_token(token)

        if not payload:
            # Invalid token, let the actual endpoint handle it
            return await call_next(request)

        user_id = payload.get("sub")
        if not user_id:
            return await call_next(request)

        # Check if user is a demo account
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(User.is_demo).where(User.id == user_id)
            )
            is_demo = result.scalar_one_or_none()

            if is_demo:
                return JSONResponse(
                    status_code=403,
                    content={
                        "detail": "Demo account is read-only. Sign up to save your changes.",
                        "is_demo": True
                    },
                    headers={"X-Demo-Account": "true"}
                )

        return await call_next(request)
