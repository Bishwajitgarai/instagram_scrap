import asyncio
import json
import time
from typing import Optional
from urllib.parse import parse_qs
from fastapi import APIRouter, HTTPException, Request
from app import scraper
from app.core.config import settings

router = APIRouter()

@router.get("/by/username")
async def scrape_user_reels(request: Request, username: str, top_reels_count: Optional[int] = settings.TOP_DEFAULT):
    """
    Scrape user reels with automated fall-back and dynamic cookie support.
    """
    start_time = time.time()
    try:
        # 🟢 Dynamic Cookie Injection
        cookie_header = request.headers.get("Cookie") or request.headers.get("X-IG-Cookie")
        if cookie_header:
            await scraper.import_cookies_from_header(cookie_header)

        # 1. Trigger Virtual Browser Render
        result = await scraper.redirect(f'https://www.instagram.com/{username}/reels/')

        filtered_calls = []
        target_user_id = None
        user_data = {}
        reels_list = []

        # 2. Extract Data from captured calls
        for call in result.get('graphql_calls', []):
            response_body = call.get('response_body', {})
            data = response_body.get("data", {})
            
            # Find User ID
            if not target_user_id:
                user_temp = data.get("user", {})
                if user_temp:
                    target_user_id = user_temp.get("id") or user_temp.get("pk")
                    user_data = user_temp
            
            # Find Reels
            # Modern structure: xdt_api__v1__clips__user__connection_v2
            clips_data = data.get("xdt_api__v1__clips__user__connection_v2", {})
            if clips_data:
                edges = clips_data.get("edges", [])
                for edge in edges:
                    reels_list.append(edge.get("node", {}))
                
                # If we have enough or have paginated_media, we might handle it
                # For now, we capture what the Virtual Browser caught
                filtered_calls.append(call)

        # 3. Handle Pagination (Simplified to use the scraper's session)
        # Note: In a production serverless environment, deep pagination is often 
        # handled by the client or via background tasks. We capture the first 12-24 items 
        # which is "Same to Same" with most browser renders.

        processing_time = time.time() - start_time

        return {
            "success": True,
            "username": username,
            "processing_time_seconds": round(processing_time, 2),
            "total_graphql_calls": len(result.get("graphql_calls", [])),
            "reels_count": len(reels_list),
            "reels_data": reels_list[:top_reels_count] if top_reels_count else reels_list,
            "user_data": user_data,
            "scraped_at": result.get("scraped_at"),
            "navigation_success": result.get("navigation_success", True)
        }

    except Exception as e:
        processing_time = time.time() - start_time
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "error": str(e),
                "processing_time_seconds": round(processing_time, 2),
                "username": username
            }
        )