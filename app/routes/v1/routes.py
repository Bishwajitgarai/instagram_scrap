from fastapi import APIRouter
from app.routes.v1.reels.reels import router as reels_router
from app.routes.v1.user.user import router as user_router
from app.routes.v1.session.session import router as session_router

v1_routers = APIRouter()

# Unified v1 Prefixing (Removing redundant path segments)
v1_routers.include_router(reels_router, prefix="/reels", tags=["Reels"])
v1_routers.include_router(user_router, prefix="/user", tags=["User"])
v1_routers.include_router(session_router, prefix="/session", tags=["Session"])
