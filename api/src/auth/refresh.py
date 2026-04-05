"""Refresh token endpoint — exchange refresh cookie for new access token."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi_users.authentication import JWTStrategy

from src.auth.backend import get_jwt_strategy, get_refresh_strategy, get_user_manager
from src.auth.manager import UserManager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/refresh")
async def refresh_token(
    request: Request,
    response: Response,
    user_manager: UserManager = Depends(get_user_manager),
):
    """Read refresh_token cookie, validate, return new access + refresh tokens."""
    refresh_cookie = request.cookies.get("refresh_token")
    if not refresh_cookie:
        raise HTTPException(status_code=401, detail="No refresh token")

    # Validate refresh token
    refresh_strategy: JWTStrategy = get_refresh_strategy()
    user = await refresh_strategy.read_token(refresh_cookie, user_manager)
    if user is None or not user.is_active:
        response.delete_cookie("refresh_token", path="/api/auth")
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    # Generate new access token
    access_strategy: JWTStrategy = get_jwt_strategy()
    access_token = await access_strategy.write_token(user)

    # Generate new refresh token (rotation)
    new_refresh = await refresh_strategy.write_token(user)
    response.set_cookie(
        key="refresh_token",
        value=new_refresh,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="lax",
        max_age=604800,
        path="/api/auth",
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "id": str(user.id),
            "email": user.email,
            "tenant_id": str(user.tenant_id) if user.tenant_id else None,
            "role": user.role,
        },
    }
