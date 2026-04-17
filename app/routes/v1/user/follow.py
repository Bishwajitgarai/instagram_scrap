from fastapi import APIRouter, HTTPException, Request
from app import scraper
import time

router = APIRouter()

@router.get("/followers/{username}")
async def get_followers(username: str, request: Request, count: int = 12, max_id: str = None):
    """
    Fetch followers for a user.
    """
    start_time = time.time()
    try:
        result = await scraper.fetch_friendships(username, "followers", count, max_id)
        
        processing_time = time.time() - start_time
        if result["success"]:
            return {
                "success": True,
                "username": username,
                "count": result["count"],
                "users": result["data"],
                "next_max_id": result["next_max_id"],
                "processing_time_seconds": round(processing_time, 2)
            }
        else:
            status_code = result.get("status_code", 400)
            raise HTTPException(status_code=status_code, detail=result["error"])

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/following/{username}")
async def get_following(username: str, request: Request, count: int = 12, max_id: str = None):
    """
    Fetch following list for a user.
    """
    start_time = time.time()
    try:
        result = await scraper.fetch_friendships(username, "following", count, max_id)
        
        processing_time = time.time() - start_time
        if result["success"]:
            return {
                "success": True,
                "username": username,
                "count": result["count"],
                "users": result["data"],
                "next_max_id": result["next_max_id"],
                "processing_time_seconds": round(processing_time, 2)
            }
        else:
            status_code = result.get("status_code", 400)
            raise HTTPException(status_code=status_code, detail=result["error"])

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
