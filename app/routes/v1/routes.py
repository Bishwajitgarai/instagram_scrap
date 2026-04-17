from fastapi import APIRouter, HTTPException
import time
from app.routes.v1.reels.reels import router as reels_router
from app.routes.v1.user.user import router as user_router
from app.routes.v1.session.session import router as session_router

v1_routers = APIRouter()

# Include your route modules
v1_routers.include_router(reels_router, prefix="/v1/reels", tags=["Reels"])
v1_routers.include_router(user_router, prefix="/v1/user", tags=["User"])
v1_routers.include_router(session_router, prefix="/v1/session", tags=["Session"])
