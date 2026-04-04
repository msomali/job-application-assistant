"""FastAPI application factory."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.auth.backend import auth_backend, fastapi_users
from src.auth.manager import UserManager
from src.config import settings
from src.middleware.tenant import TenantMiddleware
from src.schemas import UserCreate, UserRead


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Set secrets from settings
    UserManager.reset_password_token_secret = settings.jwt_secret
    UserManager.verification_token_secret = settings.jwt_secret
    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Job Application Assistant API", lifespan=lifespan)

    app.add_middleware(TenantMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Auth routes
    app.include_router(
        fastapi_users.get_auth_router(auth_backend),
        prefix="/api/auth",
        tags=["auth"],
    )
    app.include_router(
        fastapi_users.get_register_router(UserRead, UserCreate),
        prefix="/api/auth",
        tags=["auth"],
    )
    app.include_router(
        fastapi_users.get_reset_password_router(),
        prefix="/api/auth",
        tags=["auth"],
    )
    app.include_router(
        fastapi_users.get_verify_router(UserRead),
        prefix="/api/auth",
        tags=["auth"],
    )

    # API routes
    from src.routes.profile import router as profile_router
    from src.routes.tasks import router as tasks_router
    app.include_router(profile_router)
    app.include_router(tasks_router)

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok"}

    return app


app = create_app()
