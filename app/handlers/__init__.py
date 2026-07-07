from aiogram import Router

from app.handlers import admin, common, join_requests, verification


def get_root_router() -> Router:
    """Combine all feature routers into a single root router."""
    root = Router(name="root")
    root.include_router(join_requests.router)
    root.include_router(verification.router)
    root.include_router(admin.router)
    root.include_router(common.router)
    return root
