"""FastAPI application factory."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.auth.backend import auth_backend, refresh_backend, fastapi_users
from src.auth.manager import UserManager
from src.config import settings
from src.middleware.tenant import TenantMiddleware
from src.schemas import UserCreate, UserRead, UserUpdate

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Set secrets from settings
    UserManager.reset_password_token_secret = settings.jwt_secret
    UserManager.verification_token_secret = settings.jwt_secret

    # Register Telegram webhook if configured
    if settings.telegram_bot_token and settings.telegram_webhook_base_url:
        try:
            from src.telegram.sender import get_bot
            bot = get_bot()
            if bot:
                webhook_url = f"{settings.telegram_webhook_base_url}/api/telegram/webhook/{settings.telegram_bot_token}"
                await bot.set_webhook(url=webhook_url)
                logger.info("Telegram webhook registered: %s", webhook_url[:50] + "...")
        except Exception:
            logger.exception("Failed to register Telegram webhook")
    else:
        logger.info("Telegram bot disabled — TELEGRAM_BOT_TOKEN or TELEGRAM_WEBHOOK_BASE_URL not set")

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

    # Refresh token login (sets httpOnly cookie)
    app.include_router(
        fastapi_users.get_auth_router(refresh_backend),
        prefix="/api/auth/cookie",
        tags=["auth"],
    )

    # Refresh endpoint
    from src.auth.refresh import router as refresh_router
    app.include_router(refresh_router)

    app.include_router(
        fastapi_users.get_users_router(UserRead, UserUpdate),
        prefix="/api/users",
        tags=["users"],
    )

    # API routes
    from src.routes.admin import router as admin_router
    from src.routes.answers import router as answers_router
    from src.routes.billing import router as billing_router
    from src.routes.discovery import router as discovery_router
    from src.routes.jobs import router as jobs_router
    from src.routes.profile import router as profile_router
    from src.routes.search import router as search_router
    from src.routes.skills import router as skills_router
    from src.routes.tasks import router as tasks_router
    app.include_router(profile_router)
    app.include_router(jobs_router)
    app.include_router(discovery_router)
    app.include_router(search_router)
    app.include_router(skills_router)
    app.include_router(answers_router)
    app.include_router(billing_router)
    app.include_router(admin_router)
    app.include_router(tasks_router)

    from src.telegram.webhook import router as telegram_router
    app.include_router(telegram_router)

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok"}

    return app


app = create_app()
