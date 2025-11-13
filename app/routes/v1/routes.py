from fastapi import APIRouter, HTTPException
import time
from app.routes.v1.reels.reels import router as reels_router
from app.routes.v1.user.user import router as user_router

v1_routers = APIRouter()

# Include your route modules
v1_routers.include_router(reels_router, prefix="/v1/reels", tags=["Reels"])
v1_routers.include_router(user_router, prefix="/v1/user", tags=["User"])
